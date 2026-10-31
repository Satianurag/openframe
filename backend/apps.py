"""Separate app documents and explicit links to unchanged render jobs."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import RenderRequest
from .store import now

# Leaf operations require a real engine effect; planner/sequence operations use dedicated handlers.
APPS = [
    ("content-factory", "Content Factory", ["plan-shots", "generate-series", "generate-speech", "claude-export"]),
    ("supercomputer", "Supercomputer", ["plan-shots", "render-sequence", "agent-run"]),
    ("cinema-studio", "Cinema Studio", ["text-to-video", "reference-to-video", "image-to-video", "create-image", "edit-image", "plan-shots", "render-sequence", "extend-video"]),
    ("ai-influencer", "AI Influencer", ["create-image", "edit-image", "motion-transfer", "character-replacement", "replace-object", "train-identity"]),
    ("marketing-ads", "Marketing / Ads", ["create-image", "edit-image", "product-reveal", "restyle", "remove-background", "generate-speech", "render-sequence", "link-to-ad", "recreate-ad"]),
    ("canvas", "Canvas", ["create-image", "edit-image", "text-to-video", "image-to-video", "generate-speech", "speak", "remove-background", "remove-object", "replace-object", "restyle", "motion-transfer", "character-replacement", "execute-board"]),
    ("soul-image", "Soul photos", ["create-image", "edit-image", "identity-photos", "photodump"]),
    ("soul-id-cast", "Soul ID / Cast", ["create-image", "edit-image", "train-identity", "generate-character-sheet"]),
    ("popcorn", "Popcorn", ["create-image", "edit-image", "image-to-video", "plan-shots", "render-sequence", "generate-storyboard"]),
    ("speak", "Speak", ["speak", "generate-speech"]),
    ("katana", "Katana", ["restyle", "motion-transfer", "character-replacement", "recreate-edit"]),
    ("genjutsu", "Genjutsu", ["edit-image", "motion-transfer", "character-replacement", "replace-object", "remove-object", "restyle"]),
    ("mini-apps", "Mini-apps", ["relight-image", "render-sequence", "speak", "motion-transfer", "character-replacement", "cinematic", "image-to-video", "dissolve", "slow-motion", "product-reveal", "remove-object", "replace-object", "restyle", "weather", "create-image", "edit-image", "expand-image", "decompose-image", "face-swap", "remove-background", "generate-speech", "trim-video", "video-reframe", "transition-video", "fps-boost", "video-depth", "video-outpaint", "video-extend", "video-upscale", "alpha-matte", "semantic-matte", "clean-plate", "sdr-to-hdr"]),
]
SECRET_KEYS = {"password", "authorization", "api_key", "access_token", "refresh_token", "token", "secret", "comfy_api_key", "comfy_cloud_api_key", "credentials", "credential", "provider_settings"}


def app_definition(app_id: str):
    item = next((item for item in APPS if item[0] == app_id), None)
    if not item:
        raise HTTPException(404, "Unknown app")
    return item


def app_catalog():
    from engine.catalog import get_catalog, reference_limits
    catalog = get_catalog()
    effects = {effect["id"]: effect for effect in catalog["effects"]}
    models = {model["id"]: model for model in catalog["models"]}
    result = []
    for ident, name, operations in APPS:
        entries = []
        for operation in operations:
            if operation == "train-identity" and ident in {"soul-id-cast", "ai-influencer"}:
                entries.append({"id": operation, "label": "Train character", "available": True,
                    "reason": "Train a private adapter from20–50 photos on a configured Linux CUDA ComfyUI host; matching undistilled Base inference on the same host. Output resemblance still requires review.",
                    "execution": "character-training", "effect_ids": [], "model_ids": ["flux3-klein-base"]})
                continue
            if operation in {"plan-shots", "generate-series", "render-sequence"}:
                entries.append({"id": operation, "label": "Plan shots" if operation == "plan-shots" else "Render reviewed sequence",
                    "available": True, "reason": "Billboard only: one preparation image followed by its dependent video, with durable resume and no duplicate completed stage." if ident == "mini-apps" else ("Explicit editable proposal; no renders until reviewed." if operation == "plan-shots" else "Render an explicitly reviewed, ordered shot plan and assemble only complete episodes."),
                    "execution": "planner" if operation == "plan-shots" else "sequence", "effect_ids": [], "model_ids": ["qwen3.8-planner"] if operation == "plan-shots" else []})
                continue
            effect = effects.get(operation)
            entry = {"id": operation, "label": effect["name"] if effect else operation.replace("-", " ").title(),
                     "available": effect is not None,
                     "reason": "Implemented; select and check a compatible compute provider." if effect else "This operation has no implemented generation handler. Your draft can be saved; no substitute render will be submitted.",
                     "effect_ids": [operation] if effect else [], "model_ids": effect["model_ids"] if effect else []}
            if effect:
                limits = {model_id: reference_limits(models.get(model_id), effect) for model_id in effect["model_ids"] if model_id in models}
                entry["min_references"] = min((item["min"] for item in limits.values()), default=0)
                entry["max_references"] = max((item["max"] for item in limits.values()), default=0)
                entry["reference_limits_by_model"] = limits
            entries.append(entry)
        result.append({"id": ident, "name": name, "operations": entries})
    return {"items": result}


def valid_asset_id(value: str):
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Use an asset ID returned by the upload endpoint")
    return value


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled", min_length=1, max_length=160)
    schema_version: int = Field(default=1, ge=1, le=1)
    state: dict[str, Any] = Field(default_factory=dict)
    asset_ids: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Give this document a title")
        return value.strip()

    @field_validator("asset_ids")
    @classmethod
    def clean_assets(cls, value):
        return list(dict.fromkeys(valid_asset_id(item) for item in value))


class DocumentUpdate(DocumentCreate):
    expected_revision: int = Field(ge=1)


class AppRender(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    operation: str = Field(min_length=1, max_length=100)
    request: RenderRequest | None = None
    step_id: str | None = Field(default=None, max_length=100)
    group_id: str | None = Field(default=None, max_length=100)


class StoryboardShot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(min_length=1, max_length=100)
    request: RenderRequest


class StoryboardSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    submission_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    shots: list[StoryboardShot] = Field(min_length=1, max_length=8)


def validate_state(app_id, state, asset_ids):
    state = deepcopy(state)
    seen = 0
    def visit(value, depth=0):
        nonlocal seen
        seen += 1
        if depth > 12 or seen > 10000:
            raise HTTPException(422, "The saved document is too complex")
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                if len(key) > 100 or normalized in SECRET_KEYS or normalized.endswith(("_api_key", "_token", "_password", "_secret", "_path")) or normalized == "path":
                    raise HTTPException(422, "Store only app inputs in documents; credentials and filesystem paths belong outside app state")
                if normalized == "asset_id" or normalized.endswith("_asset_id"):
                    if item and item not in asset_ids:
                        raise HTTPException(422, "Every referenced asset must appear in asset_ids")
                if normalized == "asset_ids" or normalized.endswith("_asset_ids"):
                    if not isinstance(item, list) or any(ident not in asset_ids for ident in item):
                        raise HTTPException(422, "Every referenced asset must appear in asset_ids")
                    if normalized == "reference_asset_ids" and (len(item) > 50 or len(set(item)) != len(item)):
                        raise HTTPException(422, "A project may store at most 50 distinct reference images; each job sends only its active subset")
                visit(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, str) and (len(value) > 16000 or value.startswith(("data:", "file://"))):
            raise HTTPException(422, "Upload media separately and store its asset ID; text fields are limited to 16000 characters")
    visit(state)
    try:
        if len(json.dumps(state, allow_nan=False).encode()) > 256 * 1024:
            raise HTTPException(413, "A saved document is limited to 256 KiB")
    except (TypeError, ValueError):
        raise HTTPException(422, "App state must contain finite JSON values")
    if app_id == "content-factory":
        defaults = {"prompt": "", "length": 30, "episodes": 1, "mode": "local", "tab": "explore", "reference_url": None,
                    "reference_asset_id": None, "attachment_asset_ids": [], "style_id": None}
        if set(state) - set(defaults):
            raise HTTPException(422, "Unknown Content Factory field")
        state = defaults | state
        if not isinstance(state["prompt"], str) or type(state["length"]) is not int or not 15 <= state["length"] <= 300 or state["length"] % 5:
            raise HTTPException(422, "Content Factory needs text and a length from 15 to 300 seconds in 5-second increments")
        if type(state["episodes"]) is not int or state["episodes"] not in range(1, 5) or not isinstance(state["mode"], str) or state["mode"] not in {"local", "claude"} or not isinstance(state["tab"], str) or state["tab"] not in {"explore", "generations"}:
            raise HTTPException(422, "Choose 1–4 episodes and a supported Content Factory mode/tab")
        for key in ("reference_asset_id", "style_id", "reference_url"):
            if state[key] is not None and not isinstance(state[key], str):
                raise HTTPException(422, f"{key} must be text or null")
        url = state["reference_url"]
        if url:
            parsed = urlparse(url)
            if len(url) > 4096 or parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
                raise HTTPException(422, "Use an HTTP(S) reference link without embedded credentials")
    return state


def install_app_routes(app, prepare_job, public_job):
    def get_document(db, app_id, ident):
        row = db.execute("SELECT record FROM app_documents WHERE id=? AND app_id=?", (ident, app_id)).fetchone()
        if not row:
            raise HTTPException(404, "App document not found")
        return json.loads(row[0])

    def check_assets(db, ids):
        for ident in ids:
            row = db.execute("SELECT record FROM assets WHERE id=?", (ident,)).fetchone()
            if not row:
                raise HTTPException(422, "An attached asset no longer exists")

    def save_project_link(db, app_id, document_id, state):
        target = state.get("project_id") if app_id == "supercomputer" else None
        if target:
            if not isinstance(target, str) or target == document_id:
                raise HTTPException(422, "Choose another saved Supercomputer project")
            row = db.execute("SELECT record FROM app_documents WHERE id=? AND app_id=?", (target, app_id)).fetchone()
            if not row or json.loads(row[0])["state"].get("kind") != "project":
                raise HTTPException(422, "The selected Supercomputer project does not exist")
        db.execute("DELETE FROM app_document_links WHERE document_id=?", (document_id,))
        if target:
            db.execute("INSERT INTO app_document_links VALUES (?,?)", (document_id, target))

    @app.get("/api/apps")
    def list_apps():
        return app_catalog()

    @app.get("/api/apps/{app_id}/documents")
    def list_documents(app_id: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        app_definition(app_id)
        with app.state.store.connection() as db:
            items = db.execute("SELECT record FROM app_documents WHERE app_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (app_id, limit, offset)).fetchall()
            total = db.execute("SELECT COUNT(*) FROM app_documents WHERE app_id=?", (app_id,)).fetchone()[0]
        return {"items": [json.loads(item[0]) for item in items], "total": total, "offset": offset}

    @app.post("/api/apps/{app_id}/documents", status_code=201)
    def create_document(app_id: str, body: DocumentCreate):
        app_definition(app_id)
        data = body.model_dump()
        data["state"] = validate_state(app_id, data["state"], data["asset_ids"])
        timestamp = now()
        record = {**data, "id": uuid.uuid4().hex, "app_id": app_id, "revision": 1, "created_at": timestamp, "updated_at": timestamp}
        with app.state.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            check_assets(db, data["asset_ids"])
            db.execute("INSERT INTO app_documents VALUES (?,?,?,?,?)", (record["id"], app_id, 1, timestamp, json.dumps(record)))
            db.executemany("INSERT INTO app_document_assets VALUES (?,?)", [(record["id"], ident) for ident in data["asset_ids"]])
            save_project_link(db, app_id, record["id"], record["state"])
        return record

    @app.get("/api/apps/{app_id}/documents/{document_id}")
    def read_document(app_id: str, document_id: str):
        app_definition(app_id)
        with app.state.store.connection() as db:
            return get_document(db, app_id, document_id)

    @app.patch("/api/apps/{app_id}/documents/{document_id}")
    def update_document(app_id: str, document_id: str, body: DocumentUpdate):
        app_definition(app_id)
        # PATCH is partial; omitted state/assets/title retain their existing values.
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        with app.state.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = get_document(db, app_id, document_id)
            if previous["revision"] != body.expected_revision:
                raise HTTPException(409, "This document changed in another tab. Reload it before saving or submitting.")
            record = previous | changes
            record["state"] = validate_state(app_id, record["state"], record["asset_ids"])
            check_assets(db, record["asset_ids"])
            if all(record[key] == previous[key] for key in ("state", "title", "schema_version", "asset_ids")):
                return previous
            record.update(revision=previous["revision"] + 1, updated_at=now())
            db.execute("UPDATE app_documents SET revision=?,updated_at=?,record=? WHERE id=?", (record["revision"], record["updated_at"], json.dumps(record), document_id))
            db.execute("DELETE FROM app_document_assets WHERE document_id=?", (document_id,))
            db.executemany("INSERT INTO app_document_assets VALUES (?,?)", [(document_id, ident) for ident in record["asset_ids"]])
            save_project_link(db, app_id, document_id, record["state"])
        return record

    @app.delete("/api/apps/{app_id}/documents/{document_id}")
    def delete_document(app_id: str, document_id: str, expected_revision: int = Query(ge=1)):
        app_definition(app_id)
        with app.state.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            record = get_document(db, app_id, document_id)
            if record["revision"] != expected_revision:
                raise HTTPException(409, "This document changed. Reload before deleting it.")
            if any(db.execute(f"SELECT 1 FROM {table} WHERE document_id=? AND status IN ('queued','running') LIMIT 1", (document_id,)).fetchone() for table in ("sequences", "sequence_plans")):
                raise HTTPException(409, "Cancel active planning or sequence execution before deleting this document")
            if db.execute("SELECT 1 FROM app_document_links WHERE target_id=? LIMIT 1", (document_id,)).fetchone():
                raise HTTPException(409, "Move or unlink the chats in this project before deleting it")
            db.execute("DELETE FROM app_document_links WHERE document_id=?", (document_id,))
            db.execute("DELETE FROM app_documents WHERE id=?", (document_id,))
            db.execute("DELETE FROM app_document_assets WHERE document_id=?", (document_id,))
        return {"deleted": document_id, "jobs_retained": True, "media_retained": True}

    @app.get("/api/apps/{app_id}/jobs")
    def list_app_jobs(
        app_id: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
        document_id: str | None = None,
        operation: str | None = Query(None, min_length=1, max_length=100),
        preset_id: str | None = Query(None, min_length=1, max_length=100),
    ):
        app_definition(app_id)
        clause = "a.app_id=?" + (" AND a.document_id=?" if document_id else "")
        params = [app_id] + ([document_id] if document_id else [])
        if operation:
            clause += " AND json_extract(a.record, '$.operation')=?"
            params.append(operation)
        if preset_id:
            clause += " AND (json_extract(a.record, '$.step_id')=? OR json_extract(a.record, '$.document_snapshot.state.preset_id')=?)"
            params.extend([preset_id, preset_id])
        with app.state.store.connection() as db:
            rows = db.execute(f"SELECT j.record FROM jobs j JOIN app_job_links a ON a.job_id=j.id WHERE {clause} ORDER BY j.created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
            total = db.execute(f"SELECT COUNT(*) FROM jobs j JOIN app_job_links a ON a.job_id=j.id WHERE {clause}", params).fetchone()[0]
        return {"items": [public_job(json.loads(row[0])) for row in rows], "total": total, "offset": offset}

    @app.get("/api/apps/popcorn/documents/{document_id}/storyboards/{submission_id}")
    def storyboard_submission(document_id: str, submission_id: str):
        with app.state.store.connection() as db:
            get_document(db, "popcorn", document_id)
            rows = db.execute("SELECT j.record FROM jobs j JOIN app_job_links a ON a.job_id=j.id WHERE a.app_id='popcorn' AND a.document_id=? AND json_extract(a.record,'$.group_id')=? ORDER BY j.created_at", (document_id, submission_id)).fetchall()
        if not rows:
            raise HTTPException(404, "This storyboard submission has not been stored")
        latest, attempts = {}, {}
        for row in rows:
            job = json.loads(row[0])
            scene = job.get("app_context", {}).get("step_id") or job["id"]
            latest[scene] = job
            attempts.setdefault(scene, []).append(job["id"])
        return {"id": submission_id, "items": [public_job(job) for job in latest.values()], "attempt_job_ids": attempts}

    @app.post("/api/apps/popcorn/documents/{document_id}/storyboards", status_code=201)
    def submit_storyboard(document_id: str, body: StoryboardSubmission):
        # Validate the whole reviewed board before making any leaf visible to the worker.
        fingerprint = hashlib.sha256(json.dumps([shot.model_dump() for shot in body.shots], sort_keys=True).encode()).hexdigest()
        if len({shot.step_id for shot in body.shots}) != len(body.shots):
            raise HTTPException(422, "Each storyboard scene must have a distinct ID")
        with app.state.store.lock, app.state.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            document = get_document(db, "popcorn", document_id)
            previous = db.execute("SELECT record FROM app_job_links WHERE app_id='popcorn' AND document_id=? AND json_extract(record,'$.group_id')=?", (document_id, body.submission_id)).fetchall()
            if previous:
                if any(json.loads(row[0]).get("submission_sha256") != fingerprint for row in previous):
                    raise HTTPException(409, "This submission ID already belongs to a different storyboard")
                jobs = [app.state.store.get("jobs", json.loads(row[0])["job_id"]) for row in previous]
                return {"id": body.submission_id, "items": [public_job(job) for job in jobs]}
            if document["revision"] != body.expected_revision:
                raise HTTPException(409, "Save or reload the current storyboard before submitting")
            jobs = []
            for shot in body.shots:
                if shot.request.effect_id not in {"create-image", "edit-image"} or shot.request.batch_size != 1:
                    raise HTTPException(422, "A storyboard scene must request exactly one image")
                job = prepare_job(shot.request)
                requested = [value for key, value in job["request"].items() if key.endswith("_asset_id") and value]
                requested += job["request"].get("reference_asset_ids", [])
                if any(ident not in document["asset_ids"] for ident in requested):
                    raise HTTPException(422, "Attach every storyboard reference before submitting")
                context = {"app_id": "popcorn", "document_id": document_id, "document_revision": document["revision"],
                           "operation": shot.request.effect_id, "step_id": shot.step_id, "group_id": body.submission_id}
                job["app_context"] = context
                jobs.append(job)
            for job in jobs:
                association = job["app_context"] | {"job_id": job["id"], "document_snapshot": document, "submission_sha256": fingerprint}
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job["id"], job["status"], job["created_at"], job["updated_at"], json.dumps(job)))
                db.execute("INSERT INTO app_job_links VALUES (?,?,?,?)", (job["id"], "popcorn", document_id, json.dumps(association)))
        app.state.worker.wake.set()
        return {"id": body.submission_id, "items": [public_job(job) for job in jobs]}

    @app.post("/api/apps/{app_id}/documents/{document_id}/jobs", status_code=201)
    def submit_app_job(app_id: str, document_id: str, body: AppRender):
        definition = app_definition(app_id)
        if body.operation not in definition[2]:
            raise HTTPException(422, "This operation does not belong to the selected app")
        operation = next(item for item in app_catalog()["items"] if item["id"] == app_id)
        capability = next(item for item in operation["operations"] if item["id"] == body.operation)
        if not capability["available"]:
            raise HTTPException(409, capability["reason"])
        if capability.get("execution") in {"planner", "sequence"}:
            raise HTTPException(409, "This operation uses the saved planning/sequence endpoints, not a single render request")
        if body.request is None:
            raise HTTPException(422, "Provide a render request for this implemented operation")
        if body.request.effect_id not in capability["effect_ids"]:
            raise HTTPException(422, "The render effect must match the selected operation; substitution is not allowed")
        with app.state.store.lock:
            job = prepare_job(body.request)
            with app.state.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                document = get_document(db, app_id, document_id)
                if document["revision"] != body.expected_revision:
                    raise HTTPException(409, "Save or reload the current document before submitting it")
                requested = [value for key, value in job["request"].items() if key.endswith("_asset_id") and value]
                requested += job["request"].get("reference_asset_ids", [])
                if any(ident not in document["asset_ids"] for ident in requested):
                    raise HTTPException(422, "Attach all render inputs to this document and save it before submitting")
                context = {"app_id": app_id, "document_id": document_id, "document_revision": document["revision"],
                           "operation": body.operation, "step_id": body.step_id, "group_id": body.group_id}
                job["app_context"] = context
                association = context | {"job_id": job["id"], "document_snapshot": document}
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job["id"], job["status"], job["created_at"], job["updated_at"], json.dumps(job)))
                db.execute("INSERT INTO app_job_links VALUES (?,?,?,?)", (job["id"], app_id, document_id, json.dumps(association)))
        app.state.worker.wake.set()
        return public_job(job)

    @app.get("/api/jobs/{job_id}/app-context")
    def job_app_context(job_id: str):
        with app.state.store.connection() as db:
            row = db.execute("SELECT record FROM app_job_links WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise HTTPException(404, "This render has no app document association")
            return json.loads(row[0])
