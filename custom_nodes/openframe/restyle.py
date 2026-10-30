"""Bounded Canny annotator adapted from comfyui_controlnet_aux (Apache-2.0).

Upstream a587a4c1594524c1d2de5cd1a86cd868ff448e1c:
src/custom_controlnet_aux/canny/__init__.py, util.py:resize_image_with_pad,
utils.py:common_annotator_call. See CANNY_LICENSE.txt.
Changes: RGB tensor inputs only, cancellation, bounded allocation and provenance.
The detector's resize, edge padding, uint8 conversion and cv2.Canny are retained.
"""
import hashlib

import cv2
import numpy as np
import torch
import comfy.model_management


class OpenFrameCannyGuide:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",),
                "low_threshold": ("INT", {"default": 92, "min": 0, "max": 255}),
                "high_threshold": ("INT", {"default": 200, "min": 1, "max": 255}),
                "resolution": ("INT", {"default": 512, "min": 64, "max": 1024, "step": 64})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "edges"
    CATEGORY = "OpenFrame/VFX"

    def edges(self, images, low_threshold=92, high_threshold=200, resolution=512):
        if not 0 <= low_threshold < high_threshold <= 255:
            raise ValueError("Canny thresholds must satisfy 0 <= low < high <= 255.")
        frames, height, width = images.shape[:3]
        if not 1 <= frames <= 241 or not 64 <= resolution <= 1024:
            raise ValueError("The Canny guide supports 1–241 frames and 64–1024 detection resolution.")
        scale = resolution / min(height, width)
        th, tw = int(np.round(height * scale)), int(np.round(width * scale))
        if frames * th * tw * 3 * 4 > 2 * 1024**3:
            raise ValueError("Canny guide tensor exceeds the bounded 2 GiB allocation; shorten the clip.")
        result = torch.empty((frames, th, tw, 3), dtype=torch.float32, device="cpu")
        source_hash, guide_hash = hashlib.sha256(), hashlib.sha256()
        for i, frame in enumerate(images):
            comfy.model_management.throw_exception_if_processing_interrupted()
            rgb = np.asarray(frame.detach().cpu()[..., :3] * 255.0, dtype=np.uint8)
            source_hash.update(rgb.tobytes())
            resized = cv2.resize(rgb, (tw, th), interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
            padded = np.pad(resized, ((0, (-th) % 64), (0, (-tw) % 64), (0, 0)), mode="edge")
            edge = cv2.Canny(padded, low_threshold, high_threshold)[:th, :tw].copy()
            guide_hash.update(edge.tobytes())
            result[i] = torch.from_numpy(np.repeat(edge[..., None], 3, axis=2).astype(np.float32) / 255.0)
        metadata = {"method": "canny", "implementation": "comfyui_controlnet_aux", "commit": "a587a4c1594524c1d2de5cd1a86cd868ff448e1c",
                    "low_threshold": low_threshold, "high_threshold": high_threshold, "detection_resolution": resolution,
                    "frames": frames, "input_size": [width, height], "guide_size": [tw, th],
                    "input_rgb_sha256": source_hash.hexdigest(), "guide_gray_sha256": guide_hash.hexdigest()}
        return {"ui": {"openframe_restyle_control": [metadata]}, "result": (result,)}


class OpenFrameRestyleFirstFrame:
    """Fit a reviewed full native frame using the source decoder's exact geometry."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("STRING",), "source_filename": ("STRING",),
                "width": ("INT", {"min": 256, "max": 1920}),
                "height": ("INT", {"min": 256, "max": 1920}),
                "fps": ("FLOAT", {"min": 1, "max": 120})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/VFX"

    def prepare(self, image, source_filename, width, height, fps):
        from .nodes import _input_path
        from .transitions import _info, _hash
        from .media import decode_frames
        image_path, source_path = _input_path(image), _input_path(source_filename)
        reference, source = _info(image_path), _info(source_path)
        if (reference["kind"] != "image" or source["kind"] != "video" or
                (reference["width"], reference["height"]) != (source["width"], source["height"])):
            raise ValueError("The edited first-frame reference must be an image matching the source video's native dimensions.")
        fitted = decode_frames(image_path, width, height, fps, 1)
        metadata = {"role": "edited-first-frame", "input_size": [reference["width"], reference["height"]],
                    "fitted_size": [width, height], "image_sha256": _hash(image_path),
                    "fitted_rgb_sha256": hashlib.sha256(fitted.tobytes()).hexdigest(),
                    "fit": "same FFmpeg scale-increase/center-crop as the source video",
                    "later_identity_guaranteed": False}
        return {"ui": {"openframe_restyle_reference": [metadata]},
                "result": (torch.from_numpy(fitted.astype(np.float32) / 255.0),)}
