"""File-input adaptation of Sphere-Light-Render-ComfyUI's MIT PNG decoder.

Source: eric-venti-seeds/Sphere-Light-Render-ComfyUI at
cc89da68f898ddabb6fddbfb0781d3999550ac18, __init__.py:decode_render_b64.
Copyright 2026 Eric Venti and Christopher Connock. License: docs/licenses/sphere-light-MIT.txt.
The prepared browser PNG is explicit input; scalar angles do not render a sphere here.
"""
import hashlib
import numpy as np
import torch
from PIL import Image
import folder_paths


class OpenFrameRelightSphere:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/conditioning"

    @classmethod
    def IS_CHANGED(cls, filename):
        digest = hashlib.sha256()
        with open(folder_paths.get_annotated_filepath(filename), "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load(self, filename):
        if not filename:
            raise ValueError("Apply a lighting sphere before rendering.")
        with Image.open(folder_paths.get_annotated_filepath(filename)) as image:
            original_size = list(image.size)
            if max(image.size) > 2048:
                raise ValueError("The prepared lighting sphere exceeds the released decoder's 2048-pixel bound.")
            image = image.convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
            pixels = np.array(image).astype(np.float32) / 255.0
        return {"ui": {"openframe_relight_sphere": [{
            "sha256": self.IS_CHANGED(filename), "original_size": original_size,
            "decoded_size": [1024, 1024],
            "source_pin": "cc89da68f898ddabb6fddbfb0781d3999550ac18",
        }]}, "result": (torch.from_numpy(pixels).unsqueeze(0),)}
