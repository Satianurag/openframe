"""Read-only capability interpretation of a live Comfy node catalog."""
from pathlib import Path
from .models import required_model_files, model_destination
from .video_catalog import VIDEO_MODELS


def video_provider_capabilities(info):
    def options(node, field):
        inputs = info.get(node, {}).get("input", {})
        value = inputs.get("required", {}).get(field, inputs.get("optional", {}).get(field, []))
        return set(value[0]) if value and isinstance(value[0], list) else set()

    def whisper_ready():
        value = info.get("OpenFrameWhisperLoader", {}).get("input", {}).get("required", {}).get("precision", [])
        return len(value) > 1 and bool(value[1].get("openframe_longcat_whisper_available"))

    def installed(entry, profile):
        name = str(model_destination(entry).relative_to(entry["category"]))
        category = entry["category"]
        if category.startswith("audio_encoders/longcat-whisper"):
            return whisper_ready()
        mapping = {"diffusion_models": ("UNETLoader", "unet_name"), "text_encoders": ("CLIPLoader", "clip_name"), "vae": ("VAELoader", "vae_name"), "clip_vision": ("CLIPVisionLoader", "clip_name"), "loras": ("LTXICLoRALoaderModelOnly", "lora_name"), "latent_upscale_models": ("LatentUpscaleModelLoader", "model_name"), "embeddings": ("LTXVLoadConditioning", "file_name")}
        if profile == "longcat-avatar-1.5":
            mapping.update(diffusion_models=("WanVideoModelLoader", "model"), vae=("WanVideoVAELoader", "model_name"), loras=("WanVideoLoraSelect", "lora"))
        pair = mapping.get(category)
        return bool(pair and name in options(*pair))

    common_ltx = {"UNETLoader", "CLIPLoader", "VAELoader", "LTXVConditioning", "LTXVConcatAVLatent", "LTXVSeparateAVLatent", "OpenFrameSourceAudio", "OpenFrameSaveVideo"}
    nodes = {
        "wan-animate-2": {"WanAnimate2ToVideo", "WanAnimate2Cache", "OpenFrameVideoInput", "OpenFrameSaveVideo"},
        "wan-animate-2-distilled": {"WanAnimate2ToVideo", "WanAnimate2Cache", "OpenFrameVideoInput", "OpenFrameSaveVideo"},
        "longcat-avatar-1.5": {"OpenFrameWhisperLoader", "OpenFrameLongCat15Scheduler", "LongCatAvatarWhisperEmbeds", "WanVideoTextEmbedBridge", "WanVideoLongCatAvatarExtendEmbeds", "WanVideoSamplerv2", "OpenFrameSaveVideo"},
        "ltx-2.5": common_ltx,
        "video-tools": {"OpenFrameVideoEdit"},
        "ldf-vfi": {"OpenFrameLoadLDF", "LDFVFIInterpolate", "OpenFrameVideoInput", "OpenFrameSaveVideo"},
    }
    task_nodes = {
        "inpaint": {"LTXICLoRALoaderModelOnly", "LTXAddVideoICLoRAGuide", "OpenFrameGreenFill", "OpenFrameVideoInput"},
        "video-outpaint": {"LTXICLoRALoaderModelOnly", "LTXAddVideoICLoRAGuide", "OpenFrameCanvasVideo"},
        "video-extend": {"LTXVAddGuide", "OpenFrameRestoreContext", "OpenFrameExtendAudio"},
        "video-upscale": {"LTXAddVideoICLoRAGuide", "OpenFrameCanvasVideo"},
        "transition-video": {"OpenFrameTransitionInputs", "OpenFrameSaveTransition", "LTXVAddGuide", "OpenFrameRestoreContext"},
        "alpha-matte": {"LTXAddVideoICLoRAGuide", "OpenFrameCanvasVideo", "OpenFrameSaveAlphaVideo"},
        "clean-plate": {"LTXAddVideoICLoRAGuide", "OpenFrameVideoInput"},
        "sdr-to-hdr": {"LTXAddVideoICLoRAGuide", "LTXVLoadConditioning", "ImageColorSpace", "OpenFrameSaveHDRVideo"},
    }
    model_ids, details = [], {}
    for model in VIDEO_MODELS:
        profile = model["id"]
        if not nodes[profile].issubset(info):
            continue
        if profile == "ldf-vfi":
            value = info["OpenFrameLoadLDF"].get("input", {}).get("required", {}).get("tile_size", [])
            if len(value) < 2 or not value[1].get("openframe_ldf_available"):
                continue
        tasks, missing = [], {}
        for task in model["tasks"]:
            request = {"task": task, "enhance_prompt": True, "video_refinement": "two-stage", "upscale_mode": "pixel-2x"}
            absent = [Path(entry["file"]).name for entry in required_model_files(profile, request) if not installed(entry, profile)] if profile != "ldf-vfi" else []
            if profile == "ltx-2.5":
                absent += sorted(task_nodes.get(task, set()) - set(info))
                if task not in {"alpha-matte", "sdr-to-hdr"} and "TextGenerateLTX2Prompt" not in info:
                    absent.append("TextGenerateLTX2Prompt")
                if task in {"text-to-video", "image-to-video", "transition-video"}:
                    absent += sorted({"LTXVLatentUpsampler", "LatentUpscaleModelLoader", "OpenFramePadForRefinement"} - set(info))
                if task in {"inpaint", "video-outpaint"}:
                    absent += sorted({"LTXVLaplacianPyramidBlend", "OpenFramePadForRefinement"} - set(info))
            if absent:
                missing[task] = absent
            else:
                tasks.append(task)
        if tasks:
            model_ids.append(profile)
        details[profile] = {"tasks": tasks, "missing_by_task": missing, "basis": "live node schemas and installed checkpoint names; not an inference test"}
    semantic = info.get("OpenFrameSemanticMatte", {}).get("input", {}).get("required", {}).get("prompt", [])
    if len(semantic) > 1 and semantic[1].get("openframe_semantic_matte_available") and "OpenFrameSaveAlphaVideo" in info:
        model_ids.append("sam3.1-vitmatte")
        details["sam3.1-vitmatte"] = {"tasks": ["semantic-matte"], "missing_by_task": {}, "basis": "isolated runtime and pinned checkpoint files present; not an inference test"}
    return {"model_ids": model_ids, "model_capabilities": details}
