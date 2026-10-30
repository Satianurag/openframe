"""Pinned first-frame edit propagation, adapted from PaintAPlate's released graph."""

PAINTAPLATE_REVISION = "1f4a5706e4fbec2f6bb5ae763460d03551392d15"
WORKFLOW_URL = f"https://github.com/AInVFX/ainvfx-paintaplate/blob/{PAINTAPLATE_REVISION}/web/workflows/shot.json"
RIPPLE_REVISION = "76abac5ede8a3415b9d1cd803843a38ecb351600"
RIPPLE_FILE = "LTX25_Ripple_v11.safetensors"
RIPPLE_PROMPT = "Use the reference video for motion, timing, camera movement, framing and lighting changes; follow the edited first frame for every change of content, light and style."
RIPPLE_NEGATIVE = "blurry, low resolution, ugly, garbled mess, compression artifacts, glitch, flicker, still image"

RIPPLE_MODEL = {
    "id": "ltx-ripple", "name": "LTX Ripple · edited first frame", "family": "LTX",
    "badge": "First-frame propagation", "license": "LTX-2 Community License; Gemma terms apply",
    "description": "Propagate an edited starting frame through the original video using the released Ripple IC-LoRA workflow. The tracked mask limits the final composite. Heavy occlusion and large appearance changes require review; this profile is not yet quality-validated here.",
    "tasks": ["inpaint"], "supported_providers": ["local"],
    "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"],
    "default_steps": 8, "default_guidance": 1, "default_strength": 1, "default_negative_prompt": RIPPLE_NEGATIVE,
    "default_fps": 24, "default_frames": 97, "max_frames": 121,
    "dimension_multiple": 32, "frame_multiple": 8,
    "min_width": 256, "min_height": 256, "max_width": 1920, "max_height": 1920,
    "default_task_limits": {"max_pixels": 2088960, "max_long_side": 1920, "max_frames": 121}, "supports_audio": False, "supports_mask": True,
    "supports_reference": True, "requires_reference": True,
    "reference_tasks": ["inpaint"], "reference_image_role": "edited-first-frame",
    "reference_must_match_source_dimensions": True, "max_references": 1,
    "supports_uncomposited": True, "supports_encoding_quality": True,
    "encoding_quality_tasks": ["inpaint"], "workflow_source": WORKFLOW_URL,
    "implementation_status": "implemented; first-frame propagation quality validation pending",
}

RIPPLE_MODEL_FILE = {
    "repo": "WepeNerd/LTX-Ripple", "revision": RIPPLE_REVISION,
    "file": RIPPLE_FILE, "category": "loras", "size_bytes": 654443392,
    "expected_sha256": "bde543610144e5bba78782fb0ac18daa663fc087c2212244b8116deb1925ee2a",
    "license": "LTX-2 Community License", "source_note": WORKFLOW_URL,
}


def ripple_model_files(ltx_files):
    # The upstream example uses INT8 ConvRot. Reuse our pinned BF16 versions of
    # the same distilled transformer, projected encoder and video/audio VAEs.
    names = {
        "ltx-2.5-22b-distilled-transformer-bf16.safetensors",
        "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
        "ltx-2.5-video-vae-bf16.safetensors", "ltx-2.5-audio-vae-bf16.safetensors",
    }
    return [{k: v for k, v in entry.items() if k not in {"tasks", "when", "feature"}}
            for entry in ltx_files if entry["file"].split("/")[-1] in names] + [RIPPLE_MODEL_FILE]
