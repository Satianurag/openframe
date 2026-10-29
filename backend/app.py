"""OpenFrame local HTTP API. Run one worker: uvicorn backend.app:app --host 127.0.0.1."""
from __future__ import annotations

import importlib.util
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
from .models import JobUpdate, PresetCreate, RenderRequest, SettingsUpdate
from .store import Store, now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
SECRET_FIELDS = {"comfy_api_key", "comfy_cloud_api_key"}
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
DEFAULTS = {
    "default_provider": "local", "comfy_url": "http://127.0.0.1:8188",
    "comfy_cloud_url": "https://cloud.comfy.org", "comfy_api_key": "", "comfy_cloud_api_key": "",
    "comfy_cli_path": "",
    "modal_app": "openframe-comfy", "modal_environment": "main", "modal_function": "render",
    "modal_volume": "openframe-assets", "modal_progress_dict": "openframe-progress",
}


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        root = Path(data_dir or os.environ.get("OPENFRAME_DATA_DIR", PROJECT_ROOT / ".openframe"))
        if not root.is_absolute():
            root = PROJECT_ROOT / root
        app.state.store = Store(root)
        app.state.provider_checks = {}
        app.state.worker = JobWorker(app.state.store, lambda: settings(app.state.store))
        app.state.worker.start()
        yield
        app.state.worker.stop()

    app = FastAPI(title="OpenFrame Studio", version="0.1.0", lifespan=lifespan)
    origins = [origin.strip().rstrip("/") for origin in os.environ.get(
        "OPENFRAME_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
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
        return {"items": [public_asset(item) for item in app.state.store.list("assets", limit, offset)],
                "total": app.state.store.count("assets"), "offset": offset}

    @app.get("/api/assets/{asset_id}")
    def get_asset(asset_id: str):
        return public_asset(required_record(app.state.store, "assets", asset_id))

    @app.get("/api/assets/{asset_id}/file")
    def asset_file(asset_id: str, download: bool = False):
        asset = required_record(app.state.store, "assets", asset_id)
        path = checked_media_path(app.state.store, asset["path"])
        return FileResponse(path, media_type=asset.get("mime_type"), filename=asset["name"],
                            content_disposition_type="attachment" if download else "inline")

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
                raise HTTPException(409, "This asset is used by a saved render. Delete the referencing render before deleting its media.")
            for key in ("path", "thumbnail_path"):
                if asset.get(key):
                    path = Path(asset[key]).resolve()
                    if path.is_relative_to(app.state.store.root):
                        path.unlink(missing_ok=True)
            app.state.store.delete("assets", asset_id)
        return {"deleted": asset_id}

    @app.post("/api/jobs", status_code=201)
    def create_job(request: RenderRequest):
        data, warnings = validate_request(request, app.state.store)
        if not provider_configured(data["provider"], settings(app.state.store)):
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
        return create_job(RenderRequest.model_validate(job["request"]))

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
            graph = job.get("workflow") or build_export(job["request"], app.state.store)
        return graph_response(graph, f"openframe-{job_id}-{format}.json")

    @app.get("/api/jobs/{job_id}/bundle")
    def job_bundle(job_id: str, include_media: bool = False):
        job = required_record(app.state.store, "jobs", job_id)
        graph = job.get("workflow") or build_export(job["request"], app.state.store)
        try:
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
        for key in ("source_asset_id", "mask_asset_id", "reference_asset_id"):
            data[key] = None
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
    result.update(store.read_settings())
    return result


def provider_configured(provider: str, current: dict) -> bool:
    if provider == "local":
        return bool(current.get("comfy_url"))
    if provider == "comfy-cloud":
        from engine.cloud import auth_status
        return bool(current.get("comfy_cloud_url") and auth_status(current)["mode"] != "missing")
    if provider == "modal":
        return bool(current.get("modal_app") and importlib.util.find_spec("modal"))
    return False


def redact(message: str, current: dict) -> str:
    for key in SECRET_FIELDS:
        if current.get(key):
            message = message.replace(current[key], "[redacted]")
    if os.environ.get("COMFY_API_KEY"):
        message = message.replace(os.environ["COMFY_API_KEY"], "[redacted]")
    return message[:2000]


def public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key not in {"workflow", "ui_workflow", "cancel_requested"}}


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
    from engine.catalog import get_catalog
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
    for field in ("frames", "fps", "steps", "guidance"):
        if field not in request.model_fields_set:
            data[field] = model.get("default_" + field, data[field])
    if "provider" not in request.model_fields_set:
        data["provider"] = settings(store)["default_provider"]
    if data["provider"] not in {item["id"] for item in catalog["providers"]}:
        raise HTTPException(422, "Select a supported compute provider")
    if data["model_id"] not in effect["model_ids"] or effect["task"] not in model["tasks"]:
        raise HTTPException(422, "This model does not support the selected effect")
    for axis in ("width", "height"):
        value = data[axis]
        if value < model.get(f"min_{axis}", 64) or value > model.get(f"max_{axis}", 4096):
            raise HTTPException(422, f"{axis.capitalize()} must be between {model[f'min_{axis}']} and {model[f'max_{axis}']} for {model['name']}")
        multiple = model.get("dimension_multiple", 1)
        if value % multiple:
            raise HTTPException(422, f"{model['name']} requires {axis} to be a multiple of {multiple}")
    if data["frames"] > model["max_frames"] or (data["frames"] - 1) % model["frame_multiple"]:
        raise HTTPException(422, f"{model['name']} requires 1 + multiples of {model['frame_multiple']} frames, up to {model['max_frames']}")
    assets = {}
    for role in ("source", "mask", "reference"):
        ident = data.get(role + "_asset_id")
        if ident:
            assets[role] = required_record(store, "assets", ident)
            checked_media_path(store, assets[role]["path"])
    source = assets.get("source")
    if require_assets and effect["requires_video"] and (not source or source["kind"] != "video"):
        raise HTTPException(422, "Upload a source video for this effect")
    if require_assets and effect["requires_image"] and (not source or source["kind"] != "image"):
        raise HTTPException(422, "Upload a source image for this effect")
    if require_assets and effect["requires_mask"] and "mask" not in assets:
        raise HTTPException(422, "Paint or upload a mask for this effect")
    if assets.get("reference") and assets["reference"]["kind"] != "image":
        raise HTTPException(422, "The reference must be an image")
    if assets.get("reference") and not model.get("supports_reference", False):
        raise HTTPException(422, "This model does not support an additional reference image; use the source image for image animation")
    data["prompt"] = data["prompt"].strip() or effect.get("prompt", "")
    if not data["prompt"]:
        raise HTTPException(422, "Describe the result you want to create")
    warnings = []
    if source and source["kind"] == "video" and source.get("duration"):
        requested = data["frames"] / data["fps"]
        available = source["duration"] - data["trim_start"]
        tolerance = 1 / (source.get("fps") or data["fps"])
        if available <= 0 or requested > available + 0.001:
            raise HTTPException(422, f"This render requests {requested:.2f}s, but only {max(0, available):.2f}s remains in the source. Reduce duration or the start time; source frames are never silently repeated.")
        if requested < available - tolerance:
            warnings.append(f"This render uses {requested:.2f} seconds starting at {data['trim_start']:.2f}s, resampled to {data['fps']:g} fps.")
    return data, warnings


def build_export(data: dict, store: Store) -> dict:
    from engine.workflows import build_workflow
    assets = {}
    for role in ("source", "mask", "reference"):
        ident = data.get(role + "_asset_id")
        if ident:
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
