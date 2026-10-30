"""Matched weights for Comfy's released first/last-frame transition workflow.

Template: Comfy-Org/workflow_templates (MIT); adapter: valiantcat (Apache-2.0).
The LTX base and Gemma encoder retain their respective model licenses.
"""

TEMPLATE_REVISION = "abb9cf6477b59c52dbe234c67f82318dadd872b2"
TEMPLATE_PATH = "templates/template_ltx2_3_style_transition.json"
WORKFLOW_SOURCE = {
    "repository": "https://github.com/Comfy-Org/workflow_templates",
    "revision": TEMPLATE_REVISION,
    "path": TEMPLATE_PATH,
    "license": "MIT",
    "url": f"https://github.com/Comfy-Org/workflow_templates/blob/{TEMPLATE_REVISION}/{TEMPLATE_PATH}",
}
CHECKPOINT = "ltx-2.3-22b-distilled-fp8.safetensors"
ENCODER = "gemma_3_12B_it_fp4_mixed.safetensors"
ADAPTER = "ltx2.3-transition.safetensors"

DEFAULT_NEGATIVE = 'blurry, out of focus, overexposed, underexposed, low contrast, washed out colors, excessive noise, grainy texture, poor lighting, flickering, motion blur, distorted proportions, unnatural skin tones, deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, wrong hand count, artifacts around text, unreadable text on shirt or hat, incorrect lettering on cap (“PNTR”), incorrect t-shirt slogan (“JUST DO IT”), missing microphone, misplaced microphone, inconsistent perspective, camera shake, incorrect depth of field, background too sharp, background clutter, distracting reflections, harsh shadows, inconsistent lighting direction, color banding, cartoonish rendering, 3D CGI look, unrealistic materials, uncanny valley effect, incorrect ethnicity, wrong gender, exaggerated expressions, smiling, laughing, exaggerated sadness, wrong gaze direction, eyes looking at camera, mismatched lip sync, silent or muted audio, distorted voice, robotic voice, echo, background noise, off-sync audio, missing sniff sounds, incorrect dialogue, added dialogue, repetitive speech, jittery movement, awkward pauses, incorrect timing, unnatural transitions, inconsistent framing, tilted camera, missing door or shelves, missing shallow depth of field, flat lighting, inconsistent tone, cinematic oversaturation, stylized filters, or AI artifacts.'

SMOKE_MODEL = {
    "id": "ltx-2.3-transition", "name": "LTX 2.3 · Transition LoRA", "family": "LTX",
    "badge": "First/last-frame trained",
    "description": "The released Comfy first/last-frame workflow with valiantcat's matched transition adapter. Scene transformation is generated; the Smoke preset still requires visual review.",
    "tasks": ["transition-video"], "supported_providers": ["local"],
    "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"],
    "default_width": 1024, "default_height": 576,
    "default_steps": 8, "fixed_steps": 8, "default_guidance": 1, "fixed_guidance": 1,
    "default_negative_prompt": DEFAULT_NEGATIVE, "default_strength": .7, "default_fps": 24, "fixed_fps": 24,
    "default_frames": 121, "min_frames": 121, "max_frames": 241,
    "dimension_multiple": 32, "frame_multiple": 8,
    "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280,
    "default_task_limits": {"max_long_side": 1280, "max_pixels": 1048576},
    "supports_audio": True, "default_generate_audio": True, "supports_mask": False, "supports_reference": False,
    "reference_tasks": [], "max_references": 0, "supports_prompt_enhancement": False,
    "supports_refinement": False, "fixed_framing": "center-crop",
    "supports_encoding_quality": True, "encoding_quality_tasks": ["transition-video"],
    "validation_status": "awaiting-validation", "workflow_source": WORKFLOW_SOURCE,
    "license": "Apache-2.0 adapter; LTX-2 Community base; Gemma terms for the encoder; MIT workflow",
}

SMOKE_MODEL_FILES = {SMOKE_MODEL["id"]: [
    {"repo": "Lightricks/LTX-2.3-fp8", "revision": "91eda216f820e5ecb3d17dc9fe3b7cdaf56b587d",
     "file": CHECKPOINT, "category": "checkpoints", "size_bytes": 29531884062,
     "expected_sha256": "d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2",
     "license": "LTX-2 Community"},
    {"repo": "Comfy-Org/ltx-2", "revision": "ccde4ba417d7900669fd56dd292a883cee11ff37",
     "file": "split_files/text_encoders/" + ENCODER, "category": "text_encoders", "size_bytes": 9447702218,
     "expected_sha256": "aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d",
     "license": "Gemma terms"},
    {"repo": "valiantcat/LTX-2.3-Transition-LORA", "revision": "685118b10fdc2aea63b47bbc6c395fe8c602db53",
     "file": ADAPTER, "category": "loras", "size_bytes": 390229424,
     "expected_sha256": "ba420d6fefafced8e317e2d6ff951b312b52f534377d016b491877a00b830d33",
     "license": "Apache-2.0"},
]}


def smoke_available(info):
    required = {"LTXAVTextEncoderLoader", "LTXVAudioVAELoader", "LTXVPreprocess",
                "LTXVAddGuide", "LTXVCropGuides", "LTXVEmptyLatentAudio",
                "SamplerEulerAncestral", "ResizeImageMaskNode", "VAEDecodeTiled",
                "OpenFrameTransitionInputs", "OpenFrameSaveTransition", "OpenFrameRecordVideoPrompt"}
    if not required.issubset(info):
        return False
    fields = [("CheckpointLoaderSimple", "ckpt_name", CHECKPOINT),
              ("LTXAVTextEncoderLoader", "text_encoder", ENCODER),
              ("LoraLoaderModelOnly", "lora_name", ADAPTER)]
    for cls, field, filename in fields:
        value = info.get(cls, {}).get("input", {}).get("required", {}).get(field, [])
        choices = value[0] if value and isinstance(value[0], list) else value[1].get("options", []) if len(value) > 1 else []
        if filename not in choices:
            return False
    return "fit_on_load" in info["OpenFrameTransitionInputs"].get("input", {}).get("optional", {})
