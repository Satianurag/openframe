"""CPU invariants for outside-only colour continuity, without model inference."""
import importlib.util
from pathlib import Path
from unittest import TestCase
import numpy as np

_spec = importlib.util.spec_from_file_location('image_seams', Path(__file__).parents[2] / 'custom_nodes/openframe/image_seams.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
harmonize = _module.harmonize_outpaint


class OutpaintColourContinuity(TestCase):
    def fixture(self, left=24, top=20):
        y, x = np.mgrid[:80, :96]
        pixels = np.stack((.35 + .001 * x, .4 + .001 * y, .45 + .0004 * x), axis=-1).astype(np.float32)
        pixels += ((x + y) % 2)[..., None] * .015
        mask = np.zeros((80, 96), np.float32)
        mask[top:top + 40, left:left + 48] = 1
        generated = pixels.copy()
        generated[mask == 0] += np.array([.08, -.04, .06], np.float32)
        return generated, pixels, mask

    def test_all_anchors_preserve_original_and_remain_finite(self):
        for left in (0, 24, 48):
            for top in (0, 20, 40):
                with self.subTest(left=left, top=top):
                    generated, source, mask = self.fixture(left, top)
                    result, record = harmonize(generated, source, mask)
                    np.testing.assert_array_equal(result[mask == 1], source[mask == 1])
                    self.assertTrue(np.isfinite(result).all())
                    self.assertGreaterEqual(float(result.min()), 0)
                    self.assertLessEqual(float(result.max()), 1)
                    self.assertEqual(record['original_pixels_modified'], 0)

    def test_tonal_step_reduces_without_erasing_generated_texture(self):
        generated, source, mask = self.fixture()
        result, _ = harmonize(generated, source, mask)
        before = abs(generated[24:56, 23] - source[24:56, 23]).mean()
        after = abs(result[24:56, 23] - source[24:56, 23]).mean()
        self.assertLess(after, before * .15)
        def checker(pixels):
            p = pixels[32:48, 4:20]
            return (p[::2, ::2] - p[::2, 1::2] - p[1::2, ::2] + p[1::2, 1::2]) / 4
        np.testing.assert_allclose(checker(result), checker(generated), atol=.0005)

    def test_hidden_rgb_does_not_colour_surroundings(self):
        generated, source, mask = self.fixture()
        result, _ = harmonize(generated, source, mask, np.zeros(mask.shape, np.float32))
        np.testing.assert_array_equal(result[mask == 0], generated[mask == 0])
        np.testing.assert_array_equal(result[mask == 1], source[mask == 1])

    def test_partial_alpha_scales_correction_without_changing_source(self):
        generated, source, mask = self.fixture()
        full, _ = harmonize(generated, source, mask)
        half, _ = harmonize(generated, source, mask, np.full(mask.shape, .5, np.float32))
        np.testing.assert_array_equal(half[mask == 1], source[mask == 1])
        np.testing.assert_allclose((half - generated)[mask == 0], .5 * (full - generated)[mask == 0], atol=.0001)

    def test_tiny_padding_and_single_pixel_source(self):
        generated = np.full((3, 3, 3), .4, np.float32)
        source = np.full_like(generated, .5)
        mask = np.zeros((3, 3), np.float32)
        mask[1, 1] = 1
        result, _ = harmonize(generated, source, mask)
        self.assertTrue(np.isfinite(result).all())
        np.testing.assert_array_equal(result[1, 1], source[1, 1])

    def test_nonrectangular_mask_rejected_and_cancellation_propagated(self):
        generated, source, mask = self.fixture()
        bad = mask.copy(); bad[30, 30] = 0
        with self.assertRaises(ValueError): harmonize(generated, source, bad)
        def cancelled(): raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError): harmonize(generated, source, mask, check_cancelled=cancelled)
