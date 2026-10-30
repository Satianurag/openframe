"""Released text segmentation and image-matting components; no runtime download."""
# Keep engine provisioning importable before ComfyUI/custom_nodes is on sys.path.
# The standalone node pack mirrors these immutable pins in sam_runtime_config.py.
SAM3_COMMIT = "f1647e8d0c1d280991f4d1b7d974c2704537fe66"
SAM3_REVISION = "daa63191845a41281374e725f4c9e51c7a824460"
VITMATTE_REVISION = "bf486d01a7d9e3dbcc8400f7942835caf0eaf76e"
MATTING_TRANSFORMERS = "4.57.1"

MATTE_MODEL_FILES = {"sam3.1-vitmatte": [
    {"repo": "facebook/sam3.1", "revision": SAM3_REVISION, "file": "sam3.1_multiplex.pt", "category": "matting/sam3.1", "size_bytes": 3502755717, "expected_sha256": "0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6", "license": "SAM License", "requires_access": True},
    {"repo": "hustvl/vitmatte-base-composition-1k", "revision": VITMATTE_REVISION, "file": "pytorch_model.bin", "category": "matting/vitmatte", "size_bytes": 386836309, "expected_sha256": "b2521bcc4b719fb24611c39605b6642162fd7502e69b3cc846506ca921757b41", "license": "Apache-2.0"},
    {"repo": "hustvl/vitmatte-base-composition-1k", "revision": VITMATTE_REVISION, "file": "config.json", "category": "matting/vitmatte", "size_bytes": 783, "license": "Apache-2.0"},
    {"repo": "hustvl/vitmatte-base-composition-1k", "revision": VITMATTE_REVISION, "file": "preprocessor_config.json", "category": "matting/vitmatte", "size_bytes": 284, "license": "Apache-2.0"},
]}

MATTE_MODEL = {"id": "sam3.1-vitmatte", "name": "SAM3.1 + ViTMatte", "family": "SAM", "badge": "Prompted soft matte",
    "description": "Text concept tracking followed by explicit trimap-conditioned alpha refinement. Keeps original RGB. Matches visible instances of the described concept; fine alpha is refined independently per frame.",
    "tasks": ["semantic-matte"], "output_kind": "video", "supported_providers": ["local"], "compute_kind": "gpu",
    "runtime_prerequisites": "Configured Linux CUDA ComfyUI host with isolated SAM3.1/ViTMatte runtime; no native Windows/macOS support claimed",
    "preserve_source_dimensions": True, "preserve_source_fps": True, "aspect_ratios": [],
    "default_steps": 1, "fixed_steps": 1, "default_guidance": 1, "fixed_guidance": 1,
    "default_fps": 24, "default_frames": 97, "min_frames": 1, "max_frames": 241, "frame_multiple": 1,
    "dimension_multiple": 2, "min_width": 64, "min_height": 64, "max_width": 1920, "max_height": 1920,
    "default_task_limits": {"max_long_side": 1920, "max_short_side": 1088, "max_pixels": 2088960},
    "supports_reference": False, "supports_mask": False, "supports_audio": False, "reference_tasks": [],
    "license": "SAM License + Apache-2.0", "validation_status": "awaiting-validation",
    "trimap_radius": {"min": 1, "max": 64, "default": 12}, "subject_confidence": {"min": .1, "max": .9, "default": .5}}

MATTE_EFFECT = {"id": "semantic-matte", "name": "Remove video background", "description": "Describe the foreground to keep. Produces a transparent cutout and its alpha mask from the original video.",
    "task": "semantic-matte", "model_ids": ["sam3.1-vitmatte"], "prompt": "", "category": "VFX", "kind": "workflow-preset", "output_kind": "video",
    "requires_video": True, "requires_image": False, "requires_mask": False, "requires_reference": False, "requires_audio": False}
