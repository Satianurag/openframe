"""Geometric regression: python -m engine.tests.validate_mask_contour."""
import json
import cv2
import numpy as np
from custom_nodes.openframe.media import feather_mask as _feather_mask, prepare_masks


def edge_residual(alpha):
    x = np.arange(64, 448)
    crossing = np.argmax(alpha[:, x] < .5, axis=0)
    before, after = alpha[crossing - 1, x], alpha[crossing, x]
    y = crossing - 1 + (before - .5) / (before - after)
    line = np.polyval(np.polyfit(x, y, 1), x)
    return float(np.sqrt(np.mean((y - line) ** 2)))


def validate():
    yy, xx = np.mgrid[:256, :256]
    coarse = (yy < 90 + .16 * xx).astype(np.float32)
    mask = cv2.resize(coarse, (512, 512), interpolation=cv2.INTER_NEAREST)
    previous = _feather_mask(mask, 6, "inward")
    smooth = _feather_mask(mask, 6, "smooth-inward")
    before, after = edge_residual(previous), edge_residual(smooth)
    assert after < before * .25 and after < .1, (before, after)

    yy, xx = np.mgrid[:512, :512]
    detail = ((xx + yy) % 2).astype(np.float32)
    generated = np.stack([detail, 1 - detail, detail * .5], axis=-1)
    original = np.stack([xx / 512, yy / 512, np.full_like(xx, .3, dtype=float)], axis=-1)
    composite = generated * smooth[..., None] + original * (1 - smooth[..., None])
    np.testing.assert_array_equal(composite[mask == 0], original[mask == 0])
    np.testing.assert_array_equal(composite[smooth == 1], generated[smooth == 1])

    # A translating contour must translate its opacity, without frame pumping.
    errors = []
    for shift in range(1, 10):
        moved = np.pad(mask, ((shift, 0), (0, 0)), constant_values=1)[:512]
        alpha = _feather_mask(moved, 6, "smooth-inward")
        error = float(np.max(np.abs(alpha[64 + shift:400] - smooth[64:400 - shift])))
        assert error < 1e-6, error
        errors.append(error)

    # Small holes remain excluded and feathered; empty/full inputs stay exact.
    hole = np.ones((128, 128), np.float32)
    hole[63:65, 63:65] = 0
    alpha = _feather_mask(hole, 6, "smooth-inward")
    assert not alpha[63:65, 63:65].any()
    assert alpha[62, 63] == alpha[63, 62] == 0
    assert float(alpha[62:66, 62:66].max()) < .02
    for fill in (0, 1):
        constant = np.full((64, 64), fill, np.float32)
        np.testing.assert_array_equal(_feather_mask(constant, 6, "smooth-inward"), constant)
    np.testing.assert_array_equal(_feather_mask(mask, 0, "smooth-inward"), mask)
    # Existing saved graph modes retain their exact formulas.
    np.testing.assert_array_equal(_feather_mask(mask, 6, "gaussian"), cv2.GaussianBlur(mask, (13, 13), 0) * mask)
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    ramp = np.clip((distance - 1) / 6, 0, 1)
    np.testing.assert_array_equal(previous, ramp * ramp * (3 - 2 * ramp))
    # A tight tracked silhouette needs full edit opacity over its perimeter;
    # otherwise compositing restores the original object after inpainting.
    tracked = np.zeros((1, 256, 384), np.float32)
    tracked[:, 90:170, 90:290] = 1
    generation, blend = prepare_masks(tracked, 8, 6, "smooth-inward", edit_margin=12)
    assert float(blend[tracked == 1].min()) == 1
    allowed = cv2.dilate(tracked[0], np.ones((25, 25), np.uint8))
    assert not blend[0][allowed == 0].any()
    np.testing.assert_array_equal(generation[0], cv2.dilate(tracked[0], np.ones((41, 41), np.uint8)))
    legacy_gen, legacy_blend = prepare_masks(tracked, 8, 6, "smooth-inward")
    np.testing.assert_array_equal(legacy_blend[0], _feather_mask(tracked[0], 6, "smooth-inward"))
    np.testing.assert_array_equal(legacy_gen[0], cv2.dilate(tracked[0], np.ones((17, 17), np.uint8)))
    return {"legacy_edge_residual_px": before, "smooth_edge_residual_px": after,
            "moving_mask_max_opacity_error": max(errors), "outside_pixels_exact": True,
            "interior_checker_detail_exact": True, "legacy_modes_unchanged": True,
            "tracked_perimeter_fully_editable": True, "explicit_edit_support_preserved": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
