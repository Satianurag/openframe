"""A single inference queue with durable state and cooperative cancellation."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Callable

from .media import public_asset, register_asset, register_generated_archive
from .store import Store
from .models import request_asset_ids


class JobWorker:
    def __init__(self, store: Store, settings: Callable[[], dict], prepare_job=None):
        self.store = store
        self.settings = settings
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.cancels: dict[str, threading.Event] = {}
        self.thread = threading.Thread(target=self.loop, name="openframe-render", daemon=True)
        from .sequences import SequenceDriver
        self.sequences = SequenceDriver(store, prepare_job, settings, self.cancel, self.stopping.is_set) if prepare_job else None

    def start(self):
        self.store.recover()
        self.thread.start()
        self.wake.set()

    def stop(self):
        self.stopping.set()
        for event in list(self.cancels.values()):
            event.set()
        self.wake.set()
        self.thread.join(timeout=15)

    def cancel(self, ident: str) -> dict | None:
        with self.store.lock:
            job = self.store.get("jobs", ident)
            if not job or job["status"] not in {"queued", "running"}:
                return job
            changes = {"cancel_requested": True}
            if job["status"] == "queued":
                changes.update(status="cancelled", stage="Cancelled before execution")
            else:
                changes["stage"] = "Cancelling render"
            updated = self.store.update_job(ident, changes)
            event = self.cancels.get(ident)
            if event:
                event.set()
            return updated

    def loop(self):
        while not self.stopping.is_set():
            progressed = self.sequences.advance() if self.sequences else False
            job = self.store.claim_next()
            if job is None:
                if progressed:
                    continue
                self.wake.wait(timeout=2)
                self.wake.clear()
                continue
            self.execute(job)

    def execute(self, job: dict):
        ident = job["id"]
        cancel = threading.Event()
        self.cancels[ident] = cancel
        if (self.store.get("jobs", ident) or {}).get("cancel_requested"):
            cancel.set()
        last_write = 0.0
        output_dir = self.store.root / "renders" / ident
        output_dir.mkdir(parents=True, exist_ok=True)
        settings = self.settings()

        def is_cancelled():
            return cancel.is_set() or self.stopping.is_set()

        def progress(value: float, stage: str):
            nonlocal last_write
            moment = time.monotonic()
            # Node/step callbacks can be frequent. Persist significant changes, at most once a second.
            if moment - last_write < 1:
                return
            last_write = moment
            self.store.update_job(ident, {
                "progress": max(0, min(float(value), 0.99)),
                "stage": "Cancelling render" if is_cancelled() else str(stage)[:300],
            })

        try:
            from engine.runner import run_job
            asset_paths = {}
            for role, asset_id in request_asset_ids(job["request"]).items():
                if asset_id:
                    asset = self.store.get("assets", asset_id)
                    if not asset or not Path(asset["path"]).is_file():
                        raise ValueError(f"The {role} asset is no longer available")
                    asset_paths[role] = asset["path"]
            if is_cancelled():
                self.store.update_job(ident, {"status": "cancelled", "stage": "Cancelled"})
                return
            if job.get("kind") == "character-training":
                from .characters import execute_training
                execute_training(self.store, job, asset_paths, output_dir, settings, progress, is_cancelled)
                return
            result = run_job(job["request"], asset_paths, output_dir, settings, progress, is_cancelled)
            if is_cancelled():
                self.store.update_job(ident, {"status": "cancelled", "stage": "Cancelled"})
                return
            outputs = []
            for output in result.get("outputs", []):
                path = Path(output["path"]).resolve()
                if not path.is_relative_to(output_dir.resolve()) or not path.is_file():
                    raise ValueError("The inference engine returned an invalid output file")
                if path.stat().st_size == 0:
                    raise ValueError("The inference engine returned an empty output file")
                if output.get("kind") == "archive":
                    if job["request"].get("task") != "sdr-to-hdr" or job["request"].get("hdr_output_format") != "exr16":
                        raise ValueError("Only an explicitly requested HDR EXR export may return an archive")
                    asset = register_generated_archive(self.store, path, output.get("name", path.name), source_job_id=ident, role=output.get("role", "result"))
                else:
                    asset = register_asset(self.store, path, output.get("name", path.name), source_job_id=ident, role=output.get("role", "result"))
                output_record = public_asset(asset)
                output_record["role"] = output.get("role", "result")
                outputs.append(output_record)
            if not outputs:
                raise ValueError("The render completed without any video, image or audio output")
            from engine.catalog import effect_by_id
            expected_kind = effect_by_id(job["request"]["effect_id"])["output_kind"]
            if job["request"].get("task") == "sdr-to-hdr" and job["request"].get("hdr_output_format") == "exr16":
                expected_kind = "archive"
            expected_count = job["request"].get("batch_size", 1) if expected_kind == "image" else 1
            final_outputs = [item for item in outputs if item.get("role") == "result" and item["kind"] == expected_kind]
            if len(final_outputs) != expected_count:
                raise ValueError(f"The engine did not return the requested {expected_count} final {expected_kind} result(s)")
            if is_cancelled():
                self.store.update_job(ident, {"status": "cancelled", "stage": "Cancelled"})
                return
            workflow = result.get("workflow", {})
            metadata = result.get("metadata", {})
            self.store.update_job(ident, {
                "status": "succeeded", "progress": 1, "stage": "Complete", "outputs": outputs,
                "workflow": workflow, "ui_workflow": result.get("ui_workflow"), "metadata": metadata, "error": None,
            })
            manifest = {"job_id": ident, "request": job["request"], "metadata": metadata, "workflow": workflow}
            (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        except Exception as exc:
            cancelled = is_cancelled() or type(exc).__name__ == "JobCancelled"
            error = str(exc) or type(exc).__name__
            for key, value in settings.items():
                if ("key" in key or "token" in key) and isinstance(value, str) and value:
                    error = error.replace(value, "[redacted]")
            error = re.sub(r"(?i)(authorization[:=]\s*bearer\s+)\S+", r"\1[redacted]", error)
            self.store.update_job(ident, {
                "status": "cancelled" if cancelled else "failed",
                "stage": "Cancelled" if cancelled else "Render failed",
                "error": None if cancelled else error[:2500],
            })
        finally:
            self.cancels.pop(ident, None)
