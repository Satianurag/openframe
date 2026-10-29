"""A single inference queue with durable state and cooperative cancellation."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Callable

from .media import public_asset, register_asset
from .store import Store


class JobWorker:
    def __init__(self, store: Store, settings: Callable[[], dict]):
        self.store = store
        self.settings = settings
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.cancels: dict[str, threading.Event] = {}
        self.thread = threading.Thread(target=self.loop, name="openframe-render", daemon=True)

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
            job = self.store.claim_next()
            if job is None:
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
            for role in ("source", "mask", "reference"):
                asset_id = job["request"].get(f"{role}_asset_id")
                if asset_id:
                    asset = self.store.get("assets", asset_id)
                    if not asset or not Path(asset["path"]).is_file():
                        raise ValueError(f"The {role} asset is no longer available")
                    asset_paths[role] = asset["path"]
            if is_cancelled():
                self.store.update_job(ident, {"status": "cancelled", "stage": "Cancelled"})
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
                asset = register_asset(self.store, path, output.get("name", path.name), source_job_id=ident)
                output_record = public_asset(asset)
                output_record["role"] = output.get("role", "result")
                outputs.append(output_record)
            if not outputs:
                raise ValueError("The render completed without any video or image output")
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
