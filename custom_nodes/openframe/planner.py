"""Comfy output node around the existing pinned CUDA visual planner."""
from collections import deque
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import time

import folder_paths


def runtime_status():
    status = {"available": False, "model_id": "qwen3.8-planner", "detail": "Configure the isolated Qwen3.8 CUDA environment and pinned weights on this ComfyUI host; see PLANNER-RUNTIME.md. No model is downloaded at execution."}
    try:
        import torch
        from engine.analysis_models import ANALYSIS_MODEL_ID, ANALYSIS_MODEL_FILES
        python = os.environ.get("OPENFRAME_VISUAL_PLANNER_PYTHON", "")
        root = Path(os.environ.get("OPENFRAME_VISUAL_PLANNER_MODEL_DIR", str(Path(folder_paths.models_dir) / "planning/qwen3.8-27b")))
        status["available"] = bool(platform.system() == "Linux" and torch.cuda.is_available() and python
            and Path(python).is_file() and os.access(python, os.X_OK)
            and all((path := root / item["file"]).is_file() and path.stat().st_size == item["size_bytes"] for item in ANALYSIS_MODEL_FILES[ANALYSIS_MODEL_ID]))
        if status["available"]:
            status["detail"] = "Pinned Qwen3.8 files, CUDA and isolated interpreter are detected; dependency compatibility and output quality still require execution."
    except (ImportError, OSError):
        pass
    return status


class OpenFrameVisualPlanner:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"request_json": ("STRING", {"multiline": True, "openframe_visual_planner": runtime_status()}),
                             "references_json": ("STRING", {"multiline": True, "default": "[]"})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "plan"
    CATEGORY = "OpenFrame/Sequence"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def plan(self, request_json, references_json):
        import comfy.model_management as management
        from engine.planner import normalize_plan_request
        from engine.analysis_models import ANALYSIS_MODEL_ID
        status = runtime_status()
        if not status["available"]:
            raise RuntimeError(status["detail"])
        request = normalize_plan_request({**json.loads(request_json), "provider": "local", "model_id": ANALYSIS_MODEL_ID})
        submitted = json.loads(references_json)
        if not isinstance(submitted, list) or len(submitted) > 4:
            raise ValueError("Use up to four uploaded visual references.")
        references = []
        for item in submitted:
            path = Path(folder_paths.get_annotated_filepath(item["filename"])).resolve()
            if item.get("kind") not in {"image", "video"} or not path.is_file() or not path.is_relative_to(Path(folder_paths.get_input_directory()).resolve()):
                raise ValueError("Planning references must be uploaded images/videos inside ComfyUI input.")
            references.append({"asset_id": item["asset_id"], "kind": item["kind"], "path": str(path)})
        if {item["asset_id"] for item in references} != set(request["reference_asset_ids"]):
            raise ValueError("The uploaded references do not match the reviewed planning request.")
        management.unload_all_models(); management.soft_empty_cache()
        model_dir = os.environ.get("OPENFRAME_VISUAL_PLANNER_MODEL_DIR", str(Path(folder_paths.models_dir) / "planning/qwen3.8-27b"))
        with tempfile.TemporaryDirectory(prefix="openframe-plan-", dir=folder_paths.get_temp_directory()) as directory:
            root = Path(directory)
            (root / "request.json").write_text(json.dumps(request, ensure_ascii=False))
            (root / "references.json").write_text(json.dumps(references))
            output = root / "proposal.json"
            env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
            import engine
            engine_root = str(Path(engine.__file__).resolve().parent.parent)
            env["PYTHONPATH"] = engine_root + os.pathsep + env.get("PYTHONPATH", "")
            process = subprocess.Popen([os.environ["OPENFRAME_VISUAL_PLANNER_PYTHON"], "-m", "engine.planner_runtime",
                str(root / "request.json"), str(root / "references.json"), model_dir, str(output)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            lines = deque(maxlen=40)
            def consume():
                for line in iter(lambda: process.stdout.readline(4096), ""):
                    lines.append(line[-1000:])
            reader = threading.Thread(target=consume, daemon=True); reader.start()
            deadline = time.monotonic() + request["budget_seconds"] + 60
            try:
                while process.poll() is None:
                    management.throw_exception_if_processing_interrupted()
                    if time.monotonic() > deadline:
                        raise RuntimeError("Visual planning exceeded its recorded execution budget.")
                    try:
                        process.wait(timeout=.25)
                    except subprocess.TimeoutExpired:
                        pass
                reader.join(timeout=2)
                if process.returncode:
                    raise RuntimeError("Visual planner failed: " + "".join(lines)[-4000:])
                if not output.is_file() or output.stat().st_size > 2 * 1024 * 1024:
                    raise RuntimeError("No bounded planner proposal was returned.")
                return {"ui": {"openframe_plan": [json.loads(output.read_text())]}}
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                reader.join(timeout=2); process.stdout.close()
