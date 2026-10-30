"""Text-selected soft video matting, isolated from Comfy's NumPy/Transformers."""
from collections import deque
import json
import mmap
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

import numpy as np
import torch
import folder_paths
import comfy.model_management
import comfy.utils
from .media import decode_frames
from .advanced_video import _input, _streams
from .sam_runtime_config import runtime_python, official_support_status


class OpenFrameSemanticMatte:
    @classmethod
    def INPUT_TYPES(cls):
        root = Path(folder_paths.models_dir)
        ready, detail = official_support_status(root)
        if ready and not torch.cuda.is_available():
            ready, detail = False, "Official SAM3.1 requires a CUDA-capable ComfyUI host."
        if ready and not all((root / name).is_file() for name in (
            "matting/vitmatte/pytorch_model.bin",
            "matting/vitmatte/config.json", "matting/vitmatte/preprocessor_config.json")):
            ready, detail = False, "Provision the three pinned ViTMatte files in models/matting/vitmatte."
        return {"required": {
            "filename": ("STRING",), "prompt": ("STRING", {"default": "person", "openframe_semantic_matte_available": ready,
                "openframe_semantic_matte_detail": detail if not ready else "SAM3.1 and ViTMatte files present; isolated imports are checked at execution."}),
            "width": ("INT", {"min": 64, "max": 1920}), "height": ("INT", {"min": 64, "max": 1920}),
            "frames": ("INT", {"min": 1, "max": 241}), "fps": ("FLOAT", {"min": 1, "max": 120}),
            "trim_start": ("FLOAT", {"default": 0, "min": 0}), "trimap_radius": ("INT", {"default": 12, "min": 1, "max": 64}),
            "subject_confidence": ("FLOAT", {"default": .5, "min": .1, "max": .9})}}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("original_rgb", "soft_alpha")
    FUNCTION = "matte"
    CATEGORY = "OpenFrame/Video"

    def matte(self, filename, prompt, width, height, frames, fps, trim_start, trimap_radius, subject_confidence):
        if not self.INPUT_TYPES()["required"]["prompt"][1]["openframe_semantic_matte_available"]:
            raise ValueError("Configure the Linux CUDA SAM3.1 runtime and both SAM3.1/ViTMatte checkpoints on the ComfyUI host; see RECAST-RUNTIME.md. No runtime downloads are attempted.")
        if not prompt.strip() or len(prompt.strip()) > 200:
            raise ValueError("Describe the foreground to keep in 1–200 characters.")
        if min(width, height) > 1088 or width % 2 or height % 2 or not 1 <= frames <= 241:
            raise ValueError("Use an even source canvas up to 1920×1088 in either orientation and at most 241 frames.")
        path = _input(filename)
        info = next(s for s in _streams(path) if s.get("codec_type") == "video")
        sw, sh = int(info["width"]), int(info["height"])
        rotation = next((x.get("rotation", 0) for x in info.get("side_data_list", []) if "rotation" in x), 0)
        if abs(int(rotation)) % 180 == 90:
            sw, sh = sh, sw
        if (sw, sh) != (width, height):
            raise ValueError("Semantic matting preserves the source dimensions; resize the source explicitly first if needed.")
        decoded = decode_frames(path, width, height, fps, frames, trim_start)
        original, alpha, metadata = run_semantic_prediction(decoded, prompt, trimap_radius, subject_confidence)
        metadata.update(frames=frames, width=width, height=height, fps=fps, source_filename=filename, trim_start=trim_start)
        return {"ui": {"openframe_matte": [metadata]}, "result": (original, alpha)}


def run_semantic_prediction(decoded, prompt, trimap_radius, subject_confidence, *, binary_only=False, selection=None):
    """Shared bounded/cancellable isolated predictor; frames never touch disk."""
    frames, height, width = decoded.shape[:3]
    comfy.model_management.unload_all_models()
    fds, maps = [], []
    process = reader = shared_rgb = None
    stop_reader = threading.Event()
    try:
        for name, size in (("openframe-matte-rgb", frames * height * width * 3), ("openframe-matte-alpha", frames * height * width * 4)):
            fd = os.memfd_create(name)
            fds.append(fd)
            os.ftruncate(fd, size)
            maps.append(mmap.mmap(fd, size))
        shared_rgb = np.ndarray((frames, height, width, 3), np.uint8, buffer=maps[0])
        shared_rgb[:] = decoded
        del decoded
        command = [str(runtime_python()), str(Path(__file__).with_name("semantic_runtime.py")),
            "--source-fd", str(fds[0]), "--alpha-fd", str(fds[1]), "--frames", str(frames),
            "--width", str(width), "--height", str(height), "--radius", str(trimap_radius),
            "--confidence", str(subject_confidence), "--prompt", prompt.strip(), "--models", str(folder_paths.models_dir)]
        if binary_only:
            command.append("--binary-only")
        if selection is not None:
            fd = os.memfd_create("openframe-matte-selection")
            fds.append(fd)
            os.write(fd, np.asarray(selection >= .5, dtype=np.uint8).tobytes())
            command.extend(["--selection-fd", str(fd)])
        env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
        # The helper is self-contained; do not inject the parent ComfyUI's
        # NumPy/Transformers paths into its explicitly isolated interpreter.
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        process = subprocess.Popen(command, pass_fds=fds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        lines = queue.Queue(maxsize=128)

        def consume():
            for line in process.stdout:
                while not stop_reader.is_set():
                    try:
                        lines.put(line[-20000:], timeout=.25)
                        break
                    except queue.Full:
                        pass
                if stop_reader.is_set():
                    break

        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        bar, tail, metadata = comfy.utils.ProgressBar(1000), deque(maxlen=30), None
        deadline = time.monotonic() + 3600
        while reader.is_alive() or not lines.empty() or process.poll() is None:
            comfy.model_management.throw_exception_if_processing_interrupted()
            if time.monotonic() > deadline:
                raise ValueError("Prompted matting exceeded its one-hour execution budget.")
            try:
                line = lines.get(timeout=.25)
            except queue.Empty:
                continue
            tail.append(line[-1000:])
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if "progress" in event:
                bar.update_absolute(int(event["progress"] * 1000), 1000)
            if "result" in event:
                metadata = event["result"]
        if process.wait(timeout=10) or metadata is None:
            raise ValueError("Prompted matting failed: " + "".join(tail)[-3000:])
        original = None if binary_only else torch.from_numpy(shared_rgb).float().div_(255)
        alpha = torch.from_numpy(np.ndarray((frames, height, width), np.float32, buffer=maps[1])).clone()
        return original, alpha, metadata
    finally:
        stop_reader.set()
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)
            if reader:
                reader.join(timeout=2)
            if process.stdout:
                process.stdout.close()
        shared_rgb = None
        for view in maps:
            view.close()
        for fd in fds:
            os.close(fd)
