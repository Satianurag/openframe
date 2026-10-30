"""Native Comfy-Org VACE14B inpainting profile; no acceleration LoRA or model rewrite."""

TEMPLATE_REVISION = "abb9cf6477b59c52dbe234c67f82318dadd872b2"
TEMPLATE_URL = f"https://github.com/Comfy-Org/workflow_templates/blob/{TEMPLATE_REVISION}/templates/video_wan_vace_inpainting.json"
CHECKPOINT = "wan2.1_vace_14B_fp16.safetensors"
FIRST_FRAME_SOURCE = {
    "repository": "https://github.com/ali-vilab/VACE",
    "revision": "48eb44f1c4be87cc65a98bff985a26976841e9f3", "license": "Apache-2.0",
    "files": ["vace/annotators/frameref.py", "vace/annotators/composition.py", "vace/models/wan/wan_vace.py"],
    "recipe": "FrameRefExpandAnnotator(firstframe) + CompositionAnnotator(extension,repaint): known edited frame0 with zero generation mask; following frames retain the original masked video.",
}

VACE14_MODEL = {
    "id": "wan-vace-14b", "name": "Wan VACE 14B", "family": "Wan",
    "badge": "Reference-guided inpainting", "license": "Apache-2.0",
    "description": "Full-precision 14B native ComfyUI inpainting with a video, tracked mask and optional appearance reference. Uses the official unaccelerated 20-step / CFG 6 recipe. Output quality must be reviewed.",
    "tasks": ["inpaint"], "supported_providers": ["local"],
    "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"],
    "default_steps": 20, "default_guidance": 6, "default_strength": 1,
    "default_negative_prompt": '过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走,过曝，',
    "default_fps": 16, "default_frames": 81, "max_frames": 161,
    "dimension_multiple": 16, "frame_multiple": 4,
    "supports_audio": False, "supports_mask": True, "supports_reference": True,
    "reference_tasks": ["inpaint"], "max_references": 1,
    "reference_modes": ["appearance", "first-frame"], "first_frame_conditioning_source": FIRST_FRAME_SOURCE,
    "supports_uncomposited": True,
    "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280,
    "strength_controls": {"inpaint": {"label": "Video conditioning", "hint": "The official full-quality recipe uses 1.0. Video and reference conditioning guide the replacement; they do not guarantee identical pixels or geometry."}},
    "workflow_source": TEMPLATE_URL,
}

VACE14_MODEL_FILE = {
    "repo": "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
    "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d",
    "file": f"split_files/diffusion_models/{CHECKPOINT}",
    "category": "diffusion_models", "size_bytes": 34675323640,
    "expected_sha256": "f202a5c59b8a91ada1862c46a038214f1f7f216c61ec8350d25f69b919da4307",
    "license": "Apache-2.0",
    "source_note": "Official Comfy-Org FP16 VACE14B repack. Reuses the pinned Wan VAE and UMT5 encoder; no CausVid acceleration or Phantom merge.",
}
