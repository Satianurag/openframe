"""Validate native SCAIL masks and reuse the existing plate-compositing edge policy."""
import numpy as np
import torch
from .media import prepare_masks


class OpenFrameRecastMasks:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "driving_mask": ("MASK",), "pose_colors": ("IMAGE",), "reference_colors": ("IMAGE",),
            "edit_margin": ("INT", {"default": 12, "min": 0, "max": 64}),
            "feather": ("INT", {"default": 6, "min": 0, "max": 32}),
        }}
    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK")
    RETURN_NAMES = ("pose_colors", "reference_colors", "blend_mask")
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/Recast"

    def prepare(self, driving_mask, pose_colors, reference_colors, edit_margin, feather):
        masks = driving_mask.detach().float().cpu().numpy()
        if masks.ndim != 3 or masks.shape[0] != pose_colors.shape[0]:
            raise ValueError("Recast tracking must produce one mask for every driving frame.")
        if not np.any(masks >= .5):
            raise ValueError("SAM3.1 found no source performer. Paint the performer in the first selected frame and retry explicitly.")
        if not torch.any(reference_colors[..., 2] > .5):
            raise ValueError("SAM3.1 found no person in the reference image. Use a clear single-person reference.")
        # Only final plate support changes. The native colored conditioning masks
        # pass through byte-for-byte, retaining white background / blue identity.
        _, blend = prepare_masks(masks, 0, feather, "smooth-inward", edit_margin)
        counts = (masks >= .5).sum(axis=(1, 2))
        return {"result": (pose_colors, reference_colors, torch.from_numpy(blend)),
                "ui": {"openframe_recast_masks": [{"frames": len(masks), "area_min": int(counts.min()),
                    "area_max": int(counts.max()), "empty_frames": np.flatnonzero(counts == 0).tolist(),
                    "tracker": "native SAM3.1", "edit_margin": edit_margin, "feather": feather,
                    "conditioning_masks_modified": False}]}}


class OpenFrameRecastOfficialSupport:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        from .sam_runtime_config import official_support_status
        available, detail = official_support_status(folder_paths.models_dir)
        if available and not torch.cuda.is_available():
            available, detail = False, "Official SAM3.1 support requires a CUDA-capable ComfyUI host."
        return {"required": {"images": ("IMAGE",), "selected_performer": ("MASK",),
            "edit_margin": ("INT", {"default": 12, "min": 0, "max": 64,
                "openframe_official_support_available": available, "openframe_official_support_detail": detail}),
            "feather": ("INT", {"default": 6, "min": 0, "max": 32})},
            "optional": {"generated_images": ("IMAGE",)}}

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("composite_support",)
    FUNCTION = "prepare"
    CATEGORY = "OpenFrame/Recast"

    def prepare(self, images, selected_performer, edit_margin, feather, generated_images=None):
        import hashlib
        import folder_paths
        from .semantic_matte import run_semantic_prediction
        from .sam_runtime_config import official_support_status
        available, detail = official_support_status(folder_paths.models_dir)
        if not available:
            raise ValueError(detail)
        if not torch.cuda.is_available():
            raise ValueError("Official SAM3.1 support requires a CUDA-capable ComfyUI host.")
        n, h, w = images.shape[:3]
        if not 1 <= n <= 161 or max(h, w) > 1280 or selected_performer.shape != (n, h, w):
            raise ValueError("Recast support requires aligned source and native masks, up to 161 frames and 1280 pixels per axis.")
        if generated_images is not None and generated_images.shape != images.shape:
            raise ValueError("Generated performer support requires exactly aligned source and decoded generated frames.")
        decoded = np.ascontiguousarray(images.detach().cpu().clamp(0, 1).mul(255).round().to(torch.uint8).numpy())
        selection = selected_performer[0].detach().float().cpu().numpy()
        _, masks, metadata = run_semantic_prediction(decoded, "person", 1, .5, binary_only=True, selection=selection)
        values = masks.numpy()
        if generated_images is not None:
            # The native mask also covers source pixels that must be replaced.
            # Generated-person support preserves wider clothing/shoes. Both
            # official passes match the same native first-frame identity, using
            # the existing >=0.5 IoU guard; no box fill or frame-specific repair.
            generated = np.ascontiguousarray(generated_images.detach().cpu().clamp(0, 1).mul(255).round().to(torch.uint8).numpy())
            _, generated_masks, generated_metadata = run_semantic_prediction(
                generated, "person", 1, .5, binary_only=True, selection=selection)
            native = selected_performer.detach().float().cpu().numpy() >= .5
            source_masks = values >= .5
            generated_values = generated_masks.numpy() >= .5
            values = (native | source_masks | generated_values).astype(np.float32)
            metadata.update(method="official-union", generated_tracking=generated_metadata,
                            source_rgb_sha256=hashlib.sha256(decoded).hexdigest(),
                            generated_rgb_sha256=hashlib.sha256(generated).hexdigest(),
                            native_area=native.sum(axis=(1, 2)).tolist(),
                            official_source_area=source_masks.sum(axis=(1, 2)).tolist(),
                            official_generated_area=generated_values.sum(axis=(1, 2)).tolist(),
                            union_area=(values >= .5).sum(axis=(1, 2)).tolist(),
                            conditioning_masks_modified=False, vitmatte_used=False)
        _, blend = prepare_masks(values, 0, feather, "smooth-inward", edit_margin)
        counts = (values >= .5).sum(axis=(1, 2))
        metadata.update(edit_margin=edit_margin, feather=feather, feather_method="smooth-inward",
                        frames=n, width=w, height=h, area_min=int(counts.min()), area_max=int(counts.max()),
                        exported_mask="actual feathered final composite support; not native SCAIL conditioning")
        return {"result": (torch.from_numpy(blend),), "ui": {"openframe_recast_support": [metadata]}}
