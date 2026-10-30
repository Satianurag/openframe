"""Reference-only edge cleanup; original tracking and CLIP conditioning stay intact."""
import importlib.util
import numpy as np
import torch
import comfy.utils
import comfy.model_management
from .portrait_alpha import portrait_alpha_available, portrait_trimap, refine_image_alpha


def reference_cleanup_available():
    return portrait_alpha_available() and importlib.util.find_spec('numba') is not None


class OpenFrameReferenceForeground:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'reference_image': ('IMAGE', {'openframe_reference_cleanup_available': reference_cleanup_available()}),
            'reference_colors': ('IMAGE',),
            'width': ('INT', {'default': 576, 'min': 256, 'max': 1280, 'step': 32}),
            'height': ('INT', {'default': 1024, 'min': 256, 'max': 1280, 'step': 32}),
        }}
    RETURN_TYPES = ('IMAGE', 'MASK')
    RETURN_NAMES = ('clean_reference', 'alpha')
    FUNCTION = 'prepare'
    CATEGORY = 'OpenFrame/Video'

    def prepare(self, reference_image, reference_colors, width, height):
        if reference_image.shape[0] != 1 or reference_colors.shape[0] != 1:
            raise ValueError('Reference cleanup requires one character image and its native identity colors')
        if not reference_cleanup_available():
            raise ValueError('Install the pinned ViTMatte files and numba on the ComfyUI host before enabling reference cleanup')
        # Match native WanSCAILToVideo resizing and the reviewed PNG input exactly.
        image = comfy.utils.common_upscale(reference_image.movedim(-1, 1), width, height, 'bicubic', 'center').movedim(1, -1)
        colors = comfy.utils.common_upscale(reference_colors.movedim(-1, 1), width, height, 'nearest-exact', 'center').movedim(1, -1)
        rgb = np.clip(image[0].detach().cpu().numpy() * 255, 0, 255).astype(np.uint8)
        coarse = colors[0].detach().cpu().numpy().max(axis=-1) > .1
        quantized = torch.from_numpy(rgb.astype(np.float32) / 255)[None]
        alpha_tensor, alpha_meta = refine_image_alpha(quantized, torch.from_numpy(coarse.astype(np.float32))[None], quantize_16_bit=False)
        alpha = alpha_tensor[0].numpy()
        _, foreground, _ = portrait_trimap(coarse)
        from numba import get_num_threads, set_num_threads
        from ._pymatting_foreground_ml import estimate_foreground_ml
        comfy.model_management.throw_exception_if_processing_interrupted()
        threads = get_num_threads()
        try:
            set_num_threads(min(threads, 8))
            estimated = estimate_foreground_ml(rgb.astype(np.float64) / 255, alpha.astype(np.float64))
        finally:
            set_num_threads(threads)
        estimated[foreground] = rgb[foreground] / 255
        prepared = np.clip(np.rint(estimated * alpha[..., None] * 255), 0, 255).astype(np.uint8)
        comfy.model_management.throw_exception_if_processing_interrupted()
        return {'result': (torch.from_numpy(prepared.astype(np.float32) / 255)[None], alpha_tensor),
                'ui': {'openframe_reference_cleanup': [{
                    'alpha': alpha_meta, 'foreground_solver': 'PyMatting estimate_foreground_ml',
                    'solver_revision': '6d5c4a6bed0e5672abac0bad078e594423ffe4fd', 'solver_license': 'MIT',
                    'method': '12px trimap, CPU ViTMatte, foreground color recovery, black premultiplication',
                    'confident_interior_changed_pixels': int(np.any(prepared != rgb, axis=2)[foreground].sum()),
                    'conditioning': 'Reference VAE RGB only; original CLIP image and native identity masks retained',
                }]}}
