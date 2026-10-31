"""Compose ordered still references into the single sheet the Ingredients IC-LoRA expects."""
import math

import torch
import torch.nn.functional as F


def _fit(image, cell_width, cell_height):
    """Fit one still into a cell without cropping or changing its aspect ratio."""
    source = image[:1, ..., :3]
    height, width = source.shape[1:3]
    scale = min(cell_width / width, cell_height / height)
    target_width = max(1, min(cell_width, round(width * scale)))
    target_height = max(1, min(cell_height, round(height * scale)))
    mode = "area" if target_width < width or target_height < height else "bilinear"
    resized = F.interpolate(source.movedim(-1, 1), size=(target_height, target_width),
                            mode=mode, align_corners=False if mode == "bilinear" else None)
    return resized.movedim(1, -1).clamp(0, 1)


class OpenFrameReferenceSheet:
    """Tile up to nine ordered reference images into one left-to-right sheet.

    The official LTX 2.5 Ingredients workflow expects one sheet, repeated on
    every frame as the IC-LoRA guide. References are row-major, preserving the
    caller's order. Each still is letterboxed inside an equal cell so neither
    its framing nor its aspect ratio is cropped.
    """
    @classmethod
    def INPUT_TYPES(cls):
        optional = {f"image_{index}": ("IMAGE",) for index in range(1, 10)}
        optional.update({
            "width": ("INT", {"default": 0, "min": 0, "max": 4096}),
            "height": ("INT", {"default": 0, "min": 0, "max": 4096}),
            "gap": ("INT", {"default": 8, "min": 0, "max": 64}),
            "background": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
        })
        return {"required": {"columns": ("INT", {"default": 3, "min": 1, "max": 9})},
                "optional": optional}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("reference_sheet",)
    FUNCTION = "compose"
    CATEGORY = "OpenFrame/Video"

    def compose(self, columns, width=0, height=0, gap=8, background=1.0, **images):
        ordered = [images.get(f"image_{index}") for index in range(1, 10)]
        ordered = [image for image in ordered if image is not None]
        if not ordered:
            raise ValueError("The reference sheet needs at least one image.")
        if len(ordered) > 9:
            raise ValueError("The reference sheet accepts at most nine images.")
        if any(image.ndim != 4 or image.shape[0] < 1 for image in ordered):
            raise ValueError("Each reference must be a non-empty IMAGE batch.")
        columns = max(1, min(int(columns), len(ordered)))
        rows = math.ceil(len(ordered) / columns)
        gap = max(0, int(gap))
        if width <= 0 or height <= 0:
            cell_width = max(int(image.shape[2]) for image in ordered)
            cell_height = max(int(image.shape[1]) for image in ordered)
            width = columns * cell_width + (columns - 1) * gap
            height = rows * cell_height + (rows - 1) * gap
        width, height = int(width), int(height)
        if width <= 0 or height <= 0:
            raise ValueError("The reference sheet needs a positive output size.")
        cell_width = max(1, (width - (columns - 1) * gap) // columns)
        cell_height = max(1, (height - (rows - 1) * gap) // rows)
        sheet = torch.full((1, height, width, 3), float(background),
                           dtype=ordered[0].dtype, device=ordered[0].device)
        for index, image in enumerate(ordered):
            row, column = divmod(index, columns)
            fitted = _fit(image.to(device=sheet.device, dtype=sheet.dtype), cell_width, cell_height)
            x = column * (cell_width + gap) + (cell_width - fitted.shape[2]) // 2
            y = row * (cell_height + gap) + (cell_height - fitted.shape[1]) // 2
            sheet[:, y:y + fitted.shape[1], x:x + fitted.shape[2], :] = fitted
        return (sheet,)
