"""Optional, Local-only native EditVid profile; model weights are non-commercial."""
EDITVID_COMMIT = "a58b02dd71e0a7d1f9e04276aeedeb9e1220bfcc"
EDITVID_UPSTREAM_COMMIT = "ba40bed5b4bf63acb913e6be1fdc462df695e99e"
EDITVID_DEPENDENCY = {
    "repository": "https://github.com/CanFromEarth/ComfyUI_FLUX-Klein-EditVid.git",
    "revision": EDITVID_COMMIT, "license": "Apache-2.0",
    "directory": "custom_nodes/ComfyUI_FLUX-Klein-EditVid",
    "required_nodes": ["EditVidSampler"], "install_requirements": False,
    "installation": "Follow custom_nodes/openframe/EDITVID-RUNTIME.md; install the pinned native port, not a substitute sampler.",
}
EDITVID_MODEL = {
    "id": "flux-klein-editvid", "name": "EditVid · Klein 9B (non-commercial)",
    "family": "EditVid", "badge": "Local · non-commercial", "app_ids": ["katana"],
    "description": "Source-inverted, temporally coupled stylization using the pinned independent native EditVid port. Short-clip evaluation retained action and occlusion with visible fast-motion ghost trails and regenerated detail. Not an identity or pixel lock.",
    "tasks": ["restyle"], "supported_providers": ["local"],
    "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"],
    "default_width": 1024, "default_height": 576,
    "default_steps": 4, "fixed_steps": 4, "default_guidance": 1, "fixed_guidance": 1,
    "default_strength": 1, "default_negative_prompt": "", "supports_negative_prompt": False,
    "default_fps": 24, "fixed_fps": 24, "default_frames": 49, "min_frames": 9, "max_frames": 241,
    "dimension_multiple": 16, "frame_multiple": 1, "max_batch_size": 1,
    "min_width": 256, "min_height": 256, "max_width": 1024, "max_height": 1024,
    "default_task_limits": {"max_pixels": 589824}, "source_max_pixels": 2097152,
    "supports_reference": False, "reference_tasks": [], "supports_mask": False, "supports_audio": False,
    "audio_modes_by_task": {"restyle": ["source", "silent"]},
    "license": "FLUX Non-Commercial License v2.1 (9B weights); Apache-2.0 native-port code",
    "license_url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/blob/92196c8e11f7b6cf2b7493e037d8c5345c559216/LICENSE.md",
    "workflow_source": {**EDITVID_DEPENDENCY, "file": "examples/editvid_native.json",
        "original_repository": "https://github.com/PLAN-Lab/EditVid", "original_revision": EDITVID_UPSTREAM_COMMIT,
        "adaptation": "Bounded interval decoder replaces whole-video load/components; source-audio OpenFrame saver replaces silent WEBM. Native inversion, conditioning, scheduler and sampler controls retained."},
}
EDITVID_MODEL_FILES = {"flux-klein-editvid": [
    {"repo": "black-forest-labs/FLUX.2-klein-9B", "revision": "92196c8e11f7b6cf2b7493e037d8c5345c559216",
     "file": "flux-2-klein-9b.safetensors", "category": "diffusion_models", "size_bytes": 18157185168,
     "expected_sha256": "0975d6b77b5f510b99547d6724a208e36527df654e8f6134f59ece3f9f30da58", "license": "FLUX Non-Commercial License v2.1"},
    {"repo": "Comfy-Org/Flux-2-Klein-9B", "revision": "1138ce884c8e977cdacacbe779784fec4426bb3f",
     "file": "split_files/text_encoders/qwen_3_8b.safetensors", "category": "text_encoders", "size_bytes": 16381517176,
     "expected_sha256": "f0ff9239d56269ca1d05e5f86da6a79fac111af464955681f11c7ab0ec5ef6c1", "license": "See pinned Comfy-Org/Flux-2-Klein-9B notices; overall profile requires FLUX Non-Commercial License v2.1"},
    {"repo": "Comfy-Org/Flux-2-Klein-9B", "revision": "1138ce884c8e977cdacacbe779784fec4426bb3f",
     "file": "split_files/vae/flux2-vae.safetensors", "destination_name": "flux3-package-vae.safetensors", "category": "vae", "size_bytes": 336211292,
     "expected_sha256": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3", "license": "See pinned FLUX.2 VAE upstream license"},
]}


def editvid_available(info):
    required = {"EditVidSampler", "OpenFrameEditVidInput", "OpenFrameSaveVideo", "Flux2Scheduler", "VAEEncode", "VAEDecode", "ImageScale", "CLIPTextEncode"}
    for node, field, name in [("UNETLoader", "unet_name", "flux-2-klein-9b.safetensors"),
                              ("CLIPLoader", "clip_name", "qwen_3_8b.safetensors"),
                              ("VAELoader", "vae_name", "flux3-package-vae.safetensors")]:
        choices = info.get(node, {}).get("input", {}).get("required", {}).get(field, [[]])[0]
        if not isinstance(choices, list) or name not in choices:
            return False
    return required.issubset(info)
