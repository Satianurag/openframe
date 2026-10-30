"""FLUX3 image profiles; precision options are not claims of task superiority."""
from .flux3_workflows import REGION_DEPENDENCY
FLUX3_MODELS = [
    {"id": model_id, "name": name, "family": "FLUX", "badge": badge,
     "description": "Native FLUX3 distilled generation/editing, explicit prompt expansion, up to ten references and spatial layout. References do not guarantee identity; masked pixel preservation is a separate compositing option.",
     "tasks": ["text-to-image", "image-edit", "image-outpaint"], "output_kind": "image",
     "aspect_ratios": ["1:1", "4:3", "3:4", "2:3", "3:2", "5:4", "4:5", "16:9", "9:16", "21:9"],
     "default_width": 1024, "default_height": 1024, "default_steps": 16, "default_guidance": 1,
     "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 16, "frame_multiple": 1,
     "supports_audio": False, "supports_mask": True, "supports_reference": True,
     "supported_providers": ["local"], "recommended_provider": "local",
     "supports_negative_prompt": False, "fixed_guidance": 1,
     "reference_tasks": ["text-to-image", "image-edit", "image-outpaint"], "max_references": 10, "max_batch_size": 4,
     "supports_image_expansion": True, "expansion_preservation": "exact original RGB and alpha, no resampling",
     "min_width": 256, "min_height": 256, "max_width": 4096, "max_height": 4096,
     "supports_image_layout": True, "max_layout_elements": 32, "layout_coordinate_order": "top,left,bottom,right",
     "layout_coordinate_max": 1000, "supports_image_preservation": True, "supports_region_focus": True,
     "region_focus_dependency": REGION_DEPENDENCY,
     "image_preservation_modes": ["none", "outside-mask", "inside-mask"],
     "supports_prompt_expansion": True, "image_prompt_modes": ["expand", "caption"],
     "default_image_prompt_mode": "expand", "reference_megapixels": {"default": 1, "min": .25, "max": 4, "total_max": 16},
     "resolution_presets": [768, 1024, 1536, 2048, 4096], "precision": precision,
     "license": "FLUX Kommunity License 1.0", "license_url": "https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/blob/feef60b0aaf63a4773ace96636ebbcf43b881312/LICENSE.md",
     "license_note": "Conditional open weights. Noncommercial use and qualifying commercial output generation below US$5M annualized revenue; other commercial uses require licensing. Not Apache-2.0.",
     "implementation_status": "implemented; runtime validation pending"}
    for model_id, name, badge, precision in [
        ("flux3-klein", "FLUX 3 Klein · Quality", "BF16 + 10 references", "BF16 generator/encoder; INT8 prompt expander"),
        ("flux3-klein-int8", "FLUX 3 Klein · Compact", "INT8 + 10 references", "INT8 ConvRot generator/encoder; W4A8 prompt expander"),
    ]
]
