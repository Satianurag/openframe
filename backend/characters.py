"""Private character datasets and host-bound adapter registry on the serial job queue."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from PIL import Image

from .apps import valid_asset_id
from .media import public_asset
from .store import now


class CharacterTraining(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)
    dataset_asset_ids: list[str] = Field(min_length=20, max_length=50)
    loss_mask_asset_ids: list[str] = Field(default_factory=list, max_length=50)
    trigger_token: str = Field(pattern=r"^[a-z][a-z0-9_]{3,31}$")
    steps: int = Field(default=1200, ge=500, le=3000)
    resolution: Literal[512, 768, 1024] = 1024
    rank: Literal[16, 32] = 32
    learning_rate: float = Field(default=0.0001, ge=0.00001, le=0.0002)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    provider: Literal["local"] = "local"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Give the character a name")
        return value.strip()

    @field_validator("dataset_asset_ids")
    @classmethod
    def valid_dataset(cls, values):
        for ident in values:
            valid_asset_id(ident)
        if len(set(values)) != len(values):
            raise ValueError("Training images must use distinct asset IDs")
        return values

    @field_validator("loss_mask_asset_ids")
    @classmethod
    def valid_masks(cls, values):
        for ident in values:
            valid_asset_id(ident)
        return values


class CharacterName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Give the character a name")
        return value.strip()


def character_get(store, ident):
    with store.connection() as db:
        row = db.execute("SELECT record FROM characters WHERE id=?", (ident,)).fetchone()
    if not row:
        raise HTTPException(404, "Trained character not found")
    record = json.loads(row[0])
    job = store.get("jobs", record["job_id"])
    record["status"] = "ready" if job and job["status"] == "succeeded" and record.get("adapter") else (job or {}).get("status", "unavailable")
    record["progress"] = (job or {}).get("progress", 0)
    record["stage"] = (job or {}).get("stage", "Training record unavailable")
    record["error"] = (job or {}).get("error")
    return record


def resolve_character(store, data, model, settings=None):
    # Caller-supplied paths and hashes are never authority, including when a
    # stored request is reused. Resolve the immutable registry ID every time.
    data.pop("_character_adapter", None)
    ident = data.get("character_adapter_id")
    if not ident:
        return
    if not model.get("supports_character_adapters") or model["id"] != "flux3-klein-base":
        raise HTTPException(422, "This trained adapter requires the matching undistilled FLUX3 Base profile; it cannot be applied to distilled checkpoints")
    record = character_get(store, ident)
    if record["status"] != "ready":
        raise HTTPException(409, "This character's training has not completed successfully")
    trained_provider = record.get("configuration", {}).get("provider", "")
    if data.get("provider") != trained_provider:
        raise HTTPException(422, "Use the same compute provider that holds this trained adapter; weights are not transferred between providers")
    if trained_provider == "local":
        from engine.training import training_host_id
        if not settings or record.get("metadata", {}).get("host_id") != training_host_id(settings):
            raise HTTPException(422, "Reconnect the Local ComfyUI endpoint used to train this adapter; it is not present on an arbitrary replacement host")
    data["_character_adapter"] = dict(record["adapter"])
    if trained_provider == "local":
        data["_character_adapter"]["host_id"] = record["metadata"]["host_id"]


def prepare_training(store, app_id, document_id, body, *, retry_of=None):
    from engine.provider_policy import require_provider_enabled
    try:
        require_provider_enabled(body.provider)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if app_id not in {"soul-id-cast", "ai-influencer"}:
        raise HTTPException(422, "Character training belongs to Soul ID / Cast or AI Influencer")
    with store.connection() as db:
        row = db.execute("SELECT record FROM app_documents WHERE id=? AND app_id=?", (document_id, app_id)).fetchone()
    if not row:
        raise HTTPException(404, "Character document not found")
    document = json.loads(row[0])
    if document["revision"] != body.expected_revision:
        raise HTTPException(409, "Save or reload the latest character document before training")
    if not set(body.dataset_asset_ids).issubset(document["asset_ids"]):
        raise HTTPException(422, "Attach every training image to the character document before starting")
    dataset, hashes, total, total_pixels = [], set(), 0, 0
    for ident in body.dataset_asset_ids:
        image = store.get("assets", ident)
        path = Path(image["path"]).resolve() if image else None
        if not image or image["kind"] != "image" or not path.is_relative_to(store.root) or not path.is_file():
            raise HTTPException(422, "Every dataset item must be an available image")
        with Image.open(path) as picture:
            if picture.format not in {"PNG", "JPEG", "WEBP"} or getattr(picture, "n_frames", 1) != 1:
                raise HTTPException(422, "Character training requires still PNG, JPEG or WebP images")
            if body.loss_mask_asset_ids and picture.getexif().get(274, 1) != 1:
                raise HTTPException(422, "Masked training photographs must be upright before masks are drawn")
        if min(image.get("width", 0), image.get("height", 0)) < 256 or path.stat().st_size > 32 * 1024**2:
            raise HTTPException(422, "Training images must be at least 256 pixels on each side and no larger than 32 MiB each")
        pixels = image["width"] * image["height"]
        total_pixels += pixels
        if pixels > 40_000_000 or total_pixels > 500_000_000:
            raise HTTPException(422, "Training images are limited to 40 megapixels each and 500 megapixels for the full dataset")
        hashes.add(image["sha256"])
        total += path.stat().st_size
        dataset.append(public_asset(image))
    if len(hashes) != len(dataset):
        raise HTTPException(422, "The dataset contains identical files; supply20–50 distinct images")
    if total > 512 * 1024**2:
        raise HTTPException(422, "The complete training dataset is limited to512MiB")
    if body.loss_mask_asset_ids:
        from engine.training_masks import validate_loss_mask
        if len(body.loss_mask_asset_ids) != len(dataset) or not set(body.loss_mask_asset_ids).issubset(document["asset_ids"]):
            raise HTTPException(422, "Attach one ordered head-loss mask for every training photograph")
        for ident, photo in zip(body.loss_mask_asset_ids, dataset):
            mask = store.get("assets", ident)
            path = Path(mask["path"]).resolve() if mask else None
            if not mask or mask["kind"] != "image" or not path.is_relative_to(store.root) or not path.is_file() or path.stat().st_size > 32 * 1024**2:
                raise HTTPException(422, "Every loss mask must be an available workspace PNG image")
            try:
                validate_loss_mask(path, (photo["width"], photo["height"]))
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
    from engine.training_models import BASE_SHA256, BASE_REVISION, DIFFUSERS_TRAINING_COMMIT
    ident, timestamp = uuid.uuid4().hex, now()
    request = body.model_dump(exclude={"expected_revision"})
    if not body.loss_mask_asset_ids:
        request.pop("loss_mask_asset_ids", None)
    request.update(job_id=ident, model_id="flux3-character-training", effect_id="train-identity", task="character-training")
    context = {"app_id": app_id, "document_id": document_id, "document_revision": document["revision"], "operation_id": "train-identity"}
    job = {"id": ident, "kind": "character-training", "status": "queued", "progress": 0, "stage": "Queued for character training",
           "created_at": timestamp, "updated_at": timestamp, "request": request, "outputs": [], "error": None,
           "favorite": False, "warnings": ["Training creates a compatible private adapter; resemblance must still be reviewed on generated images."],
           "cancel_requested": False, "app_context": context}
    if retry_of:
        job["retry_of"] = retry_of
    record = {"id": ident, "job_id": ident, "name": body.name.strip(), "created_at": timestamp, "updated_at": timestamp,
              "status": "queued", "model_id": "flux3-klein-base", "base_model_sha256": BASE_SHA256,
              "base_revision": BASE_REVISION, "trainer_commit": DIFFUSERS_TRAINING_COMMIT,
              "trigger_token": body.trigger_token, "dataset": dataset, "dataset_asset_ids": body.dataset_asset_ids,
              "configuration": request, "app_context": context, "adapter": None}
    if not record["name"]:
        raise HTTPException(422, "Give the character a name")
    association = {**context, "job_id": ident, "document_snapshot": document}
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (ident, "queued", timestamp, timestamp, json.dumps(job)))
        db.execute("INSERT INTO characters VALUES(?,?,?,?)", (ident, ident, timestamp, json.dumps(record)))
        db.execute("INSERT INTO app_job_links VALUES(?,?,?,?)", (ident, app_id, document_id, json.dumps(association)))
    return record, job


def retry_training(store, job):
    context = job["app_context"]
    with store.connection() as db:
        row = db.execute("SELECT revision FROM app_documents WHERE id=?", (context["document_id"],)).fetchone()
    if not row:
        raise HTTPException(409, "Restore or create the character document before retraining")
    fields = set(CharacterTraining.model_fields) - {"expected_revision"}
    body = CharacterTraining(**{key: value for key, value in job["request"].items() if key in fields}, expected_revision=row[0])
    return prepare_training(store, context["app_id"], context["document_id"], body, retry_of=job["id"])[1]


def execute_training(store, job, assets, output_dir, settings, on_progress, is_cancelled):
    from engine.training import train_character
    from engine.training_models import BASE_SHA256
    from engine.runner import JobCancelled

    def submitted(record):
        safe = {key: record[key] for key in ("provider", "call_id", "prompt_id", "job_id", "host_id") if key in record}
        if not store.update_job(job["id"], {"provider_submission": safe}):
            raise ValueError("The durable training job disappeared before remote submission was recorded")
        (output_dir / "provider-job.json").write_text(json.dumps(safe))

    result = train_character(job["request"], assets, settings, on_progress, is_cancelled, submitted)
    adapter = result.get("adapter", {})
    expected_name = f"openframe/{job['id']}/character.safetensors"
    if (adapter.get("model_id") != "flux3-klein-base" or adapter.get("base_model_sha256") != BASE_SHA256
            or adapter.get("lora_name") != expected_name or adapter.get("trigger_token") != job["request"]["trigger_token"]
            or not re.fullmatch(r"[a-f0-9]{64}", str(adapter.get("sha256", "")))
            or not 0 < int(adapter.get("size_bytes", 0)) <= 2 * 1024**3):
        raise ValueError("Training returned an invalid or incompatible adapter manifest; it was not registered")
    adapter = {key: adapter[key] for key in ("id", "name", "model_id", "base_model_sha256", "lora_name", "sha256", "size_bytes", "trigger_token", "rank", "steps", "format") if key in adapter}
    adapter["id"] = job["id"]
    manifest = {"job_id": job["id"], "request": job["request"], **result, "adapter": adapter}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        current = json.loads(db.execute("SELECT record FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])
        if is_cancelled() or current.get("cancel_requested"):
            raise JobCancelled("Character training cancelled; remote artifacts, if any, were not promoted")
        character = json.loads(db.execute("SELECT record FROM characters WHERE id=?", (job["id"],)).fetchone()[0])
        character.update(adapter=adapter, status="ready", updated_at=now(), metadata=result.get("metadata", {}))
        current.update(status="succeeded", progress=1, stage="Character adapter ready", updated_at=now(), error=None,
                       workflow=result.get("workflow"), metadata={**result.get("metadata", {}), "character_adapter": adapter}, character_id=job["id"])
        db.execute("UPDATE characters SET record=? WHERE id=?", (json.dumps(character), job["id"]))
        db.execute("UPDATE jobs SET status=?,updated_at=?,record=? WHERE id=?", ("succeeded", current["updated_at"], json.dumps(current), job["id"]))


def install_character_routes(app, public_job, settings):
    @app.post("/api/apps/{app_id}/documents/{document_id}/characters", status_code=201)
    def create(app_id: str, document_id: str, body: CharacterTraining):
        if body.provider == "local" and not settings().get("comfy_url"):
            raise HTTPException(422, "Configure the Linux CUDA ComfyUI training host before training")
        with app.state.store.lock:
            record, job = prepare_training(app.state.store, app_id, document_id, body)
        app.state.worker.wake.set()
        return {"character": record, "job": public_job(job)}

    @app.get("/api/characters")
    def listing(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        with app.state.store.connection() as db:
            rows = db.execute("SELECT id FROM characters ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            total = db.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        items = [character_get(app.state.store, row[0]) for row in rows]
        return {"items": items, "total": total, "offset": offset}

    @app.get("/api/characters/{ident}")
    def get(ident: str):
        return character_get(app.state.store, ident)

    @app.patch("/api/characters/{ident}")
    def rename(ident: str, body: CharacterName):
        with app.state.store.lock:
            record = character_get(app.state.store, ident)
            if not body.name.strip():
                raise HTTPException(422, "Give the character a name")
            record.update(name=body.name.strip(), updated_at=now())
            with app.state.store.connection() as db:
                db.execute("UPDATE characters SET record=? WHERE id=?", (json.dumps(record), ident))
        return record

    @app.delete("/api/characters/{ident}")
    def remove(ident: str):
        with app.state.store.lock:
            record = character_get(app.state.store, ident)
            if record["status"] in {"queued", "running"}:
                raise HTTPException(409, "Cancel or finish training before removing its registry record")
            with app.state.store.connection() as db:
                if db.execute("SELECT 1 FROM jobs WHERE json_extract(record,'$.request.character_adapter_id')=? LIMIT 1", (ident,)).fetchone():
                    raise HTTPException(409, "Saved generations refer to this adapter; delete those generations before removing its registry record")
                db.execute("DELETE FROM characters WHERE id=?", (ident,))
        return {"deleted": ident, "remote_adapter_retained": True, "training_job_retained": True}

    @app.get("/api/characters/{ident}/manifest")
    def manifest(ident: str):
        record = character_get(app.state.store, ident)
        return Response(json.dumps(record, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="character-{ident}.json"'})
