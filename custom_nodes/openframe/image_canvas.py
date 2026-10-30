"""Place an unchanged source image on a larger canvas for instruction editing."""

import math

import torch


class OpenFrameLoadImageMask:
    """Read mask values directly, avoiding video-decoder grayscale scaling."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("STRING", {"default": "mask.png"})}}

    RETURN_TYPES = ("MASK",)
    FUNCTION = "load_mask"
    CATEGORY = "OpenFrame/Image"

    @classmethod
    def IS_CHANGED(cls, image):
        import folder_paths
        import hashlib
        with open(folder_paths.get_annotated_filepath(image), "rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def load_mask(self, image):
        import folder_paths
        import numpy as np
        from PIL import Image, ImageOps
        with Image.open(folder_paths.get_annotated_filepath(image)) as opened:
            picture = ImageOps.exif_transpose(opened)
            if picture.mode in {"I", "I;16", "I;16B", "I;16L"}:
                values = np.asarray(picture).astype(np.float32) / 65535
            else:
                values = np.asarray(picture.convert("RGB"))[..., 0].astype(np.float32) / 255
        return (torch.from_numpy(values.clip(0, 1)).unsqueeze(0),)


class OpenFrameImageRegionInfo:
    """Record the external crop node's actual geometry without altering pixels."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "source": ("IMAGE",), "stitcher": ("STITCHER",),
                             "plugin_revision": ("STRING",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "record"
    CATEGORY = "OpenFrame/Image"
    OUTPUT_NODE = True

    def record(self, image, source, stitcher, plugin_revision):
        if image.shape[0] != 1 or source.shape[0] != 1:
            raise ValueError("Region focus requires one original image before batch sampling.")
        coordinates = {
            prefix: [int(stitcher[prefix + axis][0]) for axis in ("x", "y", "w", "h")]
            for prefix in ("cropped_to_canvas_", "canvas_to_orig_")
        }
        record = {
            "mode": "masked-region", "source_width": source.shape[2], "source_height": source.shape[1],
            "sampling_width": image.shape[2], "sampling_height": image.shape[1],
            "crop_in_context_canvas_xywh": coordinates["cropped_to_canvas_"],
            "original_in_context_canvas_xywh": coordinates["canvas_to_orig_"],
            "context_factor": 1.2, "original_preresized": False,
            "generated_region_resized_back": True, "stitch_blend_pixels": stitcher["blend_pixels"],
            "upscale_algorithm": stitcher["upscale_algorithm"], "downscale_algorithm": stitcher["downscale_algorithm"],
            "repository": "https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch",
            "required_revision": plugin_revision, "license": "GPL-3.0",
        }
        return {"ui": {"openframe_image_region": [record]}, "result": (image,)}


class OpenFrameImageEditCanvas:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "mask": ("MASK",),
                             "width": ("INT", {"default": 1024, "min": 64, "max": 4096, "step": 16}),
                             "height": ("INT", {"default": 1024, "min": 64, "max": 4096, "step": 16}),
                             "preservation": (["outside-mask", "inside-mask"],)}}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("padded_source", "editable_region")
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/Image"

    def prepare(self, image, mask, width, height, preservation):
        if image.ndim != 4 or image.shape[0] != 1 or mask.ndim != 3 or mask.shape[0] != 1:
            raise ValueError("Image preservation requires one source image and one matching mask.")
        h, w = image.shape[1:3]
        if tuple(mask.shape[-2:]) != (h, w) or (width, height) != (((w + 15) // 16) * 16, ((h + 15) // 16) * 16):
            raise ValueError("Preservation keeps native source geometry and pads only to the 16-pixel model grid.")
        if preservation not in {"outside-mask", "inside-mask"}:
            raise ValueError("Choose which side of the painted mask to preserve.")
        padded = image.new_full((1, height, width, 3), .5)
        padded[:, :h, :w] = image[..., :3]
        editable = image.new_ones((1, height, width))
        selected = mask.to(image).clamp(0, 1)
        editable[:, :h, :w] = selected if preservation == "outside-mask" else 1 - selected
        return padded, editable


class OpenFrameExpandImageCanvas:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 1536, "min": 256, "max": 4096, "step": 16}),
                "height": ("INT", {"default": 1024, "min": 256, "max": 4096, "step": 16}),
                "anchor_x": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "anchor_y": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
            "optional": {"source_alpha": ("MASK",)},
        }

    RETURN_TYPES = ("IMAGE", "MASK", "MASK")
    RETURN_NAMES = ("padded_source", "protected_original", "padded_inverse_alpha")
    FUNCTION = "expand"
    CATEGORY = "OpenFrame/Image"
    OUTPUT_NODE = True

    def expand(self, image, width, height, anchor_x, anchor_y, source_alpha=None):
        if image.ndim != 4 or image.shape[0] != 1 or image.shape[-1] < 3:
            raise ValueError("Expand Image requires one original RGB image.")
        source_height, source_width = image.shape[1:3]
        if not (256 <= width <= 4096 and 256 <= height <= 4096) or width % 16 or height % 16:
            raise ValueError("Use a 16-pixel aligned canvas from 256 to 4096 pixels per side.")
        if width < source_width or height < source_height or (width == source_width and height == source_height):
            raise ValueError("The expanded canvas must contain the unchanged original and add space on at least one axis.")
        if not (math.isfinite(anchor_x) and math.isfinite(anchor_y) and 0 <= anchor_x <= 1 and 0 <= anchor_y <= 1):
            raise ValueError("Image placement anchors must be between zero and one.")

        left = math.floor((width - source_width) * anchor_x + 0.5)
        top = math.floor((height - source_height) * anchor_y + 0.5)
        right, bottom = left + source_width, top + source_height
        # This canvas is a conditioning image, not generated evidence. No resize,
        # blend or colour transform touches the original decoded pixel values.
        padded = image.new_full((1, height, width, 3), 0.5)
        padded[:, top:bottom, left:right] = image[..., :3]
        protected = image.new_zeros((1, height, width))
        protected[:, top:bottom, left:right] = 1
        inverse_alpha = image.new_ones((1, height, width))
        inverse_alpha[:, top:bottom, left:right] = 0
        alpha_supplied = source_alpha is not None and tuple(source_alpha.shape[-2:]) == (source_height, source_width)
        if alpha_supplied:
            inverse_alpha[:, top:bottom, left:right] = source_alpha[:1].to(image).clamp(0, 1)
        elif source_alpha is not None and torch.any(source_alpha != 0):
            # Comfy LoadImage returns an all-zero placeholder for opaque inputs.
            # A nonzero, differently sized alpha cannot safely be discarded.
            raise ValueError("The source alpha must match the original image dimensions.")

        record = {
            "operation": "expand-image",
            "source_width": source_width,
            "source_height": source_height,
            "output_width": width,
            "output_height": height,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "original_bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
            "padding": {"left": left, "top": top, "right": width - right, "bottom": height - bottom},
            "source_resampled": False,
            "source_alpha_supplied": alpha_supplied,
            "conditioning_background_rgb": [0.5, 0.5, 0.5],
            "preservation": "inside-mask",
            "feather": 0,
            "method": "instruction-conditioned generation followed by original-pixel compositing",
        }
        return {"ui": {"openframe_canvas": [record]}, "result": (padded, protected, inverse_alpha)}
