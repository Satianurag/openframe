"""OpenFrame local HTTP API. Run one worker: uvicorn backend.app:app --host 127.0.0.1."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .bundles import bundle_entries, stream_zip
from .jobs import JobWorker
from .media import frame_bytes, public_asset, register_asset
from .models import JobUpdate, PresetCreate, RenderRequest, SettingsUpdate, request_asset_ids
from .store import Store, now
from .product_import import ProductImport, import_product

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
SECRET_FIELDS = {"comfy_api_key", "comfy_cloud_api_key"}
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
DEFAULTS = {
    "default_provider": "local", "comfy_url": "http://127.0.0.1:8188",
    "comfy_cloud_url": "https://cloud.comfy.org", "comfy_api_key": "", "comfy_cloud_api_key": "",
    "comfy_cli_path": "",
}


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        root = Path(data_dir or os.environ.get("OPENFRAME_DATA_DIR", PROJECT_ROOT / ".openframe"))
        if not root.is_absolute():
            root = PROJECT_ROOT / root
        app.state.store = Store(root)
        app.state.provider_checks = {}
        app.state.worker = JobWorker(app.state.store, lambda: settings(app.state.store), prepare_job)
        app.state.worker.start()
        yield
        app.state.worker.stop()

    app = FastAPI(title="OpenFrame Studio", version="0.1.0", lifespan=lifespan)
    origins = [origin.strip().rstrip("/") for origin in os.environ.get(
        "OPENFRAME_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001"
    ).split(",") if origin.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Validation errors should explain the field, not echo credentials or uploaded request values.
        details = [{key: error[key] for key in ("type", "loc", "msg") if key in error} for error in exc.errors()]
        return JSONResponse({"detail": details}, status_code=422)

    @app.middleware("http")
    async def local_origin_guard(request: Request, call_next):
        # Cross-origin web pages must not submit jobs or upload files to a local GPU studio.
        origin = request.headers.get("origin", "").rstrip("/")
        same_origin = str(request.base_url).rstrip("/")
        if request.method in {"POST", "PATCH", "DELETE"} and origin and origin not in origins and origin != same_origin:
            return JSONResponse({"detail": "This browser origin is not allowed to change the studio"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/settings"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/import/product", status_code=201)
    def product_import(body: ProductImport):
        return import_product(app.state.store, body.url)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0", "ffmpeg": bool(shutil.which("ffmpeg")),
                "worker_alive": app.state.worker.thread.is_alive()}

    @app.get("/api/catalog")
    def catalog():
        from engine.catalog import get_catalog
        result = get_catalog()
        current = settings(app.state.store)
        for provider in result["providers"]:
            ident = provider["id"]
            provider["configured"] = provider_configured(ident, current)
            provider["available"] = None
            provider["detail"] = "Connection has not been checked" if provider["configured"] else "Configure this provider in Settings"
            provider.update(app.state.provider_checks.get(ident, {}))
            if ident == "comfy-cloud":
                provider["unsupported_tasks"] = ["text-to-image", "image-edit", "audio-to-video", "motion-transfer", "character-replacement", "background-removal", "text-to-speech"]
        result["limits"] = {"max_upload_mb": int(os.environ.get("OPENFRAME_MAX_UPLOAD_MB", "512")), "parallel_jobs": 1}
        return result

    @app.get("/api/settings")
    def read_settings():
        from engine.cloud import auth_status
        current = settings(app.state.store)
        public = {key: value for key, value in current.items() if key not in SECRET_FIELDS}
        for key in SECRET_FIELDS:
            public["has_" + key] = bool(current.get(key))
        public["comfy_cloud_auth"] = auth_status(current)
        return public

    @app.patch("/api/settings")
    def update_settings(update: SettingsUpdate):
        changes = update.model_dump(exclude_none=True)
        if "default_provider" in changes:
            from engine.catalog import get_catalog
            if changes["default_provider"] not in {item["id"] for item in get_catalog()["providers"]}:
                raise HTTPException(422, "Unknown default provider")
        app.state.store.save_settings(changes)
        app.state.provider_checks.clear()
        return read_settings()

    @app.post("/api/providers/{provider}/check")
    def check_provider(provider: str):
        from engine.catalog import get_catalog
        from engine.runner import check_provider as engine_check
        if provider not in {item["id"] for item in get_catalog()["providers"]}:
            raise HTTPException(404, "Unknown compute provider")
        current = settings(app.state.store)
        try:
            result = engine_check(provider, current)
        except Exception as exc:
            result = {"available": False, "detail": redact(str(exc), current)}
        result["checked_at"] = now()
        app.state.provider_checks[provider] = result
        return result

    @app.post("/api/assets", status_code=201)
    async def upload_asset(file: UploadFile = File(...)):
        root = app.state.store.root / "uploads"
        root.mkdir(exist_ok=True, mode=0o700)
        temp = root / (uuid.uuid4().hex + ".upload")
        maximum = int(os.environ.get("OPENFRAME_MAX_UPLOAD_MB", "512")) * 1024 * 1024
        size = 0
        try:
            with temp.open("wb") as handle:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise HTTPException(413, f"Upload is larger than {maximum // (1024 * 1024)} MiB")
                    handle.write(chunk)
            if size == 0:
                raise HTTPException(422, "The uploaded file is empty")
            try:
                asset = await run_in_threadpool(register_asset, app.state.store, temp, file.filename or "upload", move=True)
            except (ValueError, OSError) as exc:
                raise HTTPException(422, str(exc)) from exc
            return public_asset(asset)
        finally:
            temp.unlink(missing_ok=True)
            await file.close()

    @app.get("/api/assets")
    def list_assets(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return {"items": [public_asset(item, app.state.store) for item in app.state.store.list("assets", limit, offset)],
                "total": app.state.store.count("assets"), "offset": offset}

    @app.get("/api/assets/{asset_id}")
    def get_asset(asset_id: str):
        return public_asset(required_record(app.state.store, "assets", asset_id), app.state.store)

    @app.get("/api/assets/{asset_id}/file")
    def asset_file(asset_id: str, download: bool = False):
        asset = required_record(app.state.store, "assets", asset_id)
        path = checked_media_path(app.state.store, asset["path"])
        return FileResponse(path, media_type=asset.get("mime_type"), filename=asset["name"],
                            content_disposition_type="attachment" if download or asset["kind"] == "archive" else "inline")

    @app.get("/api/assets/{asset_id}/thumbnail")
    def asset_thumbnail(asset_id: str):
        asset = required_record(app.state.store, "assets", asset_id)
        if not asset.get("thumbnail_path"):
            raise HTTPException(404, "No thumbnail is available")
        return FileResponse(checked_media_path(app.state.store, asset["thumbnail_path"]), media_type="image/jpeg")

    @app.get("/api/assets/{asset_id}/frame")
    def asset_frame(asset_id: str, time: float = Query(0, ge=0)):
        asset = required_record(app.state.store, "assets", asset_id)
        path = checked_media_path(app.state.store, asset["path"])
        if asset["kind"] not in {"image", "video"}:
            raise HTTPException(422, "This asset is not a viewable image or video; use its download")
        if asset.get("duration") and time >= asset["duration"]:
            raise HTTPException(422, "The requested time is beyond this video's duration")
        try:
            return Response(frame_bytes(path, time), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/assets/{asset_id}")
    def delete_asset(asset_id: str):
        with app.state.store.lock:
            asset = required_record(app.state.store, "assets", asset_id)
            references = app.state.store.asset_references(asset_id)
            if references:
                raise HTTPException(409, "This asset is used by a saved render or app document. Remove its document attachment or delete the referencing render before deleting its media.")
            for key in ("path", "thumbnail_path"):
                if asset.get(key):
                    path = Path(asset[key]).resolve()
                    if path.is_relative_to(app.state.store.root):
                        path.unlink(missing_ok=True)
            app.state.store.delete("assets", asset_id)
        return {"deleted": asset_id}

    def prepare_job(request: RenderRequest, *, require_assets=True, check_provider=True):
        data, warnings = validate_request(request, app.state.store, require_assets=require_assets)
        if check_provider and not provider_configured(data["provider"], settings(app.state.store)):
            raise HTTPException(422, "Configure the selected compute provider in Settings before rendering")
        timestamp = now()
        if data["seed"] == -1:
            data["seed"] = secrets.randbelow(2**32)
        from engine.workflows import normalize_request
        try:
            data = normalize_request(data)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        job = {"id": uuid.uuid4().hex, "status": "queued", "progress": 0, "stage": "Queued",
               "created_at": timestamp, "updated_at": timestamp, "request": data,
               "outputs": [], "error": None, "favorite": False, "warnings": warnings, "cancel_requested": False}
        return job

    @app.post("/api/jobs", status_code=201)
    def create_job(request: RenderRequest):
        with app.state.store.lock:
            job = prepare_job(request)
            app.state.store.insert("jobs", job)
        app.state.worker.wake.set()
        return public_job(job)

    @app.get("/api/jobs")
    def list_jobs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return {"items": [public_job(job) for job in app.state.store.list("jobs", limit, offset)],
                "total": app.state.store.count("jobs"), "offset": offset}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return public_job(required_record(app.state.store, "jobs", job_id))

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        required_record(app.state.store, "jobs", job_id)
        return public_job(app.state.worker.cancel(job_id))

    @app.post("/api/jobs/{job_id}/retry", status_code=201)
    def retry_job(job_id: str):
        job = required_record(app.state.store, "jobs", job_id)
        if job["status"] not in TERMINAL_STATES:
            raise HTTPException(409, "Cancel or finish this render before retrying it")
        with app.state.store.lock:
            if job.get("kind") == "character-training":
                from .characters import retry_training
                replacement = retry_training(app.state.store, job)
                app.state.worker.wake.set()
                return public_job(replacement)
            replacement = prepare_job(RenderRequest.model_validate(job["request"]))
            with app.state.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT record FROM app_job_links WHERE job_id=?", (job_id,)).fetchone()
                if row:
                    association = json.loads(row[0])
                    association["job_id"] = replacement["id"]
                    replacement["app_context"] = job["app_context"]
                    db.execute("INSERT INTO app_job_links VALUES (?,?,?,?)", (replacement["id"], association["app_id"], association["document_id"], json.dumps(association)))
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (replacement["id"], replacement["status"], replacement["created_at"], replacement["updated_at"], json.dumps(replacement)))
        app.state.worker.wake.set()
        return public_job(replacement)

    @app.patch("/api/jobs/{job_id}")
    def update_job(job_id: str, update: JobUpdate):
        required_record(app.state.store, "jobs", job_id)
        return public_job(app.state.store.update_job(job_id, update.model_dump()))

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str):
        with app.state.store.lock:
            job = required_record(app.state.store, "jobs", job_id)
            if job["status"] not in TERMINAL_STATES:
                raise HTTPException(409, "Cancel or finish this render before deleting it")
            with app.state.store.connection() as db:
                if db.execute("SELECT 1 FROM characters WHERE job_id=?", (job_id,)).fetchone():
                    raise HTTPException(409, "Remove the character registry record before deleting its training provenance")
                if db.execute("SELECT 1 FROM sequence_job_links WHERE job_id=? LIMIT 1", (job_id,)).fetchone():
                    raise HTTPException(409, "This render belongs to a saved sequence. Delete the sequence before deleting its shot provenance.")
            app.state.store.delete("jobs", job_id)
        # Outputs remain in the asset library so other edits can still refer to them.
        return {"deleted": job_id, "media_retained": True}

    @app.post("/api/workflows/export")
    def export_workflow(request: RenderRequest):
        data, _ = validate_request(request, app.state.store)
        return graph_response(build_export(data, app.state.store), f"openframe-{data['model_id']}-{data['effect_id']}.json")

    @app.get("/api/jobs/{job_id}/workflow")
    def job_workflow(job_id: str, format: str = Query("api", pattern="^(api|ui)$")):
        job = required_record(app.state.store, "jobs", job_id)
        if format == "ui":
            if not job.get("ui_workflow"):
                raise HTTPException(409, "A canvas graph is not available for this run. Export the API graph instead.")
            graph = job["ui_workflow"]
        else:
            try:
                graph = job.get("workflow") or build_export(job["request"], app.state.store)
            except ValueError as exc:
                raise HTTPException(422, f"No executed graph was saved, and this recipe cannot be rebuilt: {exc}") from exc
        return graph_response(graph, f"openframe-{job_id}-{format}.json")

    @app.get("/api/jobs/{job_id}/bundle")
    def job_bundle(job_id: str, include_media: bool = False):
        job = required_record(app.state.store, "jobs", job_id)
        try:
            graph = job.get("workflow") or build_export(job["request"], app.state.store)
            entries = bundle_entries(app.state.store, job, graph, PROJECT_ROOT, include_media)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        kind = "project" if include_media else "recipe"
        return StreamingResponse(stream_zip(entries), media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="openframe-{job_id}-{kind}.zip"'
        })

    @app.get("/api/presets")
    def list_presets():
        return {"items": app.state.store.list("presets", 500)}

    @app.post("/api/presets", status_code=201)
    def create_preset(preset: PresetCreate):
        data, _ = validate_request(preset.request, app.state.store, require_assets=False)
        # Presets capture the recipe, not a dependency on a particular uploaded clip.
        for key in ("source_asset_id", "mask_asset_id", "reference_asset_id", "audio_asset_id"):
            data[key] = None
        data["reference_asset_ids"] = []
        record = {"id": uuid.uuid4().hex, "name": preset.name.strip(), "request": data, "created_at": now()}
        if not record["name"]:
            raise HTTPException(422, "Give this preset a name")
        app.state.store.insert("presets", record)
        return record

    @app.delete("/api/presets/{preset_id}")
    def delete_preset(preset_id: str):
        required_record(app.state.store, "presets", preset_id)
        app.state.store.delete("presets", preset_id)
        return {"deleted": preset_id}

    from .apps import install_app_routes
    install_app_routes(app, prepare_job, public_job)
    from .sequences import install_sequence_routes
    install_sequence_routes(app, prepare_job)
    from .characters import install_character_routes
    install_character_routes(app, public_job, lambda: settings(app.state.store))

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        dist = PROJECT_ROOT / "frontend" / "dist"
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
        return JSONResponse({"detail": "The API is running. Start the frontend dev server or build frontend/dist.", "api_docs": "/docs"})

    return app


def settings(store: Store) -> dict:
    result = {key: os.environ.get("OPENFRAME_" + key.upper(), value) for key, value in DEFAULTS.items()}
    result.update({key: value for key, value in store.read_settings().items() if key in DEFAULTS})
    if result.get("default_provider") not in {"local", "comfy-cloud"}:
        result["default_provider"] = "local"
        result["default_provider_notice"] = "The saved provider is unavailable. Local ComfyUI is the default; historical jobs retain their recorded provider and are not rerouted."
    return result


def provider_configured(provider: str, current: dict) -> bool:
    if provider == "local":
        return bool(current.get("comfy_url"))
    if provider == "comfy-cloud":
        from engine.cloud import auth_status
        return bool(current.get("comfy_cloud_url") and auth_status(current)["mode"] != "missing")
    return False


def redact(message: str, current: dict) -> str:
    for key in SECRET_FIELDS:
        if current.get(key):
            message = message.replace(current[key], "[redacted]")
    if os.environ.get("COMFY_API_KEY"):
        message = message.replace(os.environ["COMFY_API_KEY"], "[redacted]")
    return message[:2000]


SEQUEL_CONTEXT_NOTE = "The output begins with the selected context interval, followed by generated continuation; it does not include the entire original clip."
PREQUEL_CONTEXT_NOTE = "The output begins with generated footage, followed by the selected context interval; it does not include the entire original clip."


def region_focus_note(width, height):
    return f"The painted region is sampled at 1024×1024, then stitched back into the original {width}×{height} canvas; protected original pixels are retained."


def public_job(job: dict) -> dict:
    result = {key: value for key, value in job.items() if key not in {"workflow", "ui_workflow", "cancel_requested"}}
    if job.get("request", {}).get("extension_direction") == "prequel" and job.get("warnings"):
        # Correct the historical display note without rewriting the stored run.
        result["warnings"] = [PREQUEL_CONTEXT_NOTE if note == SEQUEL_CONTEXT_NOTE else note for note in job["warnings"]]
    request = job.get("request", {})
    if request.get("image_edit_focus") == "masked-region" and result.get("warnings"):
        width, height = request.get("source_width") or request.get("width"), request.get("source_height") or request.get("height")
        old = f"Protected source pixels are composited back into the final {width}×{height} image; the generation canvas is padded to {request.get('width')}×{request.get('height')} then cropped."
        result["warnings"] = [region_focus_note(width, height) if note == old else note for note in result["warnings"]]
    return result


def required_record(store: Store, table: str, ident: str) -> dict:
    record = store.get(table, ident)
    if not record:
        raise HTTPException(404, f"{table[:-1].capitalize()} not found")
    return record


def checked_media_path(store: Store, value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(store.root) or not path.is_file():
        raise HTTPException(404, "The media file is no longer available")
    return path


def validate_request(request: RenderRequest, store: Store, *, require_assets: bool = True) -> tuple[dict, list[str]]:
    from engine.catalog import get_catalog, allows_restyle_first_frame, reference_limits
    catalog = get_catalog()
    data = request.model_dump()
    if SECRET_FIELDS.intersection(request.model_extra or {}):
        raise HTTPException(422, "Store provider credentials in Settings, not in a render request")
    data.pop("job_id", None)
    if not data["mask_tracking"] or data["mask_tracking_method"] == "static":
        data.update(mask_tracking=False, mask_tracking_method="static")
    model = next((item for item in catalog["models"] if item["id"] == data["model_id"]), None)
    effect = next((item for item in catalog["effects"] if item["id"] == data["effect_id"]), None)
    if not model or not effect:
        raise HTTPException(422, "Select a supported model and effect")
    if data["image_brightness"] and not model.get("supports_image_brightness"):
        raise HTTPException(422, "This model does not implement post-render image brightness")
    for field in ("width", "height", "frames", "fps", "steps", "guidance", "negative_prompt", "strength"):
        if field not in request.model_fields_set:
            data[field] = model.get("default_" + field, data[field])
    if "voice" not in request.model_fields_set and model.get("voices"):
        data["voice"] = model["voices"][0]["id"]
    for field in ("steps", "guidance"):
        fixed = model.get("fixed_" + field)
        if fixed is not None and data[field] != fixed:
            raise HTTPException(422, f"{model['name']} requires {field}={fixed} for its matched checkpoint/scheduler")
    if "provider" not in request.model_fields_set:
        data["provider"] = settings(store)["default_provider"]
    if data["provider"] not in {item["id"] for item in catalog["providers"]}:
        raise HTTPException(422, "Select a supported compute provider")
    if model.get("supported_providers") and data["provider"] not in model["supported_providers"]:
        raise HTTPException(422, "This model is implemented for " + ", ".join(model["supported_providers"]) + "; no alternate model will be substituted")
    provider_tasks = model.get("provider_tasks", {}).get(data["provider"])
    if provider_tasks is not None and effect["task"] not in provider_tasks:
        raise HTTPException(422, "This provider does not implement the selected model operation; no substitute workflow will be used")
    if data["restyle_method"] == "water" and data["audio_mode"] == "generated":
        raise HTTPException(422, "The released Water-Simulation recipe supports source audio or silence, not newly generated audio")
    if data["inpaint_composite_mode"] == "plate-fit" and (model["id"] != "ltx-2.5" or effect["id"] != "replace-object" or not data["preserve_outside_mask"]):
        raise HTTPException(422, "Plate fitting requires LTX 2.5 object replacement with original-background preservation")
    if data["model_id"] not in effect["model_ids"] or effect["task"] not in model["tasks"]:
        raise HTTPException(422, "This model does not support the selected effect")
    if model["id"] == "flux-klein-editvid" and "generate_audio" not in request.model_fields_set:
        data["generate_audio"] = False
    if data["audio_mode"] is not None:
        if data["audio_mode"] not in model.get("audio_modes_by_task", {}).get(effect["task"], []):
            raise HTTPException(422, "This model and operation do not support the selected explicit audio mode")
        data["preserve_audio"] = data["audio_mode"] == "source"
        data["generate_audio"] = data["audio_mode"] == "generated"
    from .characters import resolve_character
    resolve_character(store, data, model, settings(store))
    assets = {}
    for role, ident in request_asset_ids(data).items():
        assets[role] = required_record(store, "assets", ident)
        checked_media_path(store, assets[role]["path"])
    source = assets.get("source")
    if model["id"] == "qwen-portrait-relight":
        from engine.portrait_relight_workflows import portrait_relight_size
        if any(data.get(key) for key in ("reference_asset_id", "reference_asset_ids", "mask_asset_id", "audio_asset_id", "image_layout", "character_adapter_id")) or data["image_preservation"] != "none":
            raise HTTPException(422, "Portrait Relight accepts one opaque source portrait; its exported workflow computes foreground masks. Extra references, masks, audio and adapters are unsupported")
        if require_assets and (not source or source["kind"] != "image"):
            raise HTTPException(422, "Upload one opaque source portrait for Portrait Relight")
        if source and source["kind"] == "image":
            from PIL import Image
            with Image.open(source["path"]) as image:
                if image.mode not in {"RGB", "RGBA"} or (image.mode == "RGBA" and image.getchannel("A").getextrema() != (255, 255)):
                    raise HTTPException(422, "Portrait Relight requires an opaque RGB or RGBA source image")
            width, height = portrait_relight_size(source["width"], source["height"])
            for axis, value in (("width", width), ("height", height)):
                if axis in request.model_fields_set and data[axis] != value:
                    raise HTTPException(422, f"Portrait Relight uses the native source-derived {width} × {height} canvas; omit dimensions or use that exact size")
                data[axis] = value
    if model["id"] == "qwen-image-relight":
        from engine.image_relight_workflows import image_relight_size
        if data["mask_asset_id"] or data["reference_asset_ids"] or data["image_layout"] or data["character_adapter_id"] or data["image_preservation"] != "none":
            raise HTTPException(422, "Directional image relighting accepts one source photo and one prepared lighting-map PNG, without masks, additional references, layout, character adapters or pixel-preservation compositing")
        light = assets.get("reference")
        if require_assets and (not source or source["kind"] != "image" or not light or light["kind"] != "image" or light.get("mime_type") != "image/png"):
            raise HTTPException(422, "Upload a source photo and its prepared opaque lighting-map PNG; direction controls alone are not an image input")
        if light:
            from PIL import Image
            with Image.open(light["path"]) as image:
                if image.mode not in {"RGB", "RGBA"} or (image.mode == "RGBA" and image.getchannel("A").getextrema() != (255, 255)):
                    raise HTTPException(422, "The prepared lighting map must be an opaque RGB or RGBA PNG")
        if source and source["kind"] == "image":
            width, height = image_relight_size(source["width"], source["height"])
            for axis, value in (("width", width), ("height", height)):
                if axis in request.model_fields_set and data[axis] != value:
                    raise HTTPException(422, f"The released relighting recipe derives {width} × {height} from the source at one megapixel; omit output dimensions or use that exact canvas")
                data[axis] = value
    if model["id"] == "ltx-2.3-relight":
        if data["mask_asset_id"] or data["reference_asset_ids"] or data["image_layout"] or data["enhance_prompt"] is True or data["audio_mode"] == "generated":
            raise HTTPException(422, "Relight accepts a source video and one prepared lighting-sphere PNG, without masks, additional references, layout, prompt enhancement or generated audio")
        sphere = assets.get("reference")
        if require_assets and (not sphere or sphere["kind"] != "image" or sphere.get("mime_type") != "image/png"):
            raise HTTPException(422, "Upload the prepared lighting-sphere PNG; rotation, elevation and intensity record its controls and do not render an image on the server")
    if data["inpaint_reference_mode"] is not None or (model["id"] == "ltx-2.5" and effect["task"] == "inpaint" and assets.get("reference")):
        if model["id"] != "ltx-2.5" or effect["task"] != "inpaint" or data["inpaint_reference_mode"] != "edited-first-frame":
            raise HTTPException(422, "LTX2.5 masked editing requires explicit edited-first-frame mode for an additional reference")
        reference = assets.get("reference")
        if data["video_refinement"] != "two-stage":
            raise HTTPException(422, "The released edited-first-frame inpaint recipe requires two-stage refinement")
        if data["reference_asset_ids"]:
            raise HTTPException(422, "Edited-first-frame conditioning accepts one full starting image, not an image list")
        if require_assets and (not source or source["kind"] != "video" or not reference or reference["kind"] != "image"):
            raise HTTPException(422, "Upload the source video and the edited full starting frame for the selected interval")
        if source and reference and (source["width"], source["height"]) != (reference["width"], reference["height"]):
            raise HTTPException(422, "The edited starting frame must match the source video's native dimensions exactly; an isolated object reference is not this conditioning mode")
    if data["vace_reference_mode"] == "first-frame":
        if model["id"] != "wan-vace-14b" or effect["task"] != "inpaint":
            raise HTTPException(422, "First-frame VACE control is available only for Wan VACE 14B masked video editing")
        reference = assets.get("reference")
        if data["reference_asset_ids"]:
            raise HTTPException(422, "First-frame control uses exactly one edited full-frame reference image")
        if require_assets and (not source or source["kind"] != "video" or not reference or reference["kind"] != "image"):
            raise HTTPException(422, "Upload the source video and its edited full starting frame")
        if source and reference and (source["width"], source["height"]) != (reference["width"], reference["height"]):
            raise HTTPException(422, "The edited starting frame must match the source video's native dimensions exactly")
    transition = effect["task"] == "transition-video"
    if transition:
        if "frames" not in request.model_fields_set:
            data["frames"] = 121
        if require_assets and any(not assets.get(role) or assets[role]["kind"] not in {"image", "video"} for role in ("source", "end")):
            raise HTTPException(422, "Upload both transition inputs: images or videos no longer than five seconds")
        for role in ("source", "end"):
            asset = assets.get(role)
            if asset and asset["kind"] == "video" and (not 0 < (asset.get("duration") or 0) <= 5.001 or not 0 < (asset.get("fps") or 0) <= 120):
                raise HTTPException(422, f"The {role} transition clip must be no longer than five seconds and no faster than 120 fps. Trim it explicitly first.")
        from engine.transitions import validate_transition_request
        try:
            validate_transition_request(data)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif assets.get("end") or data["transition_include_inputs"]:
        raise HTTPException(422, "A second endpoint and input-clip assembly are supported only by transition-video")
    if effect["task"] == "frame-interpolation":
        data["input_frames"] = data["input_frames"] or 97
        data["input_fps"] = data["input_fps"] or (source.get("fps") if source else None) or 24
        derived = int((data["input_frames"] - 1) / data["input_fps"] * data["fps"] + 1e-9) + 1
        if "frames" in request.model_fields_set and data["frames"] != derived:
            raise HTTPException(422, f"Interpolation produces {derived} frames for this source interval and target FPS; use that count or omit frames")
        data["frames"] = derived
    if source and source.get("width") and source.get("height"):
        data["source_width"], data["source_height"] = source["width"], source["height"]
    elif require_assets:
        data["source_width"], data["source_height"] = None, None
    from engine.editvid_workflows import validate_editvid
    try:
        validate_editvid(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if model.get("preserve_source_aspect") and source and source.get("width") and source.get("height"):
        ratio = source["width"] / source["height"]
        if not {"width", "height"}.intersection(request.model_fields_set):
            scale = min(1, model.get("default_width", 768) / max(source["width"], source["height"]))
            data["width"], data["height"] = (max(2, round(source[axis] * scale / 2) * 2) for axis in ("width", "height"))
        elif "width" not in request.model_fields_set:
            data["width"] = round(data["height"] * ratio / 2) * 2
        elif "height" not in request.model_fields_set:
            data["height"] = round(data["width"] / ratio / 2) * 2
        if abs(data["width"] / data["height"] - ratio) > 2 / data["height"]:
            raise HTTPException(422, "Depth output must retain the source aspect ratio; omit width/height for a bounded source-matched canvas")
    source_exact_task = effect["task"] == "alpha-matte" or (effect["task"] == "video-upscale" and data["upscale_mode"] == "pixel-2x")
    if source_exact_task and source:
        factor = 2 if effect["task"] == "video-upscale" else 1
        for axis in ("width", "height"):
            exact = source[axis] * factor
            padded = ((exact + 31) // 32) * 32
            if axis in request.model_fields_set and data[axis] not in {exact, padded}:
                raise HTTPException(422, f"This operation preserves source geometry: output {axis} is {exact}, with inference padding to {padded}")
            data[axis] = padded
    expanding_image = effect["task"] == "image-outpaint"
    if expanding_image:
        if assets.get("mask"):
            raise HTTPException(422, "Expand Image protects the original rectangle automatically; it does not accept an external mask")
        if source and (data["width"] < source.get("width", 0) or data["height"] < source.get("height", 0)
                       or (data["width"], data["height"]) == (source.get("width"), source.get("height"))):
            raise HTTPException(422, "Expand Image must enlarge at least one dimension without shrinking either source dimension")
        data["image_preservation"], data["mask_feather"] = "inside-mask", 0
    preserving_image = data["image_preservation"] != "none"
    if preserving_image and not expanding_image:
        if not model.get("supports_image_preservation") or effect["task"] != "image-edit":
            raise HTTPException(422, "Pixel preservation requires a compatible image-editing model")
        mask = assets.get("mask")
        if require_assets and (not source or source["kind"] != "image" or not mask or mask["kind"] != "image"):
            raise HTTPException(422, "Upload a source image and its painted grayscale image mask for pixel preservation")
        if source and mask and (source["width"], source["height"]) != (mask["width"], mask["height"]):
            raise HTTPException(422, "The preservation mask must have exactly the source image dimensions; it is never silently resized")
        if source:
            data["width"] = ((source["width"] + 15) // 16) * 16
            data["height"] = ((source["height"] + 15) // 16) * 16
    if data["image_edit_focus"] == "masked-region":
        if (not model.get("supports_region_focus") or effect["task"] != "image-edit"
                or data["image_preservation"] != "outside-mask"):
            raise HTTPException(422, "Masked-region focus requires a compatible FLUX3 image edit with outside-mask preservation")
        if data["reference_asset_id"] or data["reference_asset_ids"] or data["image_layout"]:
            raise HTTPException(422, "Masked-region focus uses only its original source and native mask; clear additional references and layout regions")
    if (model.get("preserve_source_dimensions") or effect.get("preserve_source_dimensions")) and source:
        required_kind = "image" if effect.get("output_kind") == "image" else "video"
        if source["kind"] != required_kind:
            raise HTTPException(422, f"This operation requires a source {required_kind}")
        data["width"], data["height"] = source["width"], source["height"]
    if model.get("preserve_source_fps") and source:
        source_fps = source.get("fps")
        if not source_fps or not 1 <= source_fps <= 120:
            raise HTTPException(422, "The source frame rate could not be determined")
        if "fps" in request.model_fields_set and abs(data["fps"] - source_fps) > .000001:
            raise HTTPException(422, f"This operation preserves the source's {source_fps:g} fps; choose that rate or omit fps")
        data["fps"] = source_fps
    for axis in ("width", "height"):
        value = data[axis]
        if value < model.get(f"min_{axis}", 64) or value > model.get(f"max_{axis}", 4096):
            raise HTTPException(422, f"{axis.capitalize()} must be between {model[f'min_{axis}']} and {model[f'max_{axis}']} for {model['name']}")
        multiple = model.get("dimension_multiple", 1)
        if value % multiple:
            raise HTTPException(422, f"{model['name']} requires {axis} to be a multiple of {multiple}")
    image_task = effect.get("output_kind") == "image"
    non_video = effect.get("output_kind") in {"image", "audio"}
    if non_video:
        data["frames"], data["fps"] = 1, 1.0
    if data["provider"] == "comfy-cloud" and effect["task"] in {"text-to-image", "image-edit", "audio-to-video", "motion-transfer", "character-replacement", "background-removal", "text-to-speech"}:
        raise HTTPException(422, "This operation requires Local ComfyUI and is unavailable on the Cloud adapter; no alternative operation will be substituted.")
    if not 1 <= data["batch_size"] <= model.get("max_batch_size", 1):
        raise HTTPException(422, "This model does not support the requested batch size")
    if not non_video and model.get("fixed_fps") is not None and data["fps"] != model["fixed_fps"]:
        raise HTTPException(422, f"{model['name']} requires exactly {model['fixed_fps']:g} fps; choose that frame rate explicitly")
    minimum_frames = model.get("min_frames", 9)
    if not non_video and (data["frames"] < minimum_frames or data["frames"] > model["max_frames"] or (data["frames"] - 1) % model["frame_multiple"]):
        raise HTTPException(422, f"{model['name']} requires 1 + multiples of {model['frame_multiple']} frames, from {minimum_frames} to {model['max_frames']}")
    limits = {**model.get("default_task_limits", {}), **model.get("task_limits", {}).get(effect["task"], {})}
    if effect["task"] == "sdr-to-hdr" and data["hdr_output_format"] == "exr16":
        if (data["frames"] > 241 or max(data["width"], data["height"]) > 1920 or min(data["width"], data["height"]) > 1088
                or data["width"] * data["height"] > 1920 * 1088
                or data["width"] * data["height"] * data["frames"] * 6 > 4 * 1024**3):
            raise HTTPException(422, "EXR sequence export is limited to241frames,1920×1088pixels and4GiB of estimated raw RGB half-float data")
    elif effect["task"] != "sdr-to-hdr" and data["hdr_output_format"] != "hevc10":
        raise HTTPException(422, "HDR output format applies only to SDR-to-HDR conversion")
    if (data["frames"] > limits.get("max_frames", model["max_frames"])
            or max(data["width"], data["height"]) > limits.get("max_long_side", 4096)
            or min(data["width"], data["height"]) > limits.get("max_short_side", 4096)
            or data["width"] * data["height"] > limits.get("max_pixels", 4096 ** 2)):
        raise HTTPException(422, "The selected task exceeds its documented frame or canvas bounds; read the model's task_limits")
    if effect["task"] == "video-extend" and ((data["context_frames"] - 1) % 8 or data["frames"] <= data["context_frames"]):
        raise HTTPException(422, "Extension requires 8n+1 context frames and a total frame count greater than the context")
    if require_assets and not transition and effect["requires_video"] and (not source or source["kind"] != "video"):
        raise HTTPException(422, "Upload a source video for this effect")
    if require_assets and not transition and effect["requires_image"] and (not source or source["kind"] != "image"):
        raise HTTPException(422, "Upload a source image for this effect")
    if require_assets and effect["requires_mask"] and not model.get("mask_optional") and "mask" not in assets:
        raise HTTPException(422, "Paint or upload a mask for this effect")
    if require_assets and effect.get("requires_audio") and (not assets.get("audio") or assets["audio"]["kind"] != "audio"):
        raise HTTPException(422, "Upload a voice recording for this operation")
    if assets.get("audio") and (not effect.get("requires_audio") or assets["audio"]["kind"] != "audio"):
        raise HTTPException(422, "Audio input is supported only by the uploaded-speech operation")
    ordered_references = data["reference_asset_ids"]
    reference_limit = reference_limits(model, effect)
    if len(set(ordered_references)) != len(ordered_references):
        raise HTTPException(422, "Reference images must be distinct; remove duplicate asset IDs")
    if effect["task"] == "reference-video":
        if data["reference_asset_id"]:
            raise HTTPException(422, "Reference-to-video uses ordered reference_asset_ids, not a single reference image")
        if any(assets.get(role) for role in ("source", "mask", "audio", "end")):
            raise HTTPException(422, "Reference-to-video accepts only reference images; remove the source, mask, audio or end asset")
        if len(ordered_references) < max(1, reference_limit["min"]):
            raise HTTPException(422, "Reference-to-video requires one to nine ordered reference images")
        if len(ordered_references) > reference_limit["max"]:
            raise HTTPException(422, f"Reference-to-video accepts at most {reference_limit['max']} reference images; remove the extra references instead of relying on truncation")
    elif ordered_references and not image_task:
        raise HTTPException(422, "This operation accepts at most one reference image; use reference_asset_id. Ordered reference lists are supported only by reference-to-video and image generation/editing")
    has_reference = "reference" in assets or (effect["task"] == "reference-video" and bool(ordered_references))
    if require_assets and (effect.get("requires_reference") or model.get("requires_reference")) and not has_reference:
        message = "Upload the edited full starting frame for the selected video interval" if model.get("reference_image_role") == "edited-first-frame" else "Upload a reference character image"
        raise HTTPException(422, message)
    references = [asset for role, asset in assets.items() if role == "reference" or role.startswith("reference_")]
    if any(asset["kind"] != "image" for asset in references):
        raise HTTPException(422, "References must be images")
    if model.get("reference_must_match_source_dimensions") and source and references:
        if any((ref.get("width"), ref.get("height")) != (source.get("width"), source.get("height")) for ref in references):
            raise HTTPException(422, "The edited starting frame must match the source video's native width and height; no reference was resized or substituted.")
    if references and allows_restyle_first_frame(model, data):
        if data["reference_asset_ids"] or not source or source["kind"] != "video" or len(references) != 1:
            raise HTTPException(422, "Canny first-frame conditioning requires a source video and one edited full-frame image")
        if (references[0].get("width"), references[0].get("height")) != (source.get("width"), source.get("height")):
            raise HTTPException(422, "The edited starting frame must match the source video's native dimensions exactly")
    if references and effect["task"] not in model.get("reference_tasks", []) and not allows_restyle_first_frame(model, data):
        raise HTTPException(422, "This model/task does not support additional reference images")
    if len(references) + (bool(source) if image_task else 0) > reference_limit["max"]:
        message = "Too many reference images; the source image counts toward this model's limit" if image_task else "Too many reference images for this operation"
        raise HTTPException(422, message)
    if image_task and source and source["kind"] != "image":
        raise HTTPException(422, "Image operations require image inputs")
    if assets.get("mask") and assets["mask"]["kind"] not in {"image", "video"}:
        raise HTTPException(422, "A mask must be an image or video")
    if assets.get("mask") and model.get("mask_input_kinds") and assets["mask"]["kind"] not in model["mask_input_kinds"]:
        raise HTTPException(422, "This model accepts a painted first-frame mask, not a mask video")
    if effect["task"] == "text-to-speech":
        if assets:
            raise HTTPException(422, "Speech generation accepts a script and voice settings, not media inputs")
        if len(data["prompt"]) > model.get("max_script_characters", 2000):
            raise HTTPException(422, "The script exceeds the selected speech model's character limit; split it into shorter shots")
    if effect["task"] == "audio-transcription" and set(assets) != {"audio"}:
        raise HTTPException(422, "Soundtrack transcription accepts exactly one audio asset")
    if not effect["requires_mask"] and "mask" in assets and not preserving_image:
        raise HTTPException(422, "The selected operation does not use a mask")
    data["prompt"] = data["prompt"].strip() or effect.get("prompt", "")
    if effect.get("prompt_policy") == "empty" and data["prompt"]:
        raise HTTPException(422, "This operation does not accept a creative prompt; it processes the selected source")
    if not data["prompt"] and effect.get("prompt_policy", "required") == "required" and model.get("requires_prompt", True):
        raise HTTPException(422, "Describe the result you want to create")
    warnings = []
    if transition:
        warnings.append(f"The generated bridge is {data['frames']} frames at 24 fps ({data['frames'] / 24:.4f}s). Input images guide its endpoints; source videos are not looped to fill it.")
        if data["transition_include_inputs"]:
            warnings.append("Original input clips are fitted and resampled to the bridge canvas/FPS before concatenation; still images are not held as extra footage. Actual assembled duration is recorded after encoding.")
    if source_exact_task and source:
        factor = 2 if effect["task"] == "video-upscale" else 1
        final_width, final_height = source["width"] * factor, source["height"] * factor
        if (data["width"], data["height"]) != (final_width, final_height):
            warnings.append(f"Inference uses a padded {data['width']}×{data['height']} canvas; final output is cropped to {final_width}×{final_height} without an additional resize.")
    if model.get("supports_image_layout"):
        if model.get("supports_character_adapters"):
            from engine.flux3_character_workflows import validate_character_request as validate_flux3_request
        else:
            from engine.flux3_workflows import validate_flux3_request
        try:
            validate_flux3_request({**data, "task": effect["task"]})
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if data["image_layout"]:
            warnings.append("Layout boxes guide placement and scale; they are not hard pixel masks.")
        if expanding_image:
            warnings.append("The original stays at native size and is anchored during denoising. New surrounding pixels are generated, then original RGB and alpha are restored exactly. Review lighting and geometry at the joins.")
        elif preserving_image and source and data["image_edit_focus"] == "masked-region":
            warnings.append(region_focus_note(source["width"], source["height"]))
        elif preserving_image and source:
            warnings.append(f"Protected source pixels are composited back into the final {source['width']}×{source['height']} image; the generation canvas is padded to {data['width']}×{data['height']} then cropped.")
    elif data["image_layout"] or data["image_prompt_mode"] != "expand" or data["image_reference_megapixels"] != 1:
        raise HTTPException(422, "The selected model does not support these FLUX3 image controls")
    if assets.get("audio"):
        remaining = assets["audio"].get("duration", 0) - data["audio_start"]
        requested = data["audio_duration"] if effect["task"] == "audio-transcription" else data["frames"] / data["fps"]
        if remaining <= 0 or requested > remaining + .001:
            raise HTTPException(422, "The requested speech segment exceeds the uploaded recording. Reduce duration or audio start; audio is never silently looped.")
        if requested < remaining - .001:
            warnings.append(f"This render uses {requested:.2f} seconds of uploaded audio starting at {data['audio_start']:.2f}s.")
    if source and source["kind"] == "video" and source.get("duration") and not transition:
        requested = (data["context_frames"] if effect["task"] == "video-extend" else data["frames"]) / data["fps"]
        if effect["task"] == "frame-interpolation":
            requested = (data["input_frames"] or 97) / (data["input_fps"] or source.get("fps") or data["fps"])
        available = source["duration"] - data["trim_start"]
        tolerance = 1 / (source.get("fps") or data["fps"])
        if available <= 0 or requested > available + 0.001:
            raise HTTPException(422, f"This render requests {requested:.2f}s, but only {max(0, available):.2f}s remains in the source. Reduce duration or the start time; source frames are never silently repeated.")
        if requested < available - tolerance:
            method = "interpolated" if effect["task"] == "frame-interpolation" else "resampled"
            warnings.append(f"This render uses {requested:.2f} seconds starting at {data['trim_start']:.2f}s, {method} to {data['fps']:g} fps.")
        if effect["task"] == "video-extend":
            warnings.append(PREQUEL_CONTEXT_NOTE if data["extension_direction"] == "prequel" else SEQUEL_CONTEXT_NOTE)
    return data, warnings


def build_export(data: dict, store: Store) -> dict:
    from engine.workflows import build_workflow
    assets = {}
    for role, ident in request_asset_ids(data).items():
        asset = required_record(store, "assets", ident)
        assets[role] = Path(asset["path"]).name
    try:
        return build_workflow(data, assets)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def graph_response(graph: dict, filename: str):
    return Response(json.dumps(graph, indent=2), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })


app = create_app()
