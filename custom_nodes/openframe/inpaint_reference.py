"""Source-aligned image input for the official LTX inpainting start-frame branch."""
import hashlib
import numpy as np
import torch


class OpenFrameInpaintFirstFrame:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("STRING",), "source_filename": ("STRING",),
            "width": ("INT", {"min": 256, "max": 1920}),
            "height": ("INT", {"min": 256, "max": 1920}),
            "fps": ("FLOAT", {"min": 1, "max": 120}),
            "trim_start": ("FLOAT", {"min": 0, "default": 0})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/VFX"

    def prepare(self, image, source_filename, width, height, fps, trim_start):
        from PIL import Image
        from .nodes import _input_path
        from .transitions import _info, _hash
        from .media import decode_frames
        image_path, source_path = _input_path(image), _input_path(source_filename)
        reference, source = _info(image_path), _info(source_path)
        if (reference["kind"] != "image" or source["kind"] != "video" or
                (reference["width"], reference["height"]) != (source["width"], source["height"])):
            raise ValueError("Inpainting needs an edited full starting frame matching the source video's native dimensions.")
        with Image.open(image_path) as picture:
            if picture.convert("RGBA").getextrema()[3][0] < 255:
                raise ValueError("The edited starting frame must be fully opaque, including its unchanged background.")
        fitted = decode_frames(image_path, width, height, fps, 1)
        metadata = {"role": "edited-first-frame", "input_size": [reference["width"], reference["height"]],
            "fitted_size": [width, height], "image_sha256": _hash(image_path),
            "fitted_rgb_sha256": hashlib.sha256(fitted.tobytes()).hexdigest(),
            "source_start_seconds": trim_start, "output_frame_index": 0,
            "fit": "same FFmpeg scale-increase/center-crop as the source video",
            "alignment_contract": "full edited frame at the selected source trim; dimensions checked, semantic correspondence requires review",
            "later_identity_guaranteed": False}
        return {"ui": {"openframe_inpaint_reference": [metadata]},
            "result": (torch.from_numpy(fitted.astype(np.float32) / 255.0),)}
