"""Comfy output node for real sequence narration and recognized word timing."""
from collections import deque
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import threading
import time

import folder_paths


def runtime_status():
    """Bounded installation detection, not a synthesis/recognition quality claim."""
    root = Path(os.environ.get("OPENFRAME_MODEL_CACHE", folder_paths.models_dir))
    ming_python = os.environ.get("OPENFRAME_MING_PYTHON", "")
    asr_python = os.environ.get("OPENFRAME_ASR_PYTHON", "")
    source = os.environ.get("OPENFRAME_MING_SOURCE", "")
    status = {"ming": False, "captions": False,
              "detail": "Configure the pinned Linux/WSL2 CUDA environments and weights on the ComfyUI host; see NARRATION-RUNTIME.md. Detection does not run inference."}
    try:
        import torch
        from engine.narration_models import MING_FILES, ASR_FILES, ALIGNER_FILES
        ready = platform.system() == "Linux" and torch.cuda.is_available()
        def files(entries):
            return all((path := root / item["category"] / Path(item["file"]).name).is_file() and path.stat().st_size == item["size_bytes"] for item in entries)
        status["ming"] = bool(ready and ming_python and Path(ming_python).is_file() and source and (Path(source) / "ming_tts.py").is_file() and files(MING_FILES))
        status["captions"] = bool(ready and asr_python and Path(asr_python).is_file() and files(ASR_FILES + ALIGNER_FILES))
    except (ImportError, OSError):
        pass
    return status


def _run(command, cancelled, stage, extra_env=None):
    lines = deque(maxlen=40)
    env = {**os.environ, **(extra_env or {}), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    def consume():
        for line in process.stdout:
            lines.append(line[-1000:])
    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    started = time.monotonic()
    try:
        while process.poll() is None:
            cancelled()
            if time.monotonic() - started > 1800:
                raise RuntimeError(stage + " exceeded its30minute execution bound")
            try:
                process.wait(timeout=.25)
            except subprocess.TimeoutExpired:
                pass
        reader.join(timeout=2)
        if process.returncode:
            raise RuntimeError(stage + " failed: " + "".join(lines)[-4000:])
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        reader.join(timeout=2)
        process.stdout.close()


class OpenFrameSequenceNarration:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"request_json": ("STRING", {"multiline": True, "openframe_narration_runtime": runtime_status()}), "audio_filename": ("STRING", {"default": ""}),
                             "filename_prefix": ("STRING", {"default": "OpenFrameNarration"})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "OpenFrame/Sequence"

    def execute(self, request_json, audio_filename, filename_prefix):
        import comfy.model_management as management
        from comfy.utils import ProgressBar
        from engine.narration_models import MING_COMMIT, MING_REVISION, ASR_COMMIT, ASR_REVISION, ALIGNER_REVISION
        from engine.narration_workflows import normalize_narration
        from engine.narration_models import NARRATION_MODEL_FILES
        from engine import narration_runtime
        request = normalize_narration({**json.loads(request_json), "provider": "local"})
        status = runtime_status()
        if (request["model_id"] == "ming-narration" and not status["ming"]) or (request.get("generate_captions") and not status["captions"]):
            raise RuntimeError(status["detail"])
        if request["model_id"] == "ming-narration" and not 1 <= len(request.get("prompt", "").strip()) <= 1200:
            raise ValueError("Narration requires a script of1–1200characters")
        root = Path(os.environ.get("OPENFRAME_MODEL_CACHE", folder_paths.models_dir))
        for entry in NARRATION_MODEL_FILES[request["model_id"]]:
            if entry.get("feature") and not request.get(entry["feature"]):
                continue
            if not (root / entry["category"] / Path(entry["file"]).name).is_file():
                raise RuntimeError("Install the selected pinned narration/caption files on the ComfyUI host")
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(parents=True, exist_ok=True)
        prefix = Path(filename_prefix).name
        if not prefix or prefix in {".", ".."}:
            raise ValueError("Invalid narration output prefix")
        target = output / (prefix + ".wav")
        request_path = output / (prefix + ".narration-request.json")
        receipt_path = output / (prefix + ".narration-part.json")
        request_path.write_text(json.dumps(request, ensure_ascii=False))
        management.unload_all_models(); management.soft_empty_cache()
        progress = ProgressBar(1000)
        cancelled = management.throw_exception_if_processing_interrupted
        metadata = {"provider": "local", "runtime": "configured isolated CUDA environments", "runtime_downloads": False}
        runtime = str(Path(narration_runtime.__file__).resolve())
        child_env = {"OPENFRAME_MODEL_CACHE": str(root)}
        try:
            if request["model_id"] == "ming-narration":
                progress.update_absolute(50)
                _run([os.environ["OPENFRAME_MING_PYTHON"], runtime, "synthesize", str(request_path), str(target), str(receipt_path)], cancelled, "Narration synthesis", child_env)
                metadata["synthesis"] = {**json.loads(receipt_path.read_text()), "model_revision": MING_REVISION, "code_revision": MING_COMMIT, "license": "MIT"}
            else:
                source = Path(folder_paths.get_annotated_filepath(audio_filename)).resolve()
                if not source.is_file() or not source.is_relative_to(Path(folder_paths.get_input_directory()).resolve()):
                    raise ValueError("Choose an uploaded soundtrack")
                _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(float(request.get("audio_start", 0))), "-i", str(source),
                      "-t", str(float(request["audio_duration"])), "-vn", "-ar", "48000", "-c:a", "pcm_s16le", str(target)], cancelled, "Soundtrack selection")
                metadata["selected_audio"] = {"start": request.get("audio_start", 0), "duration": request["audio_duration"]}
            if request.get("generate_captions"):
                progress.update_absolute(550)
                _run([os.environ["OPENFRAME_ASR_PYTHON"], runtime, "transcribe", str(request_path), str(target), str(receipt_path)], cancelled, "Speech recognition and alignment", child_env)
                metadata["transcription"] = {**json.loads(receipt_path.read_text()), "model_revision": ASR_REVISION,
                    "aligner_revision": ALIGNER_REVISION, "code_revision": ASR_COMMIT, "license": "Apache-2.0"}
            with target.open("rb") as file:
                metadata["audio_sha256"] = hashlib.file_digest(file, "sha256").hexdigest()
            (output / (prefix + ".narration.json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
            progress.update_absolute(1000)
            return {"ui": {"audio": [{"filename": target.name, "subfolder": "openframe", "type": "output", "format": "audio/wav", "role": "result"}],
                           "openframe_narration": [metadata]}}
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            request_path.unlink(missing_ok=True); receipt_path.unlink(missing_ok=True)


NODE_CLASS_MAPPINGS = {"OpenFrameSequenceNarration": OpenFrameSequenceNarration}
NODE_DISPLAY_NAME_MAPPINGS = {"OpenFrameSequenceNarration": "OpenFrame · Sequence narration and timed captions"}
