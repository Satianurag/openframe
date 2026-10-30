"""Official temporal depth inference with local-cache-only CUDA weights.

The preview is not depth data. The separate FFV1 gray16 stream and recorded
clip-global mapping retain relative predictions without per-frame normalization.
"""
import importlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading
import types
import uuid

import numpy as np
import torch
import folder_paths
import comfy.model_management as management
import comfy.utils

from .media import decode_frames, encode_video
from .transitions import _info


PROFILES = {
    "video-depth-small": {"folder": "vda-source", "package": "video_depth_anything", "checkpoint": "depth/vda-small/video_depth_anything_vits.pth",
        "commit": "4f5ae23172ba60fd7bc11ef671cca678842c7072", "license": "Apache-2.0", "semantics": "relative_inverse_depth"},
    "vigeo-1.1": {"folder": "vigeo-source", "package": "vigeo", "checkpoint": "depth/vigeo-1.1/vigeo.pt",
        "commit": "1b2a48324759f34c323358084f7d60a9c5fbf2a7", "license": "CC-BY-NC-4.0 weights; Apache-2.0 code", "semantics": "relative_depth"},
}


def _paths(profile):
    spec = PROFILES[profile]
    return Path(folder_paths.base_path) / "openframe_depth" / spec["folder"], Path(folder_paths.models_dir) / spec["checkpoint"]


def _load_source(profile):
    spec = PROFILES[profile]
    root, checkpoint = _paths(profile)
    if not checkpoint.is_file() or not (root / spec["package"]).is_dir():
        raise ValueError("Prepare the selected depth checkpoint and pinned source in the remote cache before rendering; runtime downloads are disabled.")
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15, check=True).stdout.strip()
    if revision != spec["commit"]:
        raise ValueError("The depth source revision does not match this workflow's pinned implementation.")
    if profile == "video-depth-small" and not (root / "video_depth_anything/util/openframe_alignment.py").is_file():
        raise ValueError("Run the bundled depth source preparation helper before inference.")
    name = spec["package"]
    package_path = root / name
    existing = sys.modules.get(name)
    if existing is not None and str(package_path) not in list(getattr(existing, "__path__", [])):
        raise ValueError("A different depth package is already imported; use an isolated worker with the pinned source.")
    if existing is None:
        initializer = package_path / "__init__.py"
        if initializer.exists():
            module_spec = importlib.util.spec_from_file_location(name, initializer, submodule_search_locations=[str(package_path)])
            module = importlib.util.module_from_spec(module_spec)
            sys.modules[name] = module
            module_spec.loader.exec_module(module)
        else:
            module = types.ModuleType(name)
            module.__path__ = [str(package_path)]
            sys.modules[name] = module
    return checkpoint


def _encode_depth(target, depths, valid, fps, minimum, maximum):
    frames, height, width = depths.shape
    partial = target.with_suffix(".partial.mkv")
    process = subprocess.Popen(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray16le",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an", "-frames:v", str(frames),
        "-c:v", "ffv1", "-level", "3", "-threads", "2", "-pix_fmt", "gray16le", str(partial)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    timer = threading.Timer(300, process.kill)
    timer.daemon = True
    timer.start()
    try:
        span = maximum - minimum
        for frame, mask in zip(depths, valid):
            management.throw_exception_if_processing_interrupted()
            scaled = np.zeros_like(frame) if span <= 0 else (frame - minimum) / span
            codes = np.where(mask, 1 + np.rint(np.nan_to_num(scaled).clip(0, 1) * 65534), 0).astype("<u2")
            process.stdin.write(codes.tobytes())
        process.stdin.close()
        process.stdin = None
        _, error = process.communicate(timeout=300)
        if process.returncode:
            raise ValueError("Lossless depth encoding failed: " + error.decode(errors="replace")[-1000:])
        partial.replace(target)
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        if process.stdin:
            process.stdin.close()
            process.stdin = None
        process.communicate()
        if process.stderr:
            process.stderr.close()
        partial.unlink(missing_ok=True)


class OpenFrameVideoDepth:
    @classmethod
    def INPUT_TYPES(cls):
        available = [name for name in PROFILES if _paths(name)[1].is_file() and (_paths(name)[0] / PROFILES[name]["package"]).is_dir()]
        return {"required": {"filename": ("STRING",), "profile": (list(PROFILES), {"openframe_depth_available": available}),
            "width": ("INT", {"default": 768, "min": 64, "max": 1280}), "height": ("INT", {"default": 512, "min": 64, "max": 1280}),
            "frames": ("INT", {"default": 97, "min": 2, "max": 300}), "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120}),
            "trim_start": ("FLOAT", {"default": 0, "min": 0, "max": 86400}), "preserve_audio": ("BOOLEAN", {"default": True}),
            "encoding_quality": (["legacy", "standard", "high"],), "filename_prefix": ("STRING", {"default": "OpenFrame"}),
            "colormap": (["grayscale", "turbo", "inferno", "magma", "viridis"],), "side_by_side": ("BOOLEAN", {"default": False})},
            "optional": {"inference_mode": (["chunk", "offline"], {"default": "chunk"})}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "estimate"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/VFX"

    def estimate(self, filename, profile, width, height, frames, fps, trim_start, preserve_audio, encoding_quality, filename_prefix, colormap="grayscale", side_by_side=False, inference_mode="chunk"):
        from .nodes import _input_path
        if profile not in PROFILES or not torch.cuda.is_available():
            raise ValueError("Temporal depth requires its selected profile on a CUDA worker. Use the configured Local ComfyUI host; no CPU or alternate-model fallback is used.")
        if inference_mode not in {"chunk", "offline"} or (inference_mode == "offline" and (profile != "vigeo-1.1" or frames > 64)):
            raise ValueError("Offline depth inference requires ViGeo and at most 64 frames; otherwise choose chunk mode.")
        source = _input_path(filename)
        info = _info(source)
        if info["kind"] != "video" or trim_start + frames / fps > info["duration"] + .001:
            raise ValueError("The selected depth interval must fit within a real source video.")
        if abs(info["fps"] - fps) > .000001:
            raise ValueError("Depth analysis retains the selected source frame rate.")
        if width % 2 or height % 2 or width * height > 921600 or abs(width / height - info["width"] / info["height"]) > 2 / height:
            raise ValueError("Depth output must retain source aspect, use even dimensions and stay within 921600 pixels.")
        checkpoint = _load_source(profile)
        management.unload_all_models()
        images = decode_frames(source, width, height, fps, frames, trim_start)
        progress = comfy.utils.ProgressBar(frames)
        model = cache = None
        try:
            if profile == "video-depth-small":
                from video_depth_anything.video_depth import VideoDepthAnything
                model = VideoDepthAnything(encoder="vits", features=64, out_channels=[48, 96, 192, 384], metric=False)
                model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True), strict=True)
                model = model.cuda().eval()
                processed = 0
                def before_window(_module, _inputs):
                    nonlocal processed
                    management.throw_exception_if_processing_interrupted()
                    progress.update_absolute(min(processed, frames), frames)
                    processed += 22
                handle = model.register_forward_pre_hook(before_window)
                try:
                    with torch.inference_mode():
                        depths, _ = model.infer_video_depth(images, fps, input_size=518, device="cuda", fp32=False)
                finally:
                    handle.remove()
                valid = np.isfinite(depths) & (depths >= 0)
                inference = {"mode": "official overlapping-window", "window": 32, "overlap": 10, "input_size": 518,
                             "tail_context_padding": "upstream repeats the final frame only inside its fixed inference window; output is cropped to the original requested count"}
            else:
                from vigeo import ViGeo
                model = ViGeo.from_pretrained(str(checkpoint)).cuda().eval()
                parts, masks = [], []
                with torch.inference_mode():
                    window = frames if inference_mode == "offline" else 16
                    for start in range(0, frames, window):
                        management.throw_exception_if_processing_interrupted()
                        chunk = torch.from_numpy(images[start:start + window].copy()).permute(0, 3, 1, 2).float().div_(255)
                        prediction = model.infer(chunk, mode=inference_mode, chunk_size=16, num_tokens=1369, kv_caches=cache)
                        management.throw_exception_if_processing_interrupted()
                        cache = prediction["kv_caches"]
                        part = prediction["depth_pred"][:, 0].float().cpu().numpy()
                        mask = prediction.get("mask_pred")
                        valid_part = np.isfinite(part) & (part > 0)
                        if mask is not None:
                            valid_part &= mask[:, 0].cpu().numpy().astype(bool)
                        parts.append(part); masks.append(valid_part)
                        del prediction, chunk
                        progress.update_absolute(min(start + window, frames), frames)
                depths, valid = np.concatenate(parts), np.concatenate(masks)
                del parts, masks
                inference = {"mode": inference_mode, "chunk_size": 16 if inference_mode == "chunk" else None,
                             "offline_max_frames": 64, "num_tokens": 1369, "valid_region_head": True}
        finally:
            del model, cache
            torch.cuda.empty_cache()
        if not side_by_side:
            del images
        if depths.shape != (frames, height, width) or not valid.any():
            raise ValueError("The depth model did not return valid aligned predictions for every requested frame.")
        if any(not mask.any() for mask in valid):
            raise ValueError("At least one depth frame has no valid prediction; partial depth is not a successful render.")
        minimum = float(np.min(depths, where=valid, initial=np.inf))
        maximum = float(np.max(depths, where=valid, initial=-np.inf))
        span = maximum - minimum
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        stem += "_" + uuid.uuid4().hex[:10]
        preview, raw = output / (stem + "_depth-preview.mp4"), output / (stem + "_depth16.mkv")
        def preview_frames():
            import cv2
            palettes = {"turbo": cv2.COLORMAP_TURBO, "inferno": cv2.COLORMAP_INFERNO, "magma": cv2.COLORMAP_MAGMA, "viridis": cv2.COLORMAP_VIRIDIS}
            if colormap not in {"grayscale", *palettes}:
                raise ValueError("Choose a supported depth-preview colormap.")
            for index, (frame, mask) in enumerate(zip(depths, valid)):
                normalized = np.zeros_like(frame) if span <= 0 else np.nan_to_num((frame - minimum) / span).clip(0, 1)
                if PROFILES[profile]["semantics"] == "relative_depth":
                    normalized = 1 - normalized
                pixels = np.where(mask, np.rint(normalized * 255), 0).astype(np.uint8)
                rgb = np.repeat(pixels[..., None], 3, axis=2) if colormap == "grayscale" else cv2.cvtColor(cv2.applyColorMap(pixels, palettes[colormap]), cv2.COLOR_BGR2RGB)
                rgb[~mask] = 0
                yield np.concatenate((images[index], rgb), axis=1) if side_by_side else rgb
        preview_width = width * (2 if side_by_side else 1)
        encode_video(preview, preview_frames(), preview_width, height, fps, frames, source_audio=source if preserve_audio else None,
            trim_start=trim_start, encoding_quality=encoding_quality, check_cancelled=management.throw_exception_if_processing_interrupted)
        _encode_depth(raw, depths, valid, fps, minimum, maximum)
        progress.update_absolute(frames, frames)
        metadata = {"model_id": profile, "code_revision": PROFILES[profile]["commit"], "license": PROFILES[profile]["license"],
            "semantics": PROFILES[profile]["semantics"], "metric_units": False, "inference": inference,
            "frames": frames, "fps": fps, "trim_start": trim_start, "width": width, "height": height,
            "preview_width": preview_width, "preview_height": height, "colormap": colormap, "side_by_side": side_by_side,
            "encoding": "FFV1 gray16le", "invalid_code": 0, "minimum": minimum, "maximum": maximum,
            "decode_formula": "value = minimum + (code - 1) / 65534 * (maximum - minimum), for code > 0",
            "normalization": "one min/max pair across the whole selected clip, never per-frame",
            "preview": "8-bit display with near-high intensity before the chosen colormap; use the separate 16-bit stream and this mapping for compositing",
            "valid_fraction": float(valid.mean()), "flat_depth": span <= 0,
            "source_audio": bool(preserve_audio and info["has_audio"])}
        return {"ui": {"videos": [
            {"filename": preview.name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "role": "result"},
            {"filename": raw.name, "subfolder": "openframe", "type": "output", "format": "video/x-matroska", "role": "depth"}],
            "openframe_depth": [metadata]}, "result": (str(preview),)}
