"""The official native SCAIL-2 replacement workflow, without a turbo adapter."""

SCAIL_REVISION = "fe3c728bc793ba21ca674688f822afb709ad44fb"
SAM_REVISION = "7bb8374780a725b4353ed31f3a9395c9742b5621"
RECAST_TEMPLATE = {
    "repository": "https://github.com/Comfy-Org/workflow_templates",
    "revision": "14220b8bd3e86baa852959f17039613191e66656",
    "path": "templates/video_wan21_scail2_character_replacement.json",
    "branch": "full quality, turbo_mode=false; native Base + Extend",
}

RECAST_MODEL = {
    "id": "scail-2", "name": "SCAIL-2 · Full quality", "family": "SCAIL",
    "badge": "Direct video conditioning",
    "description": "Native performer replacement with full driving-video latents, SAM3.1 identity masks and the official DPO adapter. Includes the raw generated clip for comparison. Review hands and held objects; their exact preservation is not guaranteed.",
    "tasks": ["character-replacement"], "supported_providers": ["local"],
    "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"],
    "default_width": 512, "default_height": 896, "default_steps": 40,
    "default_guidance": 5, "default_fps": 24, "default_frames": 81,
    "max_frames": 161, "dimension_multiple": 32, "frame_multiple": 4,
    "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280,
    "supports_audio": False, "supports_mask": True, "mask_optional": True,
    "supports_recast_reference_cleanup": True,
    "mask_input_kinds": ["image"], "native_mask_tracking": "sam3.1",
    "composite_tracking_methods": ["native", "official", "official-union"], "official_composite_providers": ["local"],
    "official_composite_runtime": "Configured Linux CUDA host; OPENFRAME_SAM3_PYTHON and pinned official checkpoint required",
    "supports_reference": True, "reference_tasks": ["character-replacement"],
    "max_references": 1, "supports_encoding_quality": True,
    "default_negative_prompt": "", "native_chunk_frames": 81, "native_chunk_overlap": 5,
    "license": "Apache-2.0 upstream code; MIT model; SAM License for segmentation; native ComfyUI terms apply",
    "workflow_source": RECAST_TEMPLATE,
}


def recast_model_files(existing):
    from .matte_models import MATTE_MODEL_FILES
    common = [dict(entry) for entry in existing["wan-animate"]
              if entry["category"] in {"vae", "text_encoders", "clip_vision"}]
    return {"scail-2": [
        {"repo": "Comfy-Org/SCAIL-2", "revision": SCAIL_REVISION,
         "file": "diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors", "category": "diffusion_models",
         "size_bytes": 32794040328, "expected_sha256": "e3f9cd52184949ee8ffdc01ba14de4c619e0ddfa09ae105cb7efce5c8dc9fe43", "license": "MIT"},
        {"repo": "Comfy-Org/SCAIL-2", "revision": SCAIL_REVISION,
         "file": "loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors", "category": "loras",
         "size_bytes": 1226936552, "expected_sha256": "b106522036f64e50f5f8ae3b808973515ff442cc2fac27b65d875eafb95b89e2", "license": "MIT"},
        {"repo": "Comfy-Org/sam3.1", "revision": SAM_REVISION,
         "file": "checkpoints/sam3.1_multiplex_fp16.safetensors", "category": "checkpoints",
         "size_bytes": 1745546848, "expected_sha256": "9ba99c92703c2e8b4f47de2d34a539bb8e18923049e238b780d70dbe6368eb03", "license": "SAM License"},
        *common,
        {**MATTE_MODEL_FILES["sam3.1-vitmatte"][0], "when": {"recast_composite_tracking": "official"}},
        *[{**entry, "when": {"recast_reference_cleanup": True}}
          for entry in MATTE_MODEL_FILES["sam3.1-vitmatte"] if entry["category"] == "matting/vitmatte"],
    ]}


def recast_available(info):
    required = {"WanSCAILToVideo", "SCAIL2ColoredMask", "SAM3_VideoTrack", "SAM3_TrackToMask",
                "OpenFrameRecastMasks", "OpenFrameVideoInput", "OpenFrameSaveVideo", "ColorTransfer"}
    files = {"UNETLoader": ("unet_name", "wan2.1_14B_SCAIL_2_fp16.safetensors"),
             "LoraLoaderModelOnly": ("lora_name", "wan2.1_SCAIL_2_DPO_lora_bf16.safetensors"),
             "CheckpointLoaderSimple": ("ckpt_name", "sam3.1_multiplex_fp16.safetensors"),
             "VAELoader": ("vae_name", "wan_2.1_vae.safetensors"),
             "CLIPLoader": ("clip_name", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
             "CLIPVisionLoader": ("clip_name", "clip_vision_h.safetensors")}
    if not required.issubset(info):
        return False
    for cls, (field, filename) in files.items():
        option = info.get(cls, {}).get("input", {}).get("required", {}).get(field, [])
        choices = option[0] if option and isinstance(option[0], list) else option[1].get("options", []) if len(option) > 1 else []
        if filename not in choices:
            return False
    return True


def recast_support_capability(info):
    cleanup = info.get("OpenFrameReferenceForeground", {}).get("input", {}).get("required", {}).get("reference_image", [])
    cleanup_ready = len(cleanup) > 1 and isinstance(cleanup[1], dict) and cleanup[1].get("openframe_reference_cleanup_available") is True
    options = info.get("OpenFrameRecastOfficialSupport", {}).get("input", {}).get("required", {}).get("edit_margin", [])
    metadata = options[1] if len(options) > 1 and isinstance(options[1], dict) else {}
    ready = metadata.get("openframe_official_support_available") is True
    methods = ["native", "official"] if ready else ["native"]
    if ready and "generated_images" in info.get("OpenFrameRecastOfficialSupport", {}).get("input", {}).get("optional", {}):
        methods.append("official-union")
    return {"composite_tracking_methods": methods,
            "supports_recast_reference_cleanup": cleanup_ready,
            "official_support_detail": metadata.get("openframe_official_support_detail", "Update the OpenFrame nodes and configure the official SAM runtime before selecting official support.")}
