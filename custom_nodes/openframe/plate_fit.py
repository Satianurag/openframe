"""PaintAPlate color seam-field reuse, Apache-2.0.

Source: AInVFX/ainvfx-paintaplate, mathops.py, commit below.
The five mathematical helpers are copied unchanged. Our wrapper replaces the
full-frame result list with a bounded iterator, preserves the caller's exact
mask, and omits alignment/grain/mask expansion. See PAINTAPLATE_LICENSE.txt.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

UPSTREAM_REVISION = "31adafa85819b616c4f157dc88e6a96f5b9cfd9a"
UPSTREAM_SOURCE = "https://github.com/AInVFX/ainvfx-paintaplate/blob/" + UPSTREAM_REVISION + "/mathops.py"

def shrink(img: np.ndarray, f: int) -> np.ndarray:
    """Box average by an integer factor `f` over the first two axes; the edges are cropped to a multiple of f."""
    if f <= 1:
        return img
    h, w = img.shape[0] // f * f, img.shape[1] // f * f
    x = img[:h, :w]
    return x.reshape(h // f, f, w // f, f, *x.shape[2:]).mean((1, 3))


def _axis_taps(n_in: int, n_out: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For each output index along one axis: the two input indices to blend and the weight of the second."""
    src = np.clip((np.arange(n_out, dtype=np.float64) + 0.5) * (n_in / n_out) - 0.5, 0, n_in - 1)
    i0 = np.floor(src).astype(np.intp)
    return i0, np.minimum(i0 + 1, n_in - 1), (src - i0).astype(np.float32)


def resize_to(img: np.ndarray, h: int, w: int) -> np.ndarray:
    """Resample the first two axes to exactly (h, w): separable bilinear, pixel centres aligned, edges clamped.

    The same result as scipy's zoom (order 1, grid_mode) and torch's bilinear interpolate without align_corners,
    in a quarter of the time: two gathers and two blends in numpy, no spline machinery. Enlarging the masks and
    colour fields to full size was the composite's largest cost.
    """
    if img.shape[:2] == (h, w):
        return img
    x = img.astype(np.float32, copy=False)
    if x.shape[0] != h:
        i0, i1, wy = _axis_taps(x.shape[0], h)
        wy = wy.reshape((-1,) + (1,) * (x.ndim - 1))
        x = x[i0] * (1.0 - wy) + x[i1] * wy
    if x.shape[1] != w:
        j0, j1, wx = _axis_taps(x.shape[1], w)
        wx = wx.reshape((1, -1) + (1,) * (x.ndim - 2))
        x = x[:, j0] * (1.0 - wx) + x[:, j1] * wx
    return x


def push_pull(values: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """Fill a (H, W, C) field where `weight` (H, W, 0 to 1) is zero, from the values around it.

    Weighted averages at coarser and coarser scales are blended back where the weight
    is low, so a hole takes a smooth interpolation of its border.
    """
    levels = []
    v, w = values * weight[..., None], weight.astype(np.float32)
    while min(v.shape[:2]) > 1:
        levels.append((v, w))
        ph, pw = v.shape[0] % 2, v.shape[1] % 2
        if ph or pw:
            v = np.pad(v, ((0, ph), (0, pw), (0, 0)), mode="edge")
            w = np.pad(w, ((0, ph), (0, pw)), mode="edge")
        v = v.reshape(v.shape[0] // 2, 2, v.shape[1] // 2, 2, -1).sum((1, 3))
        w = w.reshape(w.shape[0] // 2, 2, w.shape[1] // 2, 2).sum((1, 3))
    fill = v / np.maximum(w, 1e-6)[..., None]
    for lv, lw in reversed(levels):
        up = resize_to(fill, lv.shape[0], lv.shape[1])
        a = np.clip(lw, 0.0, 1.0)[..., None]
        fill = lv / np.maximum(lw, 1e-6)[..., None] * a + up * (1.0 - a)
    return fill


def seam_field(plate: np.ndarray, gen: np.ndarray, mask: np.ndarray, band: float) -> np.ndarray:
    """Log ratio (H, W, 3) that brings `gen` to the colour and exposure of `plate` at the edge of `mask`.

    It is measured on a ring just outside the mask, where the composite shows the plate, and
    spread smoothly inside it, as a Poisson blend would: colour and exposure drift are fixed,
    texture is left alone. Work at low resolution: the field is smooth by design.
    """
    outside = mask < 0.02
    if outside.all() or not outside.any():
        return np.zeros(plate.shape[:2] + (3,), np.float32)
    ring = outside & (ndimage.distance_transform_edt(outside) <= band)
    if ring.sum() < 16:
        return np.zeros(plate.shape[:2] + (3,), np.float32)
    d = np.log(np.maximum(plate[..., :3], 1e-4)) - np.log(np.maximum(gen[..., :3], 1e-4))
    lo, hi = np.percentile(d[ring], [10, 90], axis=0)  # another object crossing the ring must not pull the field
    field = push_pull(np.clip(d, lo, hi).astype(np.float32), ring.astype(np.float32))
    field = ndimage.gaussian_filter(field, (band / 2.0, band / 2.0, 0))
    return np.clip(field, -0.4, 0.4).astype(np.float32)


def fit_plate_frames(count, height, width, generated_at, original_at, mask_at,
                     check_cancelled=lambda: None):
    """Yield corrected generated RGB. Caller composites the ORIGINAL alpha once.

    Adapted from PaintAPlate fit_to_plate: unchanged seam-field mathematics,
    fixed radius-2 temporal smoothing, and a bounded sequential measurement pass.
    Deliberately excludes alignment, new grain, mask growth and mask feathering.
    """
    if not 1 <= count <= 241 or not 1 <= min(height, width) <= max(height, width) <= 2048:
        raise ValueError("Plate fitting supports 1–241 frames, up to 2048 pixels per side.")
    lo = max(1, round(max(height, width) / 480))
    hl, wl = max(1, height // lo), max(1, width // lo)
    if count * hl * wl * 3 * 4 > 768 * 1024 * 1024:
        raise ValueError("The plate-fitting low-resolution field exceeds its memory limit.")
    fields = np.empty((count, hl, wl, 3), np.float32)
    # Author's default seam ring: (grow 8 + feather 12)/scale, min 4.
    # This is a measurement width only; our caller's mask is NOT expanded.
    band = max(4.0, 20.0 / lo)
    for index in range(count):
        check_cancelled()
        generated = np.asarray(generated_at(index), np.float32)
        original = np.asarray(original_at(index), np.float32)
        mask = np.asarray(mask_at(index), np.float32)
        if generated.shape != (height, width, 3) or original.shape != generated.shape or mask.shape != (height, width):
            raise ValueError("Plate fitting requires source, generation and mask at the same frame geometry.")
        fields[index] = seam_field(shrink(original, lo), shrink(generated, lo),
                                   resize_to(mask, hl, wl), band)
    check_cancelled()
    ndimage.uniform_filter1d(fields, 5, axis=0, mode="nearest", output=fields)
    for index in range(count):
        check_cancelled()
        generated = np.array(generated_at(index), np.float32, copy=True)
        ys, xs = np.nonzero(np.asarray(mask_at(index)) > 1.0 / 1024)
        if len(ys):
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            generated[y0:y1, x0:x1] *= np.exp(resize_to(fields[index], height, width)[y0:y1, x0:x1])
        yield generated


class OpenFrameFitPlate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "source": ("IMAGE",), "mask": ("MASK",)}}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("corrected_generation",)
    FUNCTION = "fit"
    CATEGORY = "OpenFrame/finishing"

    def fit(self, images, source, mask):
        import torch
        import comfy.model_management
        count, height, width, _ = images.shape
        if len(source) != count or len(mask) != count:
            raise ValueError("Plate fitting requires equal source, generated and mask frame counts.")
        generated = images.detach().cpu().numpy()
        original = source.detach().cpu().numpy()
        alpha = mask.detach().cpu().numpy()
        result = torch.empty_like(images, device="cpu")
        for index, frame in enumerate(fit_plate_frames(count, height, width,
                lambda i: generated[i], lambda i: original[i], lambda i: alpha[i],
                comfy.model_management.throw_exception_if_processing_interrupted)):
            result[index].copy_(torch.from_numpy(frame))
        return {"ui": {"openframe_plate_fit": [{
                    "method": "PaintAPlate bounded seam field", "upstream_revision": UPSTREAM_REVISION,
                    "upstream_source": UPSTREAM_SOURCE, "license": "Apache-2.0",
                    "frames": count, "measurement_long_side": 480, "log_ratio_bound": .4,
                    "temporal_radius": 2, "alignment": False, "grain": False,
                    "mask_changed": False, "output_is_composited": False,
                    "final_alpha_composite": "performed once by the downstream saver"}]},
                "result": (result,)}
