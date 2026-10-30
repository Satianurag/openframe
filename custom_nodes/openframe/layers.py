"""Export native RGBA decomposition with explicit stack order and reconstruction evidence."""
from pathlib import Path
import uuid

import comfy.model_management
import folder_paths
import numpy as np
from PIL import Image, PngImagePlugin


class OpenFrameSaveLayers:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "source": ("IMAGE",),
                             "layer_count": ("INT", {"default": 4, "min": 2, "max": 8}),
                             "filename_prefix": ("STRING", {"default": "OpenFrame"})}}

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Image"

    def save(self, images, source, layer_count, filename_prefix):
        if images.shape[0] != layer_count + 1 or images.shape[-1] != 4:
            raise ValueError("Qwen layered output must contain one regenerated full image followed by the requested RGBA layers")
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        stem += "_" + uuid.uuid4().hex[:10]
        pixels = np.rint(images.detach().cpu().float().numpy().clip(0, 1) * 255).astype(np.uint8)
        full = Image.fromarray(pixels[0], "RGBA")
        stack = [Image.fromarray(frame, "RGBA") for frame in pixels[1:]]
        composite = Image.new("RGBA", full.size)
        for layer in stack:
            composite = Image.alpha_composite(composite, layer)
        outputs = []
        for index, (role, image) in enumerate([("result", composite), ("reconstruction", full), *[(f"layer-{i + 1}", layer) for i, layer in enumerate(stack)]]):
            comfy.model_management.throw_exception_if_processing_interrupted()
            name = f"{stem}_{role}.png"
            meta = PngImagePlugin.PngInfo()
            meta.add_text("openframe_role", role)
            meta.add_text("openframe_layer_order", "layer-1 is the backmost layer; increasing indices are composited over it")
            image.save(output / name, pnginfo=meta, compress_level=4)
            outputs.append({"filename": name, "subfolder": "openframe", "type": "output", "role": role})
        def premultiplied(image):
            value = np.asarray(image, dtype=np.float32) / 255
            return np.concatenate((value[..., :3] * value[..., 3:4], value[..., 3:4]), axis=-1)
        error = np.abs(premultiplied(composite) - premultiplied(full))
        source_pixels = source[0, ..., :3].detach().cpu().float().numpy()
        if source_pixels.shape[:2] != pixels.shape[1:3]:
            raise ValueError("Layer output geometry does not match the prepared source")
        return {"ui": {"images": outputs, "openframe_layers": [{
            "layer_count": layer_count, "width": full.width, "height": full.height,
            "stack_order": [f"layer-{i + 1}" for i in range(layer_count)],
            "ordering": "back-to-front", "alpha": "straight RGBA, 8-bit PNG",
            "reconstruction_mae_premultiplied_rgba": float(error.mean()),
            "source_mae_rgb": float(np.abs(np.asarray(composite.convert("RGB"), dtype=np.float32) / 255 - source_pixels).mean()),
            "source_preserved_exactly": False,
            "method": "Qwen-Image-Layered regenerates a full image and layers; it is not exact pixel segmentation. Entry zero is exported separately as reconstruction, never treated as a layer.",
        }]}}
