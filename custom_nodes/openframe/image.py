"""FLUX3 prompt preparation and explicit original-pixel image preservation.

No alternate inference service: CLIP.generate/tokenize are ComfyUI's native
Qwen3.5 implementation, using the selected pinned prompt-upsample checkpoint.
"""
import json
from pathlib import Path
import uuid

import numpy as np
from PIL import Image, PngImagePlugin
import folder_paths
import comfy.model_management
from .media import feather_mask
from .image_seams import harmonize_outpaint


CAPTION_SYSTEM = """Expand the user's image request into one detailed English scene caption for an image model. Preserve every explicit subject, count, position, constraint, style and exact wording. Write one concrete plan without alternatives, commentary, Markdown or JSON. Start with medium/style, then scene, light and camera, then subjects with observable colours, materials, clothing and frame-relative positions. Do not invent brands, logos, names or unrequested text. Keep requested text verbatim in quotes and its original language. Avoid inferring ethnicity, nationality, religion or other sensitive traits from appearance. Use concrete visual details instead of quality adjectives. Typical length 100–350 words. If reference images are supplied, they are attached in order: first is ref_image_0, then ref_image_1, and so forth. For a bounded edit, describe the requested end state, shadows/reflections and what remains unchanged. For multi-reference composition, identify exactly what to take from each reference by ordinal and preserve its visible distinguishing details. Do not replace the user's subjects. Layout elements, if given, are constraints: preserve their IDs when citing them as <id>, but do not output coordinates or a JSON table; the application appends the unchanged table after your caption. Output only the caption."""


class OpenFrameFlux3Prompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"request": ("STRING", {"multiline": True}), "mode": (["expand", "caption"],),
                             "width": ("INT", {"default": 1024, "min": 64, "max": 4096}),
                             "height": ("INT", {"default": 1024, "min": 64, "max": 4096}),
                             "layout_json": ("STRING", {"default": "[]", "multiline": True})},
                "optional": {"clip": ("CLIP",), **{f"image_{i}": ("IMAGE",) for i in range(10)}}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/Image"
    OUTPUT_NODE = True

    def prepare(self, request, mode, width, height, layout_json="[]", clip=None, **kwargs):
        elements = json.loads(layout_json)
        if not isinstance(elements, list) or len(elements) > 32:
            raise ValueError("Use at most 32 layout elements.")
        images = [kwargs[f"image_{i}"][:1] for i in range(10) if kwargs.get(f"image_{i}") is not None]
        if mode == "expand":
            if clip is None:
                raise ValueError("The FLUX3 prompt-upsample model is required. No raw-prompt fallback is used.")
            prompt = f"TARGET CANVAS: {width}:{height}\n{request}"
            if elements:
                prompt += "\nLayout constraints: " + json.dumps(elements, ensure_ascii=False)
            comfy.model_management.throw_exception_if_processing_interrupted()
            # Native tokenizer accepts differently sized IMAGE tensors via images;
            # do not concatenate/stretch multiple references into one image.
            tokens = clip.tokenize(prompt, images=images, min_length=1, thinking=False, system_prompt=CAPTION_SYSTEM)
            generated = clip.generate(tokens, do_sample=False, max_length=3584, repetition_penalty=1.0, mtp=False)
            caption = clip.decode(generated).strip()
            if "</think>" in caption:
                caption = caption.partition("</think>")[2].strip()
            if caption.startswith("<think>") or not caption or len(caption) > 20000:
                raise ValueError("Prompt expansion returned no usable caption; generation was stopped.")
        elif mode == "caption":
            caption = request.strip()
            if len(caption) < 80:
                raise ValueError("Provide a complete caption of at least 80 characters, or enable prompt expansion.")
        else:
            raise ValueError("Unknown prompt mode.")
        rows = []
        for element in elements:
            row = {"id": element["id"], "desc": element["description"]}
            if element.get("bbox") is not None:
                row["bbox"] = element["bbox"]
            else:
                ref = element.get("source_reference")
                row.update({"from": f"ref_image_{ref}" if ref is not None else None,
                            "src_bbox": element.get("source_bbox"), "tgt_bbox": element.get("target_bbox")})
            rows.append(row)
        final = caption + (" " + json.dumps(rows, ensure_ascii=False) if rows else "")
        record = {"original": request, "expanded": caption, "model_prompt": final, "mode": mode,
                  "layout": rows, "reference_count": len(images), "expander": "native Comfy Qwen3.5 FLUX3 prompt upsampler" if mode == "expand" else None,
                  "system_prompt": CAPTION_SYSTEM if mode == "expand" else None, "max_tokens": 3584 if mode == "expand" else None,
                  "sampling": "greedy, thinking off, MTP off" if mode == "expand" else None}
        return {"ui": {"text": [final], "openframe_prompt": [record]}, "result": (final,)}


class OpenFrameSaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "caption": ("STRING", {"forceInput": True}),
                             "filename_prefix": ("STRING", {"default": "OpenFrame"}),
                             "preservation": (["none", "outside-mask", "inside-mask"],),
                             "feather": ("INT", {"default": 8, "min": 0, "max": 32})},
                "optional": {"source": ("IMAGE",), "source_alpha": ("MASK",), "mask": ("MASK",),
                             "harmonize_outside": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Image"

    def save(self, images, caption, filename_prefix, preservation="none", feather=8, source=None, source_alpha=None, mask=None, harmonize_outside=False):
        import torch
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        source_pixels = edit_alpha = original_alpha = None
        if harmonize_outside and (preservation != "inside-mask" or feather != 0):
            raise ValueError("Outside colour continuity requires exact original-rectangle preservation with zero feather.")
        if preservation != "none":
            if preservation not in {"inside-mask", "outside-mask"} or source is None or mask is None:
                raise ValueError("Image preservation requires a source and matching painted mask.")
            source_pixels = source[0, ..., :3].detach().cpu().float().numpy()
            selected = mask[0].detach().cpu().float().numpy().clip(0, 1)
            if selected.shape != source_pixels.shape[:2]:
                raise ValueError("The painted image mask must match the original source dimensions exactly.")
            edit_alpha = selected if preservation == "outside-mask" else 1 - selected
            edit_alpha = feather_mask(edit_alpha, feather, "smooth-inward")
            if source_alpha is not None and source_alpha.shape[-2:] == source.shape[1:3]:
                original_alpha = 1 - source_alpha[0].detach().cpu().float().numpy()
        saved, returned, seam_records = [], [], []
        for index, frame in enumerate(images):
            comfy.model_management.throw_exception_if_processing_interrupted()
            pixels = frame[..., :3].detach().cpu().float().numpy().clip(0, 1)
            alpha = None
            if source_pixels is not None:
                height, width = source_pixels.shape[:2]
                if pixels.shape[0] < height or pixels.shape[1] < width or pixels.shape[0] - height >= 16 or pixels.shape[1] - width >= 16:
                    raise ValueError("Pixel preservation requires an original-size canvas padded only to the model's 16-pixel grid.")
                pixels = pixels[:height, :width]
                if harmonize_outside:
                    pixels, seam_record = harmonize_outpaint(pixels, source_pixels, 1 - edit_alpha, original_alpha,
                                                             comfy.model_management.throw_exception_if_processing_interrupted)
                    seam_records.append(seam_record)
                pixels = pixels * edit_alpha[..., None] + source_pixels * (1 - edit_alpha[..., None])
                # Exact source values regardless of outside colour correction.
                # Neither source pixels nor generated texture are resampled.
                pixels[edit_alpha == 0] = source_pixels[edit_alpha == 0]
                if original_alpha is not None and np.any(original_alpha < 1):
                    alpha = original_alpha * (1 - edit_alpha) + edit_alpha
            rgb = np.rint(pixels * 255).clip(0, 255).astype(np.uint8)
            rgba = np.dstack((rgb, np.rint(alpha * 255).clip(0, 255).astype(np.uint8))) if alpha is not None else rgb
            name = f"{stem}_{index:02d}_{uuid.uuid4().hex[:10]}.png"
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("openframe_caption", caption)
            Image.fromarray(rgba).save(output / name, pnginfo=metadata, compress_level=4)
            saved.append({"filename": name, "subfolder": "openframe", "type": "output", "role": "result"})
            returned.append(torch.from_numpy(rgb.astype(np.float32) / 255))
        return {"ui": {"images": saved, "openframe_image": [{"preservation": preservation, "feather": feather,
                    "protected_pixels": "original decoded RGB (and alpha when supplied)" if preservation != "none" else None,
                    "source_resampled": False if preservation != "none" else None,
                    "outside_colour_continuity": seam_records or None,
                    "output_width": returned[0].shape[1], "output_height": returned[0].shape[0]}]},
                "result": (torch.stack(returned),)}
