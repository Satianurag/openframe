"""Explicit, bounded shot sequences using the existing serial render worker."""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .apps import app_definition, valid_asset_id
from .media import frame_bytes, public_asset, register_asset, inspect_media
from .models import RenderRequest, request_asset_ids
from .store import now
from .sequence_audio import NarrationInput, CaptionsInput, CaptionUpdate, NarrationUpdate, EpisodeAudioUpdate, validate_cues, cues_from_words, caption_text, mix_audio, caption_ffmpeg, finalize_streaming_wav

SUPPORTED_APPS = {"content-factory", "supercomputer", "popcorn", "cinema-studio", "marketing-ads", "mini-apps"}
TERMINAL = {"failed", "cancelled", "succeeded"}


class ShotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    label: str = Field(default="Shot", max_length=160)
    request: RenderRequest
    preparation_only: bool = False
    source_from_previous: bool = False
    existing_video_asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    narration: NarrationInput = Field(default_factory=NarrationInput)


class EpisodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Episode", max_length=160)
    target_duration: float = Field(default=30, ge=1, le=300)
    shots: list[ShotInput] = Field(min_length=1, max_length=64)
    audio_asset_id: str | None = None
    audio_start: float = Field(default=0, ge=0, le=86400)
    pad_audio_silence: bool = False
    audio_provider: Literal["local"] | None = None
    keep_shot_audio: bool = False
    transition: Literal["cut", "fade", "dissolve", "wipeleft", "wiperight", "slideleft", "slideright"] = "cut"
    transition_frames: int = Field(default=12, ge=1, le=240)
    encoding_quality: Literal["standard", "high"] = "high"
    background_audio_asset_id: str | None = None
    background_audio_start: float = Field(default=0, ge=0, le=86400)
    background_gain: float = Field(default=.15, ge=0, le=2)
    duck_background: bool = True
    narration_gain: float = Field(default=1, ge=0, le=2)
    shot_audio_gain: float = Field(default=1, ge=0, le=2)
    captions: CaptionsInput = Field(default_factory=CaptionsInput)


class SequenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    episodes: list[EpisodeInput] = Field(min_length=1, max_length=4)
    planner_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class SequenceUpdate(SequenceInput):
    expected_sequence_revision: int = Field(ge=1)


class SequenceApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class PlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    prompt: str = Field(min_length=1, max_length=3000)
    style: str = Field(default="", max_length=200)
    target_duration: int = Field(default=30, ge=15, le=300)
    episodes: int = Field(default=1, ge=1, le=4)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    provider: Literal["local"] = "local"
    model_id: Literal["qwen3.8-planner", "qwen-planner-7b", "qwen-planner"] | None = None
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=4)
    reference_notes: str = Field(default="", max_length=3000)


def transition_overlap(episode, frame_counts):
    """A transition consumes explicitly reviewed overlap, never extra generated shots."""
    if episode.get("transition", "cut") == "cut" or len(frame_counts) < 2:
        return 0
    overlap = episode.get("transition_frames", 12)
    for index, count in enumerate(frame_counts):
        sides = 1 if index in (0, len(frame_counts) - 1) else 2
        if count <= overlap * sides:
            raise ValueError("The transition overlaps an entire shot. Reduce transition frames or lengthen that shot.")
    return overlap


def record_get(store, table, ident):
    if table not in {"sequences", "sequence_plans"}:
        raise ValueError("Unknown sequence table")
    with store.connection() as db:
        row = db.execute(f"SELECT record FROM {table} WHERE id=?", (ident,)).fetchone()
    if not row:
        raise HTTPException(404, "Sequence or plan not found")
    return json.loads(row[0])


def record_save(store, table, record, *, reset_cancel=False):
    if table not in {"sequences", "sequence_plans"}:
        raise ValueError("Unknown sequence table")
    record["updated_at"] = now()
    with store.connection() as db:
        previous = db.execute(f"SELECT record FROM {table} WHERE id=?", (record["id"],)).fetchone()
        if previous and not reset_cancel and json.loads(previous[0]).get("cancel_requested"):
            record["cancel_requested"] = True
            if record["status"] == "succeeded":
                record.update(status="cancelled", stage="Cancelled; any completed outputs are retained")
        db.execute(f"UPDATE {table} SET status=?,updated_at=?,record=? WHERE id=?", (record["status"], record["updated_at"], json.dumps(record), record["id"]))


def asset(store, ident, kind=None):
    value = store.get("assets", ident)
    if not value or (kind and value["kind"] != kind):
        raise ValueError(f"An input is missing or is not {kind or 'readable media'}")
    path = Path(value["path"]).resolve()
    if not path.is_relative_to(store.root) or not path.is_file():
        raise ValueError("An input media file is no longer available")
    return value


def sequence_view(store, record):
    result = deepcopy(record)
    result.pop("document_snapshot", None)
    with store.connection() as db:
        rows = db.execute("SELECT episode_index,record FROM sequence_shots WHERE sequence_id=? ORDER BY episode_index,position", (record["id"],)).fetchall()
    complete = progress = 0
    for episode in result["episodes"]:
        episode["shots"] = []
    for row in rows:
        shot = json.loads(row[1])
        if shot.get("job_id"):
            job = store.get("jobs", shot["job_id"])
            if job:
                shot["job_status"] = job["status"]
                shot["progress"] = job["progress"]
                shot["stage"] = job["stage"]
        if shot.get("narration_job_id"):
            narration_job = store.get("jobs", shot["narration_job_id"])
            if narration_job:
                if shot.get("narration_status") != "failed":
                    shot["narration_status"] = narration_job["status"]
                shot["narration_progress"] = narration_job["progress"]
                shot["narration_stage"] = narration_job["stage"]
                shot["narration_error"] = shot.get("narration_error") or narration_job.get("error")
        complete += shot["status"] == "succeeded"
        progress += 1 if shot["status"] == "succeeded" else shot.get("progress", 0)
        result["episodes"][row[0]]["shots"].append(shot)
    result["completed_shots"] = complete
    result["total_shots"] = len(rows)
    result["progress"] = 1 if record["status"] == "succeeded" else min(.95, progress / max(1, len(rows)) * .95)
    return result


def install_sequence_routes(app, prepare_job):
    def document(app_id, ident, revision):
        app_definition(app_id)
        if app_id not in SUPPORTED_APPS:
            raise HTTPException(422, "This app has no sequence/planning operation")
        with app.state.store.connection() as db:
            row = db.execute("SELECT record FROM app_documents WHERE id=? AND app_id=?", (ident, app_id)).fetchone()
        if not row:
            raise HTTPException(404, "App document not found")
        value = json.loads(row[0])
        if value["revision"] != revision:
            raise HTTPException(409, "Save or reload the latest document before continuing")
        if value["state"].get("reference_url"):
            raise HTTPException(422, "Social/product link analysis is not implemented. Clear the reference link or replace it with uploaded media and an explicit shot plan; the URL will not be silently ignored.")
        return value

    def insert(table, value):
        with app.state.store.connection() as db:
            db.execute(f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?)", (value["id"], value["app_id"], value["document_id"], value["status"], value["created_at"], value["updated_at"], json.dumps(value)))

    @app.get("/api/planner")
    def planner_status():
        from engine.planner import planner_status
        return planner_status(app.state.worker.settings())

    @app.post("/api/apps/{app_id}/documents/{document_id}/plans", status_code=201)
    def create_plan(app_id: str, document_id: str, body: PlannerInput):
        if app_id in {"marketing-ads", "mini-apps"}:
            raise HTTPException(422, "This app uses an explicit reviewed stage plan, not an automatic sequence planner")
        from engine.planner import normalize_plan_request
        with app.state.store.lock:
            snapshot = document(app_id, document_id, body.expected_revision)
            try:
                request = normalize_plan_request(body.model_dump(exclude={"expected_revision"}))
                from engine.provider_policy import require_provider_enabled
                require_provider_enabled(request["provider"])
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            for ident in request["reference_asset_ids"]:
                asset = app.state.store.get("assets", ident)
                if ident not in snapshot["asset_ids"] or not asset or asset["kind"] not in {"image", "video"}:
                    raise HTTPException(422, "Planning references must be image/video assets in the saved document")
                if asset["kind"] == "video" and float(asset.get("duration") or 0) > 300:
                    raise HTTPException(422, "Trim reference videos to at most five minutes before analysis")
            timestamp = now()
            value = {"id": uuid.uuid4().hex, "app_id": app_id, "document_id": document_id, "document_revision": snapshot["revision"],
                     "status": "queued", "stage": "Queued for CUDA visual planning" if request["model_id"] == "qwen3.8-planner" else "Queued for legacy CPU text planning", "progress": 0, "request": request, "proposal": None,
                     "error": None, "cancel_requested": False, "created_at": timestamp, "updated_at": timestamp}
            insert("sequence_plans", value)
        app.state.worker.wake.set()
        return value

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str):
        return record_get(app.state.store, "sequence_plans", plan_id)

    @app.post("/api/plans/{plan_id}/cancel")
    def cancel_plan(plan_id: str):
        with app.state.store.lock:
            record = record_get(app.state.store, "sequence_plans", plan_id)
            if record["status"] not in TERMINAL:
                record.update(cancel_requested=True, stage="Cancellation requested")
                if record["status"] == "queued":
                    record.update(status="cancelled", stage="Cancelled before planning")
                record_save(app.state.store, "sequence_plans", record)
        return record

    def save_sequence(app_id: str, document_id: str, body: SequenceInput, replace_id=None, expected_sequence_revision=None):
        from engine.catalog import effect_by_id
        store = app.state.store
        with store.lock:
            snapshot = document(app_id, document_id, body.expected_revision)
            if app_id == "content-factory" and (len(body.episodes) != snapshot["state"]["episodes"] or any(episode.target_duration != snapshot["state"]["length"] for episode in body.episodes)):
                raise HTTPException(422, "Save the intended episode count and target length in Content Factory first")
            if len(body.model_dump_json().encode()) > 1024 * 1024:
                raise HTTPException(413, "The explicit sequence plan is limited to 1 MiB")
            planner = record_get(store, "sequence_plans", body.planner_id) if body.planner_id else None
            if planner and (planner["app_id"] != app_id or planner["document_id"] != document_id or planner["status"] != "succeeded"):
                raise HTTPException(422, "Use a completed proposal belonging to this app document")
            timestamp = now()
            record = {"id": replace_id or uuid.uuid4().hex, "revision": 1, "app_id": app_id, "document_id": document_id, "document_revision": snapshot["revision"],
                      "document_snapshot": snapshot, "planner_id": body.planner_id,
                      "planner_provenance": planner["proposal"].get("metadata") if planner else None, "status": "draft", "stage": "Review shots, then explicitly start rendering", "episodes": [],
                      "error": None, "cancel_requested": False, "created_at": timestamp, "updated_at": timestamp}
            if app_id == "mini-apps":
                if snapshot["state"].get("preset_id") != "billboard" or len(body.episodes) != 1 or len(body.episodes[0].shots) != 2:
                    raise HTTPException(422, "Mini-app sequences currently support only Billboard composition followed by its video")
                if not replace_id:
                    with store.connection() as db:
                        unfinished = db.execute("SELECT id FROM sequences WHERE app_id=? AND document_id=? AND status!='succeeded' LIMIT 1", (app_id, document_id)).fetchone()
                    if unfinished:
                        raise HTTPException(409, "This Billboard already has an incomplete sequence. Resume it or explicitly delete its inactive draft before creating another.")
                first, second = body.episodes[0].shots
                if not first.preparation_only or second.preparation_only or not second.source_from_previous or body.episodes[0].transition != "cut":
                    raise HTTPException(422, "Billboard requires one preparation image followed by one image-to-video stage, without a transition")
                if (first.request.width, first.request.height) != (second.request.width, second.request.height):
                    raise HTTPException(422, "Billboard preparation and video must use the same explicit canvas dimensions")
            elif any(shot.preparation_only for episode in body.episodes for shot in episode.shots):
                raise HTTPException(422, "Preparation-only image stages are currently scoped to Billboard")
            shot_rows = []
            seen = set()
            for index, episode in enumerate(body.episodes):
                if episode.captions.mode == "soundtrack" or any(shot.narration.text.strip() for shot in episode.shots):
                    from engine.provider_policy import require_provider_enabled
                    try:
                        require_provider_enabled(episode.audio_provider or "local")
                    except ValueError as exc:
                        raise HTTPException(422, str(exc)) from exc
                if episode.audio_asset_id and any(shot.narration.text.strip() for shot in episode.shots):
                    raise HTTPException(422, "Choose an explicit foreground soundtrack or per-shot narration; background music has its own separate field")
                if episode.captions.mode == "soundtrack" and not episode.audio_asset_id:
                    raise HTTPException(422, "Soundtrack captions require an explicit foreground soundtrack")
                if episode.audio_asset_id and episode.keep_shot_audio:
                    raise HTTPException(422, "Choose an explicit soundtrack or per-shot audio, not both")
                if episode.audio_asset_id:
                    try:
                        valid_asset_id(episode.audio_asset_id)
                        soundtrack = asset(store, episode.audio_asset_id, "audio")
                    except ValueError as exc:
                        raise HTTPException(422, str(exc)) from exc
                    if episode.audio_asset_id not in snapshot["asset_ids"]:
                        raise HTTPException(422, "Attach the soundtrack to the document before creating a sequence")
                    if episode.audio_start >= soundtrack["duration"]:
                        raise HTTPException(422, "The foreground recording must start before its end")
                background = None
                if episode.background_audio_asset_id:
                    try:
                        valid_asset_id(episode.background_audio_asset_id)
                        background = asset(store, episode.background_audio_asset_id, "audio")
                    except ValueError as exc:
                        raise HTTPException(422, str(exc)) from exc
                    if episode.background_audio_asset_id not in snapshot["asset_ids"]:
                        raise HTTPException(422, "Attach the background audio to the document first")
                duration, dimensions = 0, None
                for position, shot in enumerate(episode.shots):
                    if shot.id in seen:
                        raise HTTPException(422, "Every shot ID must be unique in the sequence")
                    seen.add(shot.id)
                    effect = effect_by_id(shot.request.effect_id)
                    if shot.preparation_only:
                        if not effect or effect["id"] not in {"create-image", "edit-image"} or shot.request.batch_size != 1 or shot.source_from_previous or shot.existing_video_asset_id or shot.narration.text.strip():
                            raise HTTPException(422, "A Billboard preparation stage must produce one image, without narration or an existing-video input")
                    elif not effect or effect.get("output_kind", "video") != "video":
                        raise HTTPException(422, "Every timeline shot must use an implemented video operation")
                    if shot.source_from_previous and (position == 0 or effect["task"] != "image-to-video" or shot.request.source_asset_id):
                        raise HTTPException(422, "Previous-frame continuation requires an image-to-video operation after another shot, without a separate source image")
                    request = prepare_job(shot.request, require_assets=not shot.source_from_previous, check_provider=False)["request"]
                    if any(ident not in snapshot["asset_ids"] for ident in request_asset_ids(request).values()):
                        raise HTTPException(422, "Attach every shot input to the saved document before creating the sequence")
                    existing = None
                    if shot.existing_video_asset_id:
                        existing = store.get("assets", shot.existing_video_asset_id)
                        if shot.existing_video_asset_id not in snapshot["asset_ids"] or not existing or existing["kind"] != "video":
                            raise HTTPException(422, "Attach the existing video before adding it to an assembly")
                        if shot.source_from_previous or request["model_id"] != "video-tools" or request["effect_id"] != "trim-video" or request.get("source_asset_id") != existing["id"] or request.get("trim_start", 0) != 0:
                            raise HTTPException(422, "Existing-video assembly uses the complete selected video, without a generation or trim request")
                        if not existing.get("frame_count") or (request["width"], request["height"], request["frames"]) != (existing["width"], existing["height"], existing["frame_count"]) or abs(request["fps"] - existing["fps"]) > 1e-6:
                            raise HTTPException(422, "Existing-video assembly must retain the exact native dimensions, frame count and FPS")
                        if not Path(existing["path"]).is_file():
                            raise HTTPException(422, "The selected existing video is unavailable")
                    if episode.keep_shot_audio and not shot.preparation_only:
                        from engine.catalog import model_by_id
                        model = model_by_id(request["model_id"])
                        source = store.get("assets", request.get("source_asset_id")) if request.get("source_asset_id") else None
                        audio_expected = (model.get("supports_audio") and request.get("generate_audio")) or request.get("audio_asset_id") or (source and source["kind"] == "video" and source.get("has_audio") and request.get("preserve_audio"))
                        if not audio_expected:
                            raise HTTPException(422, "Per-shot audio was selected but a shot has no configured audio source. Enable supported native audio, choose a soundtrack, or select no audio before rendering.")
                    shape = (request["width"], request["height"], request["fps"])
                    if not shot.preparation_only:
                        if dimensions is not None and shape != dimensions:
                            raise HTTPException(422, "Shots within an episode must use the same width, height and FPS; no implicit crop or retiming is applied")
                        dimensions = shape
                        duration += request["frames"] / request["fps"]
                    if shot.narration.text.strip():
                        if shot.narration.start >= request["frames"] / request["fps"]:
                            raise HTTPException(422, "Narration must start inside its shot")
                        from engine.narration_workflows import normalize_narration
                        try:
                            normalize_narration({"model_id": "ming-narration", "provider": episode.audio_provider or "local", "voice": shot.narration.voice, "caption_language": shot.narration.language, "speech_speed": shot.narration.speed})
                        except ValueError as exc:
                            raise HTTPException(422, str(exc)) from exc
                    shot_rows.append((index, position, {"id": shot.id, "label": shot.label, "request": request,
                        "existing_video_asset_id": shot.existing_video_asset_id,
                        "existing_video_provenance": {"source_job_id": existing.get("source_job_id"), "sha256": existing["sha256"], "execution": "reuse-existing-video; no render submitted"} if existing else None,
                        "preparation_only": shot.preparation_only, "source_from_previous": shot.source_from_previous, "status": "pending", "job_id": None, "attempt_job_ids": [],
                        "narration": shot.narration.model_dump(), "narration_job_id": None, "narration_status": "pending" if shot.narration.text.strip() else "none", "narration_attempt_job_ids": [],
                        "error": None, "output_asset_id": None, "actual_duration": None}))
                    if existing:
                        shot_rows[-1][2].update(status="succeeded", output_asset_id=existing["id"], actual_duration=existing["duration"])
                if app_id == "mini-apps" and tuple(shot_rows[0][2]["request"][key] for key in ("width", "height")) != dimensions[:2]:
                    raise HTTPException(422, "The normalized Billboard image and video canvases differ; select matching explicit dimensions")
                try:
                    overlap = transition_overlap(episode.model_dump(), [row[2]["request"]["frames"] for row in shot_rows if row[0] == index and not row[2].get("preparation_only")])
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                duration -= overlap * (sum(not shot.preparation_only for shot in episode.shots) - 1) / dimensions[2]
                if duration > 300.001:
                    raise HTTPException(422, "The actual frame-aligned shot plan exceeds 300 seconds for an episode. Edit the shots explicitly; nothing is silently trimmed.")
                if dimensions[0] * dimensions[1] * len(episode.shots) * 16 > 2 * 1024**3:
                    raise HTTPException(422, "This episode exceeds the bounded assembly memory estimate. Reduce shot count or resolution.")
                if episode.audio_asset_id and soundtrack["duration"] - episode.audio_start < duration - .001 and not episode.pad_audio_silence:
                    raise HTTPException(422, "The explicit soundtrack does not cover the planned episode duration")
                if background and background["duration"] - episode.background_audio_start < duration - .001:
                    raise HTTPException(422, "Background audio does not cover the planned episode; it is never silently looped")
                try:
                    validate_cues([cue.model_dump() for cue in episode.captions.cues], duration)
                    if episode.captions.burn_in:
                        caption_ffmpeg()
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                record["episodes"].append({"id": f"episode-{index+1}", "title": episode.title, "target_duration": episode.target_duration,
                    "planned_duration": duration, "actual_duration": None, "audio_asset_id": episode.audio_asset_id,
                    "audio_start": episode.audio_start, "keep_shot_audio": episode.keep_shot_audio,
                    "transition": episode.transition, "transition_frames": episode.transition_frames,
                    "encoding_quality": episode.encoding_quality, "status": "pending", "output": None})
                record["episodes"][-1].update(episode.model_dump(exclude={"shots", "title", "target_duration"}))
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                if replace_id:
                    previous = record_get(store, "sequences", replace_id)
                    if previous["status"] != "draft" or previous["revision"] != expected_sequence_revision:
                        raise HTTPException(409, "Only the latest unstarted draft can be edited")
                    if previous["app_id"] != app_id or previous["document_id"] != document_id:
                        raise HTTPException(422, "A draft cannot move to a different app document")
                    record.update(revision=previous["revision"] + 1, created_at=previous["created_at"])
                    for table in ("sequence_shots", "sequence_assets"):
                        db.execute(f"DELETE FROM {table} WHERE sequence_id=?", (replace_id,))
                    db.execute("DELETE FROM sequences WHERE id=?", (replace_id,))
                db.execute("INSERT INTO sequences VALUES (?,?,?,?,?,?,?)", (record["id"], app_id, document_id, "draft", record["created_at"], timestamp, json.dumps(record)))
                db.executemany("INSERT INTO sequence_shots VALUES (?,?,?,?)", [(record["id"], ep, pos, json.dumps(shot)) for ep, pos, shot in shot_rows])
                db.executemany("INSERT INTO sequence_assets VALUES (?,?)", [(record["id"], ident) for ident in snapshot["asset_ids"]])
        return sequence_view(store, record)

    @app.post("/api/apps/{app_id}/documents/{document_id}/sequences", status_code=201)
    def create_sequence(app_id: str, document_id: str, body: SequenceInput):
        return save_sequence(app_id, document_id, body)

    @app.patch("/api/sequences/{sequence_id}")
    def update_sequence(sequence_id: str, body: SequenceUpdate):
        previous = record_get(app.state.store, "sequences", sequence_id)
        plan = SequenceInput.model_validate(body.model_dump(exclude={"expected_sequence_revision"}))
        return save_sequence(previous["app_id"], previous["document_id"], plan, sequence_id, body.expected_sequence_revision)

    @app.get("/api/apps/{app_id}/plans")
    def list_plans(app_id: str, document_id: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        app_definition(app_id)
        clause = "app_id=?" + (" AND document_id=?" if document_id else "")
        args = [app_id] + ([document_id] if document_id else [])
        with app.state.store.connection() as db:
            rows = db.execute(f"SELECT record FROM sequence_plans WHERE {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
            total = db.execute(f"SELECT COUNT(*) FROM sequence_plans WHERE {clause}", args).fetchone()[0]
        return {"items": [json.loads(row[0]) for row in rows], "total": total, "offset": offset}

    @app.get("/api/apps/{app_id}/sequences")
    def list_sequences(app_id: str, document_id: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        app_definition(app_id)
        clause = "app_id=?" + (" AND document_id=?" if document_id else "")
        args = [app_id] + ([document_id] if document_id else [])
        with app.state.store.connection() as db:
            rows = db.execute(f"SELECT record FROM sequences WHERE {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
            total = db.execute(f"SELECT COUNT(*) FROM sequences WHERE {clause}", args).fetchone()[0]
        return {"items": [sequence_view(app.state.store, json.loads(row[0])) for row in rows], "total": total, "offset": offset}

    @app.get("/api/sequences/{sequence_id}")
    def get_sequence(sequence_id: str):
        return sequence_view(app.state.store, record_get(app.state.store, "sequences", sequence_id))

    def editable_episode(sequence_id, episode_index, revision):
        record = record_get(app.state.store, "sequences", sequence_id)
        if record["revision"] != revision:
            raise HTTPException(409, "Reload the latest sequence before saving this correction")
        if record["status"] in {"queued", "running", "draft"}:
            raise HTTPException(409, "Use the draft editor before starting, or wait for active work to stop before correcting completed work")
        if not 0 <= episode_index < len(record["episodes"]):
            raise HTTPException(404, "Episode not found")
        with app.state.store.connection() as db:
            if db.execute("SELECT 1 FROM jobs JOIN sequence_job_links ON jobs.id=sequence_job_links.job_id WHERE sequence_id=? AND jobs.status IN ('queued','running') LIMIT 1", (sequence_id,)).fetchone():
                raise HTTPException(409, "Wait for the sequence's active child jobs to finish cancelling")
        return record, record["episodes"][episode_index]

    def invalidate_assembly(episode):
        if episode.get("output"):
            episode["previous_outputs"] = (episode.get("previous_outputs", []) + [episode["output"]])[-20:]
        episode.update(status="pending", output=None)

    @app.patch("/api/sequences/{sequence_id}/episodes/{episode_index}/shots/{shot_index}/narration")
    def correct_narration(sequence_id: str, episode_index: int, shot_index: int, body: NarrationUpdate):
        store = app.state.store
        with store.lock:
            record, episode = editable_episode(sequence_id, episode_index, body.expected_revision)
            with store.connection() as db:
                row = db.execute("SELECT record FROM sequence_shots WHERE sequence_id=? AND episode_index=? AND position=?", (sequence_id, episode_index, shot_index)).fetchone()
            if not row:
                raise HTTPException(404, "Shot not found")
            shot = json.loads(row[0])
            narration = body.narration.model_dump()
            if shot.get("preparation_only") and narration["text"].strip():
                raise HTTPException(422, "Preparation images have no timeline duration; attach narration to the video stage")
            if narration["text"].strip():
                if episode.get("audio_asset_id"):
                    raise HTTPException(422, "A foreground soundtrack and per-shot narration cannot be combined")
                if narration["start"] >= (shot.get("actual_duration") or shot["request"]["frames"] / shot["request"]["fps"]):
                    raise HTTPException(422, "Narration starts beyond this shot's duration")
                from engine.narration_workflows import normalize_narration
                try:
                    normalize_narration({"model_id": "ming-narration", "provider": episode.get("audio_provider") or "local", "voice": narration["voice"], "caption_language": narration["language"], "speech_speed": narration["speed"]})
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
            shot.update(narration=narration, narration_job_id=None, narration_status="pending" if narration["text"].strip() else "none",
                        narration_output_asset_id=None, narration_output=None, narration_actual_duration=None, narration_error=None, narration_metadata=None)
            with store.connection() as db:
                db.execute("UPDATE sequence_shots SET record=? WHERE sequence_id=? AND episode_index=? AND position=?", (json.dumps(shot), sequence_id, episode_index, shot_index))
            if episode.get("captions", {}).get("mode") == "narration":
                episode["captions"]["cues"] = []
            invalidate_assembly(episode)
            record.update(revision=record["revision"] + 1, status="failed", stage="Narration changed; resume missing work. Completed video shots are retained.", error=None, cancel_requested=False)
            record_save(store, "sequences", record, reset_cancel=True)
        return sequence_view(store, record)

    @app.patch("/api/sequences/{sequence_id}/episodes/{episode_index}/audio")
    def correct_audio(sequence_id: str, episode_index: int, body: EpisodeAudioUpdate):
        store = app.state.store
        with store.lock:
            record, episode = editable_episode(sequence_id, episode_index, body.expected_revision)
            changes = body.model_dump(exclude_unset=True, exclude={"expected_revision", "expected_document_revision", "reassemble"})
            updated = {**episode, **changes}
            with store.connection() as db:
                shots = [json.loads(row[0]) for row in db.execute("SELECT record FROM sequence_shots WHERE sequence_id=? AND episode_index=?", (sequence_id, episode_index))]
                all_shots = [json.loads(row[0]) for row in db.execute("SELECT record FROM sequence_shots WHERE sequence_id=?", (sequence_id,))]
            if body.reassemble and any(shot["status"] != "succeeded" or (shot.get("narration", {}).get("text", "").strip() and shot.get("narration_status") != "succeeded") for shot in all_shots):
                raise HTTPException(409, "Complete missing video and narration before rebuilding the episode")
            if updated.get("audio_asset_id") and (updated.get("keep_shot_audio") or any(shot.get("narration", {}).get("text", "").strip() for shot in shots)):
                raise HTTPException(422, "Choose a foreground soundtrack or shot audio/narration; background audio is separate")
            if updated.get("captions", {}).get("mode") == "soundtrack" and not updated.get("audio_asset_id"):
                raise HTTPException(422, "Change soundtrack captions to manual or none before removing their recording")
            if updated.get("keep_shot_audio"):
                for shot in shots:
                    media = store.get("assets", shot.get("output_asset_id")) if shot.get("output_asset_id") else None
                    request = shot["request"]
                    source = store.get("assets", request.get("source_asset_id")) if request.get("source_asset_id") else None
                    configured = request.get("audio_asset_id") or request.get("generate_audio") or (source and source.get("has_audio") and request.get("preserve_audio"))
                    if (media and not media.get("has_audio")) or (not media and not configured):
                        raise HTTPException(422, "A shot has no audio; choose a separate soundtrack/background or leave shot audio off")
            selected = [value for value in (updated.get("audio_asset_id"), updated.get("background_audio_asset_id")) if value]
            previous = {value for value in (episode.get("audio_asset_id"), episode.get("background_audio_asset_id")) if value}
            new_ids = set(selected) - previous
            snapshot = None
            if new_ids or body.expected_document_revision is not None:
                if body.expected_document_revision is None:
                    raise HTTPException(409, "Attach the replacement recording and send the latest document revision")
                snapshot = document(record["app_id"], record["document_id"], body.expected_document_revision)
                if not new_ids.issubset(snapshot["asset_ids"]):
                    raise HTTPException(422, "Attach replacement audio to the saved app document first")
            duration = episode.get("actual_duration") or episode["planned_duration"]
            for key, start_key in (("audio_asset_id", "audio_start"), ("background_audio_asset_id", "background_audio_start")):
                if updated.get(key):
                    try:
                        recording = asset(store, updated[key], "audio")
                    except ValueError as exc:
                        raise HTTPException(422, str(exc)) from exc
                    available = recording["duration"] - updated.get(start_key, 0)
                    if available <= 0 or (available < duration - .001 and not (key == "audio_asset_id" and updated.get("pad_audio_silence"))):
                        raise HTTPException(422, "The selected recording does not cover the episode; audio is never silently looped")
            foreground_changed = any(updated.get(key) != episode.get(key) for key in ("audio_asset_id", "audio_start"))
            episode.update(changes)
            if foreground_changed:
                episode.pop("transcription", None)
                episode["transcription_job_id"] = None
                if episode.get("captions", {}).get("mode") == "soundtrack":
                    episode["captions"]["cues"] = []
            if snapshot:
                record.update(document_snapshot=snapshot, document_revision=snapshot["revision"])
            invalidate_assembly(episode)
            record.update(revision=record["revision"] + 1, status="queued" if body.reassemble else "failed",
                          stage="Queued to rebuild episode audio from completed media" if body.reassemble else "Audio changed; resume assembly. Completed videos and speech are retained.",
                          error=None, cancel_requested=False, updated_at=now())
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE sequences SET status=?,updated_at=?,record=? WHERE id=?", (record["status"], record["updated_at"], json.dumps(record), sequence_id))
                db.executemany("INSERT OR IGNORE INTO sequence_assets VALUES (?,?)", [(sequence_id, ident) for ident in selected])
        if body.reassemble:
            app.state.worker.wake.set()
        return sequence_view(store, record)

    @app.patch("/api/sequences/{sequence_id}/episodes/{episode_index}/captions")
    def correct_captions(sequence_id: str, episode_index: int, body: CaptionUpdate):
        store = app.state.store
        with store.lock:
            record, episode = editable_episode(sequence_id, episode_index, body.expected_revision)
            cues = [cue.model_dump() for cue in body.cues]
            try:
                validate_cues(cues, episode.get("actual_duration") or episode["planned_duration"])
                if body.burn_in:
                    caption_ffmpeg()
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            if body.reassemble:
                with store.connection() as db:
                    shots = [json.loads(row[0]) for row in db.execute("SELECT record FROM sequence_shots WHERE sequence_id=?", (sequence_id,))]
                if any(shot["status"] != "succeeded" or (shot.get("narration", {}).get("text", "").strip() and shot.get("narration_status") != "succeeded") for shot in shots):
                    raise HTTPException(409, "Resume and complete missing shot/narration work before caption-only reassembly")
            episode["captions"] = {**episode.get("captions", {}), "mode": "manual", "cues": cues, "burn_in": body.burn_in}
            episode["captions_edited"] = True
            invalidate_assembly(episode)
            record.update(revision=record["revision"] + 1, status="queued" if body.reassemble else "failed",
                          stage="Queued for caption-only reassembly" if body.reassemble else "Captions changed; resume assembly from completed media",
                          error=None, cancel_requested=False)
            record_save(store, "sequences", record, reset_cancel=True)
        if body.reassemble:
            app.state.worker.wake.set()
        return sequence_view(store, record)

    @app.get("/api/sequences/{sequence_id}/episodes/{episode_index}/captions.{fmt}")
    def export_captions(sequence_id: str, episode_index: int, fmt: Literal["srt", "vtt"]):
        record = record_get(app.state.store, "sequences", sequence_id)
        if not 0 <= episode_index < len(record["episodes"]):
            raise HTTPException(404, "Episode not found")
        episode = record["episodes"][episode_index]
        cues = episode.get("captions", {}).get("cues", [])
        return Response(caption_text(cues, fmt), media_type="application/x-subrip" if fmt == "srt" else "text/vtt",
                        headers={"Content-Disposition": f'attachment; filename="episode-{episode_index + 1}.{fmt}"'})

    @app.post("/api/sequences/{sequence_id}/{action}")
    def sequence_action(sequence_id: str, action: Literal["start", "cancel", "resume", "retry"], approval: SequenceApproval | None = None):
        store = app.state.store
        with store.lock:
            record = record_get(store, "sequences", sequence_id)
            if action == "cancel":
                if record["status"] not in TERMINAL:
                    record.update(cancel_requested=True, stage="Cancellation requested")
                    if record["status"] in {"draft", "queued"}:
                        record.update(status="cancelled", stage="Cancelled before execution")
                    record_save(store, "sequences", record)
                    with store.connection() as db:
                        rows = db.execute("SELECT record FROM sequence_shots WHERE sequence_id=?", (sequence_id,)).fetchall()
                    for row in rows:
                        shot = json.loads(row[0])
                        if shot.get("job_id"):
                            app.state.worker.cancel(shot["job_id"])
                        if shot.get("narration_job_id"):
                            app.state.worker.cancel(shot["narration_job_id"])
                    for episode in record["episodes"]:
                        if episode.get("transcription_job_id"):
                            app.state.worker.cancel(episode["transcription_job_id"])
            else:
                if action == "start" and (approval is None or approval.expected_revision != record["revision"]):
                    raise HTTPException(409, "Review the latest saved plan and submit its expected_revision before starting")
                allowed = {"draft"} if action == "start" else {"failed", "cancelled"}
                if record["status"] not in allowed:
                    raise HTTPException(409, "This sequence cannot be started/resumed from its current state")
                with store.connection() as db:
                    rows = db.execute("SELECT episode_index,position,record FROM sequence_shots WHERE sequence_id=?", (sequence_id,)).fetchall()
                    for row in rows:
                        shot = json.loads(row[2])
                        job = store.get("jobs", shot["job_id"]) if shot.get("job_id") else None
                        if job and job["status"] in {"queued", "running"}:
                            raise HTTPException(409, "The previous shot is still active. Wait for cancellation to finish before resuming.")
                        speech_job = store.get("jobs", shot["narration_job_id"]) if shot.get("narration_job_id") else None
                        if speech_job and speech_job["status"] in {"queued", "running"}:
                            raise HTTPException(409, "Wait for active narration cancellation before resuming")
                        if speech_job and speech_job["status"] in {"failed", "cancelled"}:
                            shot.update(narration_job_id=None, narration_status="pending", narration_error=None)
                        if shot["status"] == "failed" or (shot["status"] != "succeeded" and (not job or job["status"] != "succeeded")):
                            shot.update(status="pending", job_id=None, error=None)
                        db.execute("UPDATE sequence_shots SET record=? WHERE sequence_id=? AND episode_index=? AND position=?", (json.dumps(shot), sequence_id, row[0], row[1]))
                for episode in record["episodes"]:
                    caption_job = store.get("jobs", episode["transcription_job_id"]) if episode.get("transcription_job_id") else None
                    if caption_job and caption_job["status"] in {"queued", "running"}:
                        raise HTTPException(409, "Wait for active soundtrack transcription cancellation before resuming")
                    if caption_job and caption_job["status"] in {"failed", "cancelled"}:
                        episode["transcription_job_id"] = None
                record.update(status="queued", stage="Queued for explicit shot execution", cancel_requested=False, error=None)
                record_save(store, "sequences", record, reset_cancel=True)
        app.state.worker.wake.set()
        return sequence_view(store, record)

    @app.delete("/api/sequences/{sequence_id}")
    def delete_sequence(sequence_id: str):
        store = app.state.store
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            record = record_get(store, "sequences", sequence_id)
            if record["status"] not in TERMINAL | {"draft"}:
                raise HTTPException(409, "Cancel the sequence before deleting it")
            for table in ("sequence_shots", "sequence_assets", "sequence_job_links", "sequences"):
                field = "id" if table == "sequences" else "sequence_id"
                db.execute(f"DELETE FROM {table} WHERE {field}=?", (sequence_id,))
        return {"deleted": sequence_id, "jobs_retained": True, "media_retained": True}


class SequenceDriver:
    def __init__(self, store, prepare_job, settings, cancel_job, stopping):
        self.store, self.prepare_job, self.settings = store, prepare_job, settings
        self.cancel_job, self.stopping = cancel_job, stopping

    def cancelled(self, table, ident):
        return self.stopping() or record_get(self.store, table, ident).get("cancel_requested", False)

    def save_shot(self, sequence_id, episode_index, position, shot):
        with self.store.connection() as db:
            db.execute("UPDATE sequence_shots SET record=? WHERE sequence_id=? AND episode_index=? AND position=?", (json.dumps(shot), sequence_id, episode_index, position))

    def advance(self):
        # Sequence bookkeeping can append a child behind existing FIFO jobs.
        # Planner inference still waits for the render queue to drain.
        with self.store.connection() as db:
            queued = db.execute("SELECT 1 FROM jobs WHERE status='queued' LIMIT 1").fetchone()
            plan = None if queued else db.execute("SELECT record FROM sequence_plans WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            sequence = db.execute("SELECT record FROM sequences WHERE status IN ('queued','running') ORDER BY created_at LIMIT 1").fetchone()
        if plan and (not sequence or json.loads(plan[0])["created_at"] < json.loads(sequence[0])["created_at"]):
            with self.store.lock:
                selected = record_get(self.store, "sequence_plans", json.loads(plan[0])["id"])
                if selected["status"] != "queued" or selected.get("cancel_requested"):
                    return
                selected.update(status="running", stage="Preparing selected planner")
                record_save(self.store, "sequence_plans", selected)
            self.run_plan(selected)
            return True
        elif sequence:
            self.advance_sequence(json.loads(sequence[0]))
            return True
        return False

    def run_plan(self, record):
        from engine.planner import plan_video
        ident = record["id"]
        last_write = 0.0
        def progress(value, stage):
            nonlocal last_write
            if time.monotonic() - last_write < 1:
                return
            last_write = time.monotonic()
            current = record_get(self.store, "sequence_plans", ident)
            current.update(progress=min(.99, max(0, value)), stage=str(stage)[:300])
            record_save(self.store, "sequence_plans", current)
        def submitted(info):
            current = record_get(self.store, "sequence_plans", ident)
            current["provider_job"] = info
            record_save(self.store, "sequence_plans", current)
        try:
            if self.cancelled("sequence_plans", ident):
                raise ValueError("Planning cancelled before submission")
            references = []
            for asset_id in record["request"].get("reference_asset_ids", []):
                asset = self.store.get("assets", asset_id)
                if not asset or not Path(asset["path"]).is_file():
                    raise ValueError("A selected planning reference is no longer available")
                references.append({"asset_id": asset_id, "kind": asset["kind"], "path": asset["path"]})
            result = plan_video(record["request"], self.settings(), progress, lambda: self.cancelled("sequence_plans", ident), submitted, references=references)
            current = record_get(self.store, "sequence_plans", ident)
            if self.cancelled("sequence_plans", ident):
                current.update(status="cancelled", stage="Planning cancelled")
            else:
                result.setdefault("metadata", {})["review_policy"] = "A proposal requiring explicit review; no shots have been rendered."
                current.update(status="succeeded", progress=1, stage="Editable proposal ready; no renders submitted", proposal=result)
        except Exception as exc:
            current = record_get(self.store, "sequence_plans", ident)
            error = str(getattr(exc, "detail", exc))
            cancelled = self.cancelled("sequence_plans", ident) and "could not be confirmed" not in error
            current.update(status="cancelled" if cancelled else "failed", stage="Planning cancelled" if cancelled else "Planning failed", error=error)
        record_save(self.store, "sequence_plans", current)

    def advance_sequence(self, record):
        ident = record["id"]
        try:
            if self.cancelled("sequences", ident):
                record.update(status="cancelled", stage="Sequence cancelled; completed shots retained")
                record_save(self.store, "sequences", record)
                return
            if record["status"] == "queued":
                record.update(status="running", stage="Preparing next explicit shot")
                record_save(self.store, "sequences", record)
            with self.store.connection() as db:
                rows = db.execute("SELECT episode_index,position,record FROM sequence_shots WHERE sequence_id=? ORDER BY episode_index,position", (ident,)).fetchall()
            for episode_index, episode in enumerate(record["episodes"]):
                if episode["status"] == "succeeded":
                    continue
                episode_rows = [(row[1], json.loads(row[2])) for row in rows if row[0] == episode_index]
                for position, shot in episode_rows:
                    if shot["status"] == "succeeded":
                        if shot.get("narration", {}).get("text", "").strip() and shot.get("narration_status") != "succeeded":
                            self.advance_narration(record, episode_index, position, shot)
                            return
                        continue
                    if shot.get("job_id"):
                        job = self.store.get("jobs", shot["job_id"])
                        if not job:
                            raise ValueError("A sequence render was deleted; its provenance is unavailable")
                        if job["status"] in {"queued", "running"}:
                            return
                        if job["status"] != "succeeded":
                            shot.update(status=job["status"], error=job.get("error") or "The shot was cancelled")
                            self.save_shot(ident, episode_index, position, shot)
                            raise ValueError(f"Episode {episode_index+1}, shot {position+1} did not complete: {shot['error']}")
                        kind = "image" if shot.get("preparation_only") else "video"
                        outputs = [output for output in job["outputs"] if output["kind"] == kind and output.get("role", "result") == "result"]
                        if len(outputs) != 1:
                            raise ValueError(f"A sequence stage must produce exactly one final {kind}")
                        media = asset(self.store, outputs[0]["id"], kind)
                        request = shot["request"]
                        if (media["width"], media["height"]) != (request["width"], request["height"]) or (kind == "video" and abs(media["fps"] - request["fps"]) > .01):
                            raise ValueError("A stage returned unexpected dimensions/FPS; the sequence will not silently crop or retime it")
                        if kind == "video" and media.get("frame_count") is not None and media["frame_count"] != request["frames"]:
                            raise ValueError("A shot returned an incomplete frame count")
                        shot.update(status="succeeded", output_asset_id=media["id"], actual_duration=media["duration"] if kind == "video" else 0, error=None)
                        self.save_shot(ident, episode_index, position, shot)
                        with self.store.connection() as db:
                            db.execute("INSERT OR IGNORE INTO sequence_assets VALUES (?,?)", (ident, media["id"]))
                        # Persist one completed transition, then re-read fresh rows next tick.
                        return
                    self.submit_shot(record, episode_index, position, shot, episode_rows)
                    return
                if episode.get("captions", {}).get("mode") == "soundtrack" and not episode.get("transcription"):
                    self.advance_transcription(record, episode_index)
                    return
                record["stage"] = f"Assembling episode {episode_index+1} from completed shots"
                record_save(self.store, "sequences", record)
                self.assemble(record, episode_index, episode_rows)
                return
            record.update(status="succeeded", stage="All episodes assembled from complete shots", error=None)
            record_save(self.store, "sequences", record)
        except Exception as exc:
            current = record_get(self.store, "sequences", ident)
            cancelled = self.cancelled("sequences", ident)
            if "shot" in locals() and shot["status"] != "succeeded":
                shot.update(status="cancelled" if cancelled else "failed", error=None if cancelled else str(getattr(exc, "detail", exc))[:2500])
                self.save_shot(ident, episode_index, position, shot)
            current.update(status="cancelled" if cancelled else "failed", stage="Sequence cancelled; completed shots retained" if cancelled else "Sequence incomplete — action required",
                           error=None if cancelled else str(getattr(exc, "detail", exc))[:2500])
            record_save(self.store, "sequences", current)

    def enqueue_audio(self, record, request, episode_index, position=None, shot=None):
        """One normal child job, atomically linked to its sequence owner."""
        with self.store.lock:
            if self.cancelled("sequences", record["id"]):
                return
            job = self.prepare_job(RenderRequest.model_validate(request))
            context = {"app_id": record["app_id"], "document_id": record["document_id"], "document_revision": record["document_revision"],
                       "operation": request["effect_id"], "step_id": f"audio:{episode_index}:{position}", "group_id": record["id"], "sequence_id": record["id"]}
            job["app_context"] = context
            association = context | {"job_id": job["id"], "document_snapshot": record["document_snapshot"]}
            if shot is not None:
                shot.update(narration_job_id=job["id"], narration_status="queued", narration_error=None)
                shot.setdefault("narration_attempt_job_ids", []).append(job["id"])
                stage = f"Narrating episode {episode_index + 1}, shot {position + 1}"
            else:
                record["episodes"][episode_index]["transcription_job_id"] = job["id"]
                record["episodes"][episode_index].setdefault("transcription_attempt_job_ids", []).append(job["id"])
                stage = f"Recognizing soundtrack captions for episode {episode_index + 1}"
            record.update(stage=stage, updated_at=now())
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job["id"], "queued", job["created_at"], job["updated_at"], json.dumps(job)))
                db.execute("INSERT INTO app_job_links VALUES (?,?,?,?)", (job["id"], record["app_id"], record["document_id"], json.dumps(association)))
                db.execute("INSERT INTO sequence_job_links VALUES (?,?)", (record["id"], job["id"]))
                if shot is not None:
                    db.execute("UPDATE sequence_shots SET record=? WHERE sequence_id=? AND episode_index=? AND position=?", (json.dumps(shot), record["id"], episode_index, position))
                db.execute("UPDATE sequences SET updated_at=?,record=? WHERE id=?", (record["updated_at"], json.dumps(record), record["id"]))

    def advance_narration(self, record, episode_index, position, shot):
        narration = shot["narration"]
        if not shot.get("narration_job_id"):
            self.enqueue_audio(record, {"model_id": "ming-narration", "effect_id": "narrate-shot", "provider": record["episodes"][episode_index].get("audio_provider") or "local",
                "prompt": narration["text"], "voice": narration["voice"], "speech_speed": narration["speed"], "caption_language": narration["language"],
                "seed": shot["request"]["seed"], "width": 64, "height": 64, "frames": 1, "fps": 1, "steps": 1, "guidance": 1,
                "generate_captions": record["episodes"][episode_index].get("captions", {}).get("mode") == "narration"}, episode_index, position, shot)
            return
        job = self.store.get("jobs", shot["narration_job_id"])
        if not job:
            raise ValueError("Narration provenance is missing")
        if job["status"] in {"queued", "running"}:
            return
        if job["status"] != "succeeded":
            shot.update(narration_status="failed", narration_error=job.get("error") or "Narration was cancelled")
            self.save_shot(record["id"], episode_index, position, shot)
            raise ValueError(shot["narration_error"])
        outputs = [item for item in job["outputs"] if item["kind"] == "audio" and item.get("role", "result") == "result"]
        if len(outputs) != 1:
            raise ValueError("Narration must return one actual audio recording")
        audio = asset(self.store, outputs[0]["id"], "audio")
        shot.update(narration_output_asset_id=audio["id"], narration_output=public_asset(audio), narration_actual_duration=audio["duration"],
                    narration_metadata=job.get("metadata", {}).get("narration", {}), narration_status="succeeded", narration_error=None)
        if audio["duration"] + narration["start"] > shot["actual_duration"] + .001:
            shot.update(narration_status="failed", narration_error=f"Narration lasts {audio['duration']:.2f}s but only {shot['actual_duration'] - narration['start']:.2f}s is available. Shorten the script or explicitly change its speed/start; no speech was clipped.")
        self.save_shot(record["id"], episode_index, position, shot)
        with self.store.connection() as db:
            db.execute("INSERT OR IGNORE INTO sequence_assets VALUES (?,?)", (record["id"], audio["id"]))
        if shot["narration_error"]:
            raise ValueError(shot["narration_error"])

    def advance_transcription(self, record, episode_index):
        episode = record["episodes"][episode_index]
        if not episode.get("audio_asset_id"):
            raise ValueError("Soundtrack captions require an explicit foreground soundtrack")
        if not episode.get("transcription_job_id"):
            available = asset(self.store, episode["audio_asset_id"], "audio")["duration"] - episode["audio_start"]
            self.enqueue_audio(record, {"model_id": "qwen-caption", "effect_id": "transcribe-audio", "provider": episode.get("audio_provider") or "local", "prompt": "",
                "audio_asset_id": episode["audio_asset_id"], "audio_start": episode["audio_start"], "audio_duration": min(episode["planned_duration"], available) if episode.get("pad_audio_silence") else episode["planned_duration"],
                "caption_language": episode["captions"].get("language", "English"), "generate_captions": True,
                "width": 64, "height": 64, "frames": 1, "fps": 1, "steps": 1, "guidance": 1, "seed": 42}, episode_index)
            return
        job = self.store.get("jobs", episode["transcription_job_id"])
        if not job:
            raise ValueError("Soundtrack transcription provenance is missing")
        if job["status"] in {"queued", "running"}:
            return
        if job["status"] != "succeeded":
            raise ValueError(job.get("error") or "Soundtrack transcription was cancelled")
        transcription = job.get("metadata", {}).get("narration", {}).get("transcription")
        if not transcription or not transcription.get("words"):
            raise ValueError("The soundtrack returned no real word timing")
        episode["transcription"] = transcription
        record_save(self.store, "sequences", record)

    def submit_shot(self, record, episode_index, position, shot, episode_rows):
        request = deepcopy(shot["request"])
        dependency_asset = None
        if shot["source_from_previous"]:
            previous = episode_rows[position - 1][1]
            if previous["status"] != "succeeded":
                raise ValueError("The preceding shot is not complete")
            if previous.get("preparation_only"):
                dependency_asset = asset(self.store, previous["output_asset_id"], "image")
                shot["dependency"] = {"job_id": previous["job_id"], "output_asset_id": dependency_asset["id"], "sha256": dependency_asset["sha256"], "execution": "direct preparation-image input; no extraction or copy"}
            else:
                media = asset(self.store, previous["output_asset_id"], "video")
                directory = self.store.root / "sequences" / record["id"] / "inputs"
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"episode-{episode_index+1}-shot-{position+1}.png"
                timestamp = max(0, media["duration"] - 1 / media["fps"])
                path.write_bytes(frame_bytes(Path(media["path"]), timestamp))
                dependency_asset = register_asset(self.store, path, path.name, source_job_id=previous["job_id"])
                shot["dependency"] = {"job_id": previous["job_id"], "output_asset_id": media["id"], "frame_time": timestamp, "derived_asset_id": dependency_asset["id"]}
            request["source_asset_id"] = dependency_asset["id"]
        with self.store.lock:
            if self.cancelled("sequences", record["id"]):
                return
            job = self.prepare_job(RenderRequest.model_validate(request))
            context = {"app_id": record["app_id"], "document_id": record["document_id"], "document_revision": record["document_revision"],
                       "operation": request["effect_id"], "step_id": f"{episode_index+1}:{shot['id']}", "group_id": record["id"], "sequence_id": record["id"]}
            job["app_context"] = context
            snapshot = deepcopy(record["document_snapshot"])
            if dependency_asset:
                snapshot["asset_ids"] = list(dict.fromkeys(snapshot["asset_ids"] + [dependency_asset["id"]]))
            association = context | {"job_id": job["id"], "document_snapshot": snapshot}
            shot.update(status="queued", job_id=job["id"], resolved_request=job["request"], error=None)
            shot["attempt_job_ids"].append(job["id"])
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job["id"], "queued", job["created_at"], job["updated_at"], json.dumps(job)))
                db.execute("INSERT INTO app_job_links VALUES (?,?,?,?)", (job["id"], record["app_id"], record["document_id"], json.dumps(association)))
                db.execute("INSERT INTO sequence_job_links VALUES (?,?)", (record["id"], job["id"]))
                db.execute("UPDATE sequence_shots SET record=? WHERE sequence_id=? AND episode_index=? AND position=?", (json.dumps(shot), record["id"], episode_index, position))
                if dependency_asset:
                    db.execute("INSERT OR IGNORE INTO sequence_assets VALUES (?,?)", (record["id"], dependency_asset["id"]))
            current = record_get(self.store, "sequences", record["id"])
            current["stage"] = f"Rendering episode {episode_index+1}, shot {position+1}: {shot['label']}"
            record_save(self.store, "sequences", current)

    def assemble(self, record, episode_index, rows):
        episode = record["episodes"][episode_index]
        preparations = [{"job_id": shot["job_id"], "output_asset_id": shot["output_asset_id"], "sha256": asset(self.store, shot["output_asset_id"], "image")["sha256"], "request": shot.get("resolved_request", shot["request"])} for _, shot in rows if shot.get("preparation_only")]
        rows = [(position, shot) for position, shot in rows if not shot.get("preparation_only")]
        clips = [asset(self.store, shot["output_asset_id"], "video") for _, shot in rows]
        frame_counts = [clip["frame_count"] for clip in clips]
        fps = clips[0]["fps"]
        overlap = transition_overlap(episode, frame_counts)
        expected_frames = sum(frame_counts) - overlap * (len(clips) - 1)
        duration = expected_frames / fps
        if not 0 < duration <= 300.001:
            raise ValueError("Measured episode duration is outside the 300-second bound; no shots were trimmed")
        if episode["keep_shot_audio"] and any(not item["has_audio"] for item in clips):
            raise ValueError("Per-shot audio was requested, but a shot is silent. Use an explicit soundtrack or disable shot audio in a new reviewed plan.")
        directory = self.store.root / "sequences" / record["id"]
        directory.mkdir(parents=True, exist_ok=True)
        audio_normalizations = []
        def prepared_audio(value):
            normalized, evidence = finalize_streaming_wav(value, directory / "normalized-audio")
            if evidence:
                audio_normalizations.append(evidence)
            return normalized
        target = directory / f"episode-{episode_index+1}-{uuid.uuid4().hex[:12]}.mp4"
        partial = target.with_name(target.stem + ".partial.mp4")
        narration_tracks, elapsed, last_narration_end = [], 0.0, 0.0
        captions = deepcopy(episode.get("captions", {"mode": "none", "burn_in": False, "cues": []}))
        generated_cues = []
        for (_, shot), clip in zip(rows, clips):
            narration = shot.get("narration", {})
            if narration.get("text", "").strip():
                if shot.get("narration_status") != "succeeded":
                    raise ValueError("Complete the shot's narration before assembling")
                audio = prepared_audio(asset(self.store, shot["narration_output_asset_id"], "audio"))
                offset = elapsed + narration.get("start", 0)
                if audio["duration"] + narration.get("start", 0) > clip["duration"] + .001:
                    raise ValueError("Narration exceeds its shot interval; edit the script instead of clipping speech")
                if offset < last_narration_end - .001:
                    raise ValueError("Narration overlaps across a shot transition. Shorten or offset the scripts explicitly.")
                last_narration_end = offset + audio["duration"]
                narration_tracks.append({"asset": audio, "offset": offset, "job_id": shot["narration_job_id"]})
                if captions["mode"] == "narration":
                    transcript = shot.get("narration_metadata", {}).get("transcription", {})
                    if not transcript.get("words"):
                        raise ValueError("Narration captions require actual recognized word timing")
                    generated_cues += cues_from_words(transcript["words"], offset, narration.get("language", "English"))
            elapsed += clip["duration"] - overlap / fps
        if captions["mode"] == "narration":
            captions["cues"] = generated_cues
        elif captions["mode"] == "soundtrack":
            captions["cues"] = cues_from_words(episode["transcription"]["words"], 0, captions.get("language", "English"))
        elif captions["mode"] == "none":
            captions["cues"] = []
        validate_cues(captions.get("cues", []), duration)
        background = prepared_audio(asset(self.store, episode["background_audio_asset_id"], "audio")) if episode.get("background_audio_asset_id") else None
        if background and background["duration"] - episode.get("background_audio_start", 0) < duration - .001:
            raise ValueError("Background audio is shorter than the measured episode; no looping was applied")
        encoder = caption_ffmpeg() if captions.get("burn_in") and captions.get("cues") else "ffmpeg"
        command = [encoder, "-nostdin", "-y", "-v", "error", "-xerror", "-nostats", "-filter_complex_threads", "1"]
        for clip in clips:
            command += ["-threads", "1", "-i", clip["path"]]
        filters, inputs = [], []
        for index, clip in enumerate(clips):
            filters.append(f"[{index}:v:0]settb=AVTB,setpts=PTS-STARTPTS[v{index}]")
            inputs.append(f"[v{index}]")
            if episode["keep_shot_audio"]:
                filters.append(f"[{index}:a:0]aresample=48000:async=1:first_pts=0,apad,atrim=duration={clip['duration']:.9f}[a{index}]")
                inputs.append(f"[a{index}]")
        audio_count = int(episode["keep_shot_audio"])
        if overlap:
            video, audio = "v0", "a0"
            elapsed = frame_counts[0] / fps
            for index in range(1, len(clips)):
                next_video = f"transition{index}"
                filters.append(f"[{video}][v{index}]xfade=transition={episode['transition']}:duration={overlap / fps:.9f}:offset={elapsed - overlap / fps:.9f}[{next_video}]")
                video = next_video
                if audio_count:
                    next_audio = f"crossaudio{index}"
                    filters.append(f"[{audio}][a{index}]acrossfade=d={overlap / fps:.9f}:c1=tri:c2=tri[{next_audio}]")
                    audio = next_audio
                elapsed += (frame_counts[index] - overlap) / fps
            filters.append(f"[{video}]trim=end_frame={expected_frames},setpts=PTS-STARTPTS[outv]")
            if audio_count:
                filters.append(f"[{audio}]atrim=duration={duration:.9f},asetpts=PTS-STARTPTS[outa]")
        else:
            filters.append("".join(inputs) + f"concat=n={len(clips)}:v=1:a={audio_count}[outv]" + ("[outa]" if audio_count else ""))
        soundtrack = None
        if episode["audio_asset_id"]:
            soundtrack = prepared_audio(asset(self.store, episode["audio_asset_id"], "audio"))
            available = soundtrack["duration"] - episode["audio_start"]
            if available <= 0 or (available < duration - .001 and not episode.get("pad_audio_silence")):
                raise ValueError("The explicit soundtrack is shorter than the measured episode; no audio was looped")
            command += ["-ss", str(episode["audio_start"]), "-i", soundtrack["path"]]
            pad = "apad," if episode.get("pad_audio_silence") else ""
            filters.append(f"[{len(clips)}:a:0]asetpts=PTS-STARTPTS,{pad}atrim=duration={duration:.9f}[outa]")
        final_audio = mix_audio(command, filters, episode, narration_tracks, duration, len(clips) + int(bool(soundtrack)), bool(audio_count or soundtrack), background)
        video_label = "outv"
        if captions.get("burn_in") and captions.get("cues"):
            subtitle_name = f"episode-{episode_index + 1}.srt"
            (directory / subtitle_name).write_text(caption_text(captions["cues"], "srt"))
            filters.append(f"[outv]subtitles=filename={subtitle_name}:force_style='FontName=Arial,FontSize=20,Outline=1,Shadow=0,MarginV=16'[captioned]")
            video_label = "captioned"
        command += ["-filter_complex", ";".join(filters), "-map", f"[{video_label}]"]
        if final_audio:
            command += ["-map", f"[{final_audio}]", "-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        from custom_nodes.openframe.media import video_encoding_args
        command += ["-c:v", "libx264", "-threads", "2", "-preset", "fast"]
        command += video_encoding_args(clips[0]["width"], clips[0]["height"], fps, episode.get("encoding_quality", "legacy"))
        command += ["-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-movflags", "+faststart", str(partial)]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=directory)
        started = time.monotonic()
        try:
            while True:
                try:
                    _, error = process.communicate(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancelled("sequences", record["id"]) or time.monotonic() - started > 1800:
                        raise ValueError("Assembly cancelled or exceeded its 30-minute bound")
            if process.returncode:
                raise ValueError("Episode assembly failed: " + error.decode(errors="replace")[-1500:])
            if self.cancelled("sequences", record["id"]):
                raise ValueError("Assembly cancelled")
            partial.replace(target)
            measured = inspect_media(target)
            if measured.get("frame_count") != expected_frames:
                raise ValueError("The assembled frame count does not match the reviewed shot and transition plan")
            if abs(measured["duration"] - duration) > 1 / clips[0]["fps"] + .001:
                raise ValueError("Assembled duration differs from the measured complete shots")
            output = register_asset(self.store, target, f"{episode['title'] or 'Episode'}.mp4")
            provenance = {"sequence_id": record["id"], "episode_id": episode["id"], "target_duration": episode["target_duration"],
                          "planned_duration": episode["planned_duration"], "actual_duration": output["duration"], "expected_frames": expected_frames, "preparation_stages": preparations,
                          "shots": [{"id": shot["id"], "job_id": shot["job_id"], "asset_id": clip["id"], "sha256": clip["sha256"],
                                     "actual_duration": clip["duration"], "request": shot.get("resolved_request", shot["request"]), "dependency": shot.get("dependency"),
                                     "existing_video": shot.get("existing_video_provenance")} for (_, shot), clip in zip(rows, clips)],
                          "audio": {"keep_shot_audio": episode["keep_shot_audio"], "soundtrack_asset_id": episode["audio_asset_id"], "audio_start": episode["audio_start"],
                                    "pad_audio_silence": episode.get("pad_audio_silence", False),
                                    "speech_caption_provider": episode.get("audio_provider") or "local",
                                    "background_asset_id": episode.get("background_audio_asset_id"), "background_start": episode.get("background_audio_start", 0),
                                    "background_gain": episode.get("background_gain", .15), "duck_background": bool(background and (narration_tracks or soundtrack or audio_count) and episode.get("duck_background", True)),
                                    "narration_gain": episode.get("narration_gain", 1), "shot_audio_gain": episode.get("shot_audio_gain", 1), "limiter": .95,
                                    "input_normalizations": audio_normalizations,
                                    "narration": [{"job_id": track["job_id"], "asset_id": track["asset"]["id"], "sha256": track["asset"]["sha256"], "start": track["offset"], "duration": track["asset"]["duration"]} for track in narration_tracks]},
                          "captions": captions, "transcription_job_id": episode.get("transcription_job_id"),
                          "output": public_asset(output), "assembly": "Ordered cuts" if not overlap else "Explicit frame-aligned transitions with overlapping shot audio",
                          "transition": {"kind": episode.get("transition", "cut"), "overlap_frames": overlap},
                          "encoding_quality": episode.get("encoding_quality", "legacy")}
            target.with_suffix(".json").write_text(json.dumps(provenance, indent=2))
            with self.store.lock:
                current = record_get(self.store, "sequences", record["id"])
                if self.cancelled("sequences", record["id"]):
                    raise ValueError("Assembly cancelled")
                current["episodes"][episode_index].update(status="succeeded", actual_duration=output["duration"], output=public_asset(output), provenance=provenance, captions=captions)
                record_save(self.store, "sequences", current)
                with self.store.connection() as db:
                    db.execute("INSERT OR IGNORE INTO sequence_assets VALUES (?,?)", (record["id"], output["id"]))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate()
            if process.stderr:
                process.stderr.close()
            partial.unlink(missing_ok=True)
