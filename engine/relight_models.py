"""Official released LTX 2.3 sphere-conditioned relighting recipe."""
REVISION = "aa64fa30f382cc507bfe40ece59d37c1fc9d2d92"
REPO = "Lightricks/LTX-2.3-22b-IC-LoRA-Relight"
TEMPLATE = "LTX-2.3_Relight_ICLoRA_SingleStage_Distilled.json"
WORKFLOW_URL = f"https://huggingface.co/{REPO}/blob/{REVISION}/{TEMPLATE}"
CHECKPOINT = "ltx-2.3-22b-dev.safetensors"
ENCODER = "gemma_3_12B_it_fp8_scaled.safetensors"
DISTILL = "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"
ADAPTER = "ltx-2.3-22b-ic-lora-relight-1.0.safetensors"
RELIGHT_MODEL = {
    "id": "ltx-2.3-relight", "name": "LTX 2.3 · Sphere Relight", "family": "LTX",
    "badge": "Official relighting IC-LoRA", "tasks": ["restyle"], "effect_ids": ["relight"],
    "description": "Released sphere-conditioned relighting graph, with a prepared lighting PNG and a matching direction/look caption. Uses cached FP8 Gemma instead of the template's unquantized encoder.",
    "supported_providers": ["local"], "supports_audio": True,
    "audio_modes_by_task": {"restyle": ["source", "silent"]}, "default_generate_audio": False,
    "supports_mask": False, "supports_reference": True, "reference_tasks": ["restyle"],
    "reference_required": True, "reference_role": "lighting-sphere", "max_references": 1,
    "supports_prompt_enhancement": False, "supports_refinement": False,
    "fixed_width": 1280, "fixed_height": 704, "default_width": 1280, "default_height": 704,
    "default_fps": 24, "fixed_fps": 24, "default_frames": 121, "min_frames": 9, "max_frames": 121,
    "frame_multiple": 8, "dimension_multiple": 32, "min_width": 1280, "max_width": 1280,
    "min_height": 704, "max_height": 704, "aspect_ratios": ["20:11"],
    "default_steps": 8, "fixed_steps": 8, "default_guidance": 1, "fixed_guidance": 1,
    "default_strength": 1, "default_negative_prompt": "pc game, console game, video game, cartoon, childish, ugly, blurry, deformed",
    "supports_encoding_quality": True, "encoding_quality_tasks": ["restyle"],
    "validation_status": "awaiting-validation", "workflow_source": WORKFLOW_URL,
    "license": "LTX-2 Community adapter/base; Gemma encoder terms; MIT sphere renderer",
}


def relight_model_files(existing):
    shared = [dict(e) for e in existing if e["file"].split("/")[-1] in {CHECKPOINT, ENCODER, DISTILL}]
    if len(shared) != 3:
        raise ValueError("Relight requires the exact DEV, distilled-1.1 and FP8 Gemma files.")
    return shared + [{"repo": REPO, "revision": REVISION, "file": ADAPTER,
        "category": "loras", "size_bytes": 327309305,
        "expected_sha256": "c0d519f83681395d160e115829a9044d7d2ec013be6a2655834d235a2e866ebd",
        "license": "LTX-2 Community; gated access agreement"}]


def relight_available(info):
    required = {"OpenFrameRelightSphere", "OpenFrameVideoInput", "OpenFrameSaveVideo",
                "LTXAddVideoICLoRAGuide", "LTXICLoRALoaderModelOnly", "LTXVTiledVAEDecode",
                "LTXVConcatAVLatent", "LTXVSeparateAVLatent", "LTXVCropGuides"}
    if not required.issubset(info):
        return False
    for cls, field, filename in [("CheckpointLoaderSimple", "ckpt_name", CHECKPOINT),
            ("LTXAVTextEncoderLoader", "text_encoder", ENCODER),
            ("LoraLoaderModelOnly", "lora_name", DISTILL),
            ("LTXICLoRALoaderModelOnly", "lora_name", ADAPTER)]:
        spec = info.get(cls, {}).get("input", {}).get("required", {}).get(field, [])
        choices = spec[0] if spec and isinstance(spec[0], list) else spec[1].get("options", []) if len(spec) > 1 else []
        if filename not in choices:
            return False
    return True
