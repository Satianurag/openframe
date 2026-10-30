"""Build one explicit ComfyUI API graph per selected model; no hidden inference."""
import copy
import secrets
from .catalog import model_by_id, effect_by_id, allows_restyle_first_frame


class WorkflowError(ValueError):
    pass


def normalize_request(request):
    r = copy.deepcopy(request)
    from .provider_policy import require_provider_enabled
    try:
        require_provider_enabled(r.get("provider", "local"))
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    model = model_by_id(r.get("model_id", "ltx-0.9.8"))
    effect = effect_by_id(r.get("effect_id", "text-to-video"))
    if not model or not effect or model["id"] not in effect["model_ids"]:
        raise WorkflowError("This model does not support the selected effect.")
    if (r.get("reference_asset_id") or r.get("reference_asset_ids")) and effect["task"] not in model.get("reference_tasks", []) and not allows_restyle_first_frame(model, r):
        raise WorkflowError("This model/task does not support an additional reference image. Image-to-video uses its source image as the reference.")
    r.update(model_id=model["id"], effect_id=effect["id"], task=effect["task"])
    if allows_restyle_first_frame(model, r) and r.get("reference_asset_ids"):
        raise WorkflowError("Canny first-frame conditioning accepts one edited full-frame image, not an image list.")
    vace_mode = r.get("vace_reference_mode", "appearance")
    if vace_mode not in {"appearance", "first-frame"} or (vace_mode == "first-frame" and
            (model["id"] != "wan-vace-14b" or effect["task"] != "inpaint" or r.get("reference_asset_ids"))):
        raise WorkflowError("First-frame VACE control requires the VACE14B masked-video profile and one edited full-frame reference.")
    if r.get("image_edit_focus", "full") != "full" and not model.get("supports_region_focus"):
        raise WorkflowError("This model does not support focused image-region editing.")
    from .image_relight_workflows import validate_image_brightness
    validate_image_brightness(r, model)
    image_task = model.get("output_kind") == "image"
    non_video = model.get("output_kind") in {"image", "audio"}
    reference_count = len(r.get("reference_asset_ids") or []) + bool(r.get("reference_asset_id")) + (bool(r.get("source_asset_id")) if image_task else 0)
    if reference_count > model.get("max_references", 1):
        raise WorkflowError("Too many reference images for this model.")
    for key, default in [("width", model.get("default_width", 512)), ("height", model.get("default_height", 288)), ("frames", 121 if effect["task"] == "transition-video" else model["default_frames"]), ("steps", model["default_steps"])]:
        r[key] = int(r.get(key, default))
    r["fps"] = float(r.get("fps", model["default_fps"]))
    r["guidance"] = float(r.get("guidance", model["default_guidance"]))
    r["strength"] = float(r.get("strength", model.get("default_strength", .8)))
    r["batch_size"] = int(r.get("batch_size", 1))
    if not 1 <= r["batch_size"] <= model.get("max_batch_size", 1):
        raise WorkflowError("This model does not support the requested batch size.")
    if non_video:
        r["frames"], r["fps"] = 1, 1.0
    r["mask_tracking_method"] = r.get("mask_tracking_method", "sam2") if r.get("mask_tracking", True) else "static"
    if r["mask_tracking_method"] not in {"sam2", "flow", "static"}:
        raise WorkflowError("Unknown mask tracking method.")
    margin = r.get("mask_edit_margin")
    if margin is None:
        margin = 12 if r["task"] in {"inpaint", "character-replacement"} and r["mask_tracking_method"] != "static" else 0
    r["mask_edit_margin"] = int(margin)
    if not 0 <= r["mask_edit_margin"] <= 64:
        raise WorkflowError("Edit margin must be from 0 to 64 output pixels.")
    r["seed"] = int(r.get("seed", -1))
    if r["seed"] < 0:
        r["seed"] = secrets.randbelow(2**32)
    if not (0 <= r["seed"] < 2**64):
        raise WorkflowError("Seed must fit an unsigned 64-bit integer.")
    for axis in ("width", "height"):
        if not model["min_" + axis] <= r[axis] <= model["max_" + axis] or r[axis] % model["dimension_multiple"]:
            raise WorkflowError(f"{axis.title()} must be a multiple of {model['dimension_multiple']} within this model's supported range.")
    if not non_video and (not model.get("min_frames", 9) <= r["frames"] <= model["max_frames"] or (r["frames"] - 1) % model["frame_multiple"]):
        raise WorkflowError(f"Frame count must be {model['frame_multiple']}n+1, from {model.get('min_frames', 9)} to {model['max_frames']}.")
    if model.get("fixed_fps") and r["fps"] != model["fixed_fps"]:
        raise WorkflowError(f"This model requires {model['fixed_fps']} FPS for audio alignment.")
    if not 1 <= r["fps"] <= 120 or not 1 <= r["steps"] <= 50 or not .05 <= r["strength"] <= 1:
        raise WorkflowError("FPS, steps or transformation strength is outside the supported range.")
    user_prompt = str(r.get("prompt", "")).strip()
    r["prompt"] = user_prompt or effect["prompt"]
    if effect.get("prompt_policy") == "empty":
        r["prompt"] = ""
    if not r["prompt"] and effect.get("prompt_policy") not in {"empty", "optional"} and model.get("requires_prompt", True):
        raise WorkflowError("Describe the scene you want to generate.")
    from .video_request import normalize_video_request
    normalize_video_request(r, model, effect, WorkflowError)
    if model.get("supports_image_layout"):
        if r["model_id"] == "flux3-klein-base":
            from .flux3_character_workflows import validate_character_request
            validate_character_request(r)
        else:
            from .flux3_workflows import validate_flux3_request
            validate_flux3_request(r)
    elif r.get("image_layout") or r.get("image_preservation", "none") != "none" or r.get("image_prompt_mode", "expand") != "expand" or r.get("image_reference_megapixels", 1) != 1:
        raise WorkflowError("This model does not support FLUX3 image layout, prompt or pixel-preservation controls.")
    if r["task"] == "text-to-speech":
        r["voice"] = r.get("voice") or model["voices"][0]["id"]
        r["speech_speed"] = float(r.get("speech_speed", 1.0))
        if r["voice"] not in {v["id"] for v in model["voices"]} or not .5 <= r["speech_speed"] <= 2:
            raise WorkflowError("Choose a supported voice and speech speed from 0.5 to 2.")
        if len(r["prompt"]) > model["max_script_characters"]:
            raise WorkflowError(f"Speech scripts are limited to {model['max_script_characters']:,} characters per job.")
    if r["model_id"] in {"ming-narration", "qwen-caption"}:
        from .narration_workflows import normalize_narration
        normalize_narration(r)
    if r["task"] == "image-layers":
        r["layer_count"] = int(r.get("layer_count") or 4)
        if not 2 <= r["layer_count"] <= 8:
            raise WorkflowError("Image decomposition supports 2–8 layers.")
    if r["task"] == "video-depth":
        from .depth_workflows import normalize_depth_request
        normalize_depth_request(r)
    elif r.get("depth_inference_mode", "chunk") != "chunk":
        raise WorkflowError("Depth inference mode is only available for a depth operation.")
    method = r.get("recast_composite_tracking") or "native"
    if r.get("recast_reference_cleanup") and r["model_id"] != "scail-2":
        raise WorkflowError("Reference edge cleanup is available only for SCAIL-2 character replacement.")
    if method not in {"native", "official", "official-union"}:
        raise WorkflowError("Choose native, official source, or source + generated Recast composite tracking.")
    if method in {"official", "official-union"} and (r["model_id"] != "scail-2" or r.get("mask_asset_id") or r.get("provider") not in {"local"}):
        raise WorkflowError("Official Recast composite tracking requires SCAIL-2 with automatic performer selection on a configured Local ComfyUI host; manual masks use native tracking.")
    if r["model_id"] == "scail-2":
        r["recast_composite_tracking"] = method
    r.setdefault("negative_prompt", model.get("default_negative_prompt", "" if model.get("supports_negative_prompt") is False else "low quality, distorted anatomy, flicker, text, watermark"))
    if r["model_id"] == "qwen-portrait-relight":
        from .portrait_relight_workflows import validate_portrait_relight
        validate_portrait_relight(r)
    if r["model_id"] == "qwen-image-relight":
        from .image_relight_workflows import validate_image_relight
        validate_image_relight(r)
    from .editvid_workflows import validate_editvid
    validate_editvid(r)
    return r


def _sigmas(steps, strength=1.0):
    base = [1.0, .99375, .9875, .98125, .975, .909375, .725, .421875, 0.0]
    start = (1.0 - strength) * 8
    values = []
    for i in range(steps + 1):
        x = start + (8 - start) * i / steps
        lo = min(int(x), 7); part = x - lo
        values.append(base[lo] * (1 - part) + base[lo + 1] * part)
    return ", ".join(f"{x:.8f}" for x in values)


def build_workflow(request, assets=None):
    r = normalize_request(request)
    if r["model_id"] == "flux-klein-editvid":
        from .editvid_workflows import build_editvid_workflow
        return build_editvid_workflow(r, assets)
    if r["model_id"] == "qwen-portrait-relight":
        from .portrait_relight_workflows import build_portrait_relight_workflow
        return build_portrait_relight_workflow(r, assets)
    if r["model_id"] == "qwen-image-relight":
        from .image_relight_workflows import build_image_relight_workflow
        return build_image_relight_workflow(r, assets)
    if r["model_id"] == "sam3.1-vitmatte":
        from .matte_workflows import build_matte_workflow
        return build_matte_workflow(r, assets)
    if r["model_id"] in {"ming-narration", "qwen-caption"}:
        from .narration_workflows import build_narration_workflow
        return build_narration_workflow(r, assets)
    if r["model_id"] == "flux3-klein-base":
        from .flux3_character_workflows import build_character_workflow
        return build_character_workflow(r, assets)
    if r["model_id"] == "qwen-image-layered":
        from .layer_workflows import build_layer_workflow
        return build_layer_workflow(r, assets)
    if r["model_id"] in {"wan-animate-2", "wan-animate-2-distilled"}:
        from .motion2_workflows import build_motion2_workflow
        return build_motion2_workflow(r, assets)
    if r["model_id"] == "longcat-avatar-1.5":
        from .longcat_workflows import build_longcat_workflow
        return build_longcat_workflow(r, assets)
    if r["model_id"] == "ltx-ripple":
        from .ripple_workflows import build_ripple_workflow
        return build_ripple_workflow(r, assets)
    if r["model_id"] == "ltx-2.5":
        from .ltx25_workflows import build_ltx25_workflow
        return build_ltx25_workflow(r, assets)
    if r["model_id"] == "ltx-2.3-transition":
        from .smoke_workflows import build_smoke_workflow
        return build_smoke_workflow(r, assets)
    if r["model_id"] == "ltx-2.3-relight":
        from .relight_workflows import build_relight_workflow
        return build_relight_workflow(r, assets)
    if r["model_id"] == "video-tools":
        from .video_tools import build_video_tool_workflow
        return build_video_tool_workflow(r, assets)
    if r["model_id"] == "ldf-vfi":
        from .video_tools import build_interpolation_workflow
        return build_interpolation_workflow(r, assets)
    if r["model_id"] in {"video-depth-small", "vigeo-1.1"}:
        from .depth_workflows import build_depth_workflow
        return build_depth_workflow(r, assets)
    if r["model_id"] in {"flux3-klein", "flux3-klein-int8"}:
        from .flux3_workflows import build_flux3_workflow
        return build_flux3_workflow(r, assets)
    if r["model_id"] in {"flux-klein-4b", "birefnet"}:
        from .image_workflows import build_image_workflow
        return build_image_workflow(r, assets)
    if r["model_id"] == "kokoro-82m":
        return {
            "speech": {"class_type": "OpenFrameKokoroSpeech", "inputs": {"text": r["prompt"], "voice": r["voice"], "speed": r["speech_speed"]}},
            "save": {"class_type": "OpenFrameSaveAudio", "inputs": {"audio": ["speech", 0], "filename_prefix": str(r.get("job_id", "OpenFrame"))}},
        }
    if r["model_id"] == "scail-2":
        from .recast_workflows import build_recast_workflow
        return build_recast_workflow(r, assets)
    if r["model_id"] == "wan-animate":
        from .character_workflows import build_character_workflow
        return build_character_workflow(r, assets)
    if r["model_id"] == "wan-s2v":
        from .speech_workflows import build_speech_workflow
        return build_speech_workflow(r, assets)
    if assets and assets.get("reference") and r["task"] not in model_by_id(r["model_id"]).get("reference_tasks", []) and not allows_restyle_first_frame(model_by_id(r["model_id"]), r):
        raise WorkflowError("This model/task does not support an additional reference image.")
    files = {"source": "source.mp4" if r["task"] in {"inpaint", "restyle"} else "source.png", "mask": "mask.png", "reference": "reference.png", "audio": "speech.wav"}
    files.update(assets or {})
    graph = {}
    def node(id, cls, **inputs):
        graph[str(id)] = {"class_type": cls, "inputs": inputs, "_meta": {"title": cls}}
        return [str(id), 0]
    width, height, frames, fps = r["width"], r["height"], r["frames"], r["fps"]
    editing = r["task"] in {"inpaint", "restyle"}
    refine_inpaint = r["model_id"] == "ltx-2.3" and r["effect_id"] == "remove-object"
    source = mask = blend = None
    if editing:
        source = node("source", "OpenFrameVideoInput", filename=files["source"], width=width, height=height, frames=frames, fps=fps, mask_filename=files["mask"] if r["task"] == "inpaint" else "", track_mask=bool(r.get("mask_tracking", True)), mask_dilation=int(r.get("mask_dilation", 8)), mask_feather=int(r.get("mask_feather", 3)), trim_start=float(r.get("trim_start", 0)), tracking_method=r["mask_tracking_method"], feather_method="smooth-inward", edit_margin=r["mask_edit_margin"])
        mask, blend = ["source", 1], ["source", 2]
    elif r["task"] == "image-to-video":
        source = node("image", "LoadImage", image=files["source"])
    audio = None
    if r["model_id"] in {"wan-vace", "wan-vace-14b"}:
        checkpoint = "wan2.1_vace_14B_fp16.safetensors" if r["model_id"] == "wan-vace-14b" else "wan2.1_vace_1.3B_fp16.safetensors"
        model = node("model", "UNETLoader", unet_name=checkpoint, weight_dtype="default")
        model = node("shift", "ModelSamplingSD3", model=model, shift=5.0)
        clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
        vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
        positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
        negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
        extra = {}
        first_frame_control = r["model_id"] == "wan-vace-14b" and r.get("vace_reference_mode") == "first-frame"
        if editing:
            control_video = source
            control_mask = mask
            if first_frame_control:
                # Released VACE FrameRefExpand + Composition(extension,repaint).
                # Keep the original source/blend mask untouched for final compositing.
                reference = node("reference", "LoadImage", image=files["reference"])
                first = node("fit_reference", "ImageScale", image=reference, upscale_method="lanczos", width=width, height=height, crop="center")
                tail = node("source_after_first", "ImageFromBatch", image=source, batch_index=1, length=frames - 1)
                control_video = node("known_first_video", "ImageBatch", image1=first, image2=tail)
                mask_images = node("control_mask_images", "MaskToImage", mask=mask)
                mask_tail = node("mask_after_first", "ImageFromBatch", image=mask_images, batch_index=1, length=frames - 1)
                zero = node("known_first_mask", "SolidMask", value=0.0, width=width, height=height)
                zero_image = node("known_first_mask_image", "MaskToImage", mask=zero)
                mask_batch = node("known_first_mask_batch", "ImageBatch", image1=zero_image, image2=mask_tail)
                control_mask = node("known_first_control_mask", "ImageToMask", image=mask_batch, channel="red")
            if r["task"] == "inpaint":
                # Official VACE inpainting blanks the selected pixels before
                # encoding both inactive and reactive conditioning streams.
                inverted = node("inverse_mask", "InvertMask", mask=control_mask)
                cleared = node("mask_image", "MaskToImage", mask=inverted)
                control_video = node("masked_guide", "ImageCompositeMasked", destination=control_video, source=cleared, x=0, y=0, resize_source=True, mask=control_mask)
            extra.update(control_video=control_video, control_masks=control_mask)
        if r["task"] == "image-to-video":
            # VACE's reference input is identity/style guidance, not an opening
            # frame. Its native control branch pads this known frame with neutral
            # video and white (generatable) masks for the remaining time steps.
            first_mask = node("first_frame_mask", "SolidMask", value=0.0, width=width, height=height)
            extra.update(control_video=source, control_masks=first_mask)
        elif assets and assets.get("reference") and not first_frame_control:
            extra["reference_image"] = node("reference", "LoadImage", image=files["reference"])
        node("condition", "WanVaceToVideo", positive=positive, negative=negative, vae=vae, width=width, height=height, length=frames, batch_size=1, strength=r["strength"], **extra)
        samples = node("sample", "KSampler", model=model, positive=["condition", 0], negative=["condition", 1], latent_image=["condition", 2], seed=r["seed"], steps=r["steps"], cfg=r["guidance"], sampler_name="uni_pc", scheduler="simple", denoise=1.0)
        latent = node("trim_reference", "TrimVideoLatent", samples=samples, trim_amount=["condition", 3])
    else:
        ltx2 = r["model_id"] == "ltx-2.3"
        checkpoint = "ltx-2.3-22b-dev.safetensors" if ltx2 else "ltxv-2b-0.9.8-distilled.safetensors"
        model = node("model", "CheckpointLoaderSimple", ckpt_name=checkpoint)
        vae = ["model", 2]
        if ltx2:
            clip = node("text_encoder", "LTXAVTextEncoderLoader", text_encoder="gemma_3_12B_it_fp8_scaled.safetensors", ckpt_name=checkpoint, device="default")
            model = node("distill", "LoraLoaderModelOnly", model=model, lora_name="ltx-2.3-22b-distilled-lora-384-1.1.safetensors", strength_model=.5)
        else:
            clip = node("text_encoder", "CLIPLoader", clip_name="t5xxl_fp8_e4m3fn_scaled.safetensors", type="ltxv", device="default")
        positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
        negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
        node("condition", "LTXVConditioning", positive=positive, negative=negative, frame_rate=fps)
        positive, negative = ["condition", 0], ["condition", 1]
        sample_width, sample_height = width, height
        if r["task"] == "inpaint":
            coarse_source, coarse_mask = source, mask
        if refine_inpaint:
            # Match the published two-stage IC-LoRA graph. Padding preserves
            # geometry for requested sizes divisible by 32 but not by 64.
            full_width, full_height = ((width + 63) // 64) * 64, ((height + 63) // 64) * 64
            full_source = node("pad_refinement", "OpenFramePadForRefinement", images=source, mask=mask)
            full_mask = ["pad_refinement", 1]
            sample_width, sample_height = full_width // 2, full_height // 2
            coarse_source = node("coarse_source", "ImageScale", image=full_source, upscale_method="lanczos", width=sample_width, height=sample_height, crop="disabled")
            mask_image = node("full_mask_image", "MaskToImage", mask=full_mask)
            mask_image = node("coarse_mask_image", "ImageScale", image=mask_image, upscale_method="nearest-exact", width=sample_width, height=sample_height, crop="disabled")
            coarse_mask = node("coarse_mask", "ImageToMask", image=mask_image, channel="red")
        latent = node("empty", "EmptyLTXVLatentVideo", width=sample_width, height=sample_height, length=frames, batch_size=1)
        if r["task"] == "image-to-video":
            latent = node("image_condition", "LTXVImgToVideoInplace", vae=vae, image=source, latent=latent, strength=1.0, bypass=False)
        if r["task"] == "restyle":
            latent = node("source_latent", "VAEEncode", pixels=source, vae=vae)
        if r["task"] == "inpaint":
            model = node("inpaint_adapter", "LTXICLoRALoaderModelOnly", model=model, lora_name="ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors", strength_model=1.0)
            guide = node("green_guide", "OpenFrameGreenFill", images=coarse_source, mask=coarse_mask)
            # The published inpaint adapter was trained at reference factor 1.
            node("inpaint_guide", "LTXAddVideoICLoRAGuideAdvanced", positive=positive, negative=negative, vae=vae, latent=latent, image=guide, frame_idx=0, strength=r["strength"], latent_downscale_factor=1.0, crop="disabled", use_tiled_encode=True, tile_size=256, tile_overlap=64, attention_strength=1.0)
            positive, negative, latent = ["inpaint_guide", 0], ["inpaint_guide", 1], ["inpaint_guide", 2]
        if ltx2:
            audio_vae = node("audio_vae", "LTXVAudioVAELoader", ckpt_name=checkpoint)
            audio_latent = node("audio_latent", "LTXVEmptyLatentAudio", frames_number=frames, frame_rate=fps, batch_size=1, audio_vae=audio_vae)
            latent = node("av_latent", "LTXVConcatAVLatent", video_latent=latent, audio_latent=audio_latent)
        noise = node("noise", "RandomNoise", noise_seed=r["seed"])
        guider = node("guider", "CFGGuider", model=model, positive=positive, negative=negative, cfg=r["guidance"])
        sampler = node("sampler", "KSamplerSelect", sampler_name="euler_ancestral_cfg_pp" if ltx2 else "euler")
        sigmas = node("sigmas", "ManualSigmas", sigmas=_sigmas(r["steps"], r["strength"] if r["task"] == "restyle" else 1.0))
        latent = node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=latent)
        if ltx2:
            latent = node("separate", "LTXVSeparateAVLatent", av_latent=["sample", 1] if r["task"] == "inpaint" else latent)
            audio_samples = ["separate", 1]
        if r["task"] == "inpaint":
            node("crop_guides", "LTXVCropGuides", positive=positive, negative=negative, latent=latent)
            latent = ["crop_guides", 2]
            if refine_inpaint:
                coarse = node("decode_coarse", "VAEDecodeTiled", samples=["crop_guides", 2], vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
                # Never blend against the artificial green conditioning placeholder:
                # its low frequencies tint the reconstructed hole. Fill the plate's
                # hole with generated pixels before the multiband boundary blend.
                coarse_plate = node("coarse_plate", "ImageCompositeMasked", destination=coarse_source, source=coarse, x=0, y=0, resize_source=False, mask=coarse_mask)
                coarse = node("blend_coarse", "LTXVLaplacianPyramidBlend", image_a=coarse, image_b=coarse_plate, mask=coarse_mask, trim_to_shortest=False, mask_low_res_dilation=5)
                enlarged = node("upscale_refinement", "ImageScale", image=coarse, upscale_method="lanczos", width=full_width, height=full_height, crop="disabled")
                encoded = node("encode_refinement", "VAEEncodeTiled", pixels=enlarged, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
                node("freeze_refinement_audio", "LTXVSetAudioRefTokens", positive=["crop_guides", 0], negative=["crop_guides", 1], audio_latent=audio_samples)
                refined_input = node("refinement_av", "LTXVConcatAVLatent", video_latent=encoded, audio_latent=["freeze_refinement_audio", 2])
                refined_guider = node("refinement_guider", "CFGGuider", model=model, positive=["crop_guides", 0], negative=["crop_guides", 1], cfg=r["guidance"])
                refined_noise = node("refinement_noise", "RandomNoise", noise_seed=(r["seed"] + 1) % 2**64)
                refined_sampler = node("refinement_sampler", "KSamplerSelect", sampler_name="euler_cfg_pp")
                refined_sigmas = node("refinement_sigmas", "ManualSigmas", sigmas="0.7250, 0.4219, 0.0")
                node("sample_refinement", "SamplerCustomAdvanced", noise=refined_noise, guider=refined_guider, sampler=refined_sampler, sigmas=refined_sigmas, latent_image=refined_input)
                latent = node("separate_refinement", "LTXVSeparateAVLatent", av_latent=["sample_refinement", 1])
                audio_samples = ["separate_refinement", 1]
        if ltx2 and r.get("generate_audio", True):
            audio = node("decode_audio", "LTXVAudioVAEDecode", samples=audio_samples, audio_vae=audio_vae)
    images = node("decode", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    if refine_inpaint:
        refined_plate = node("refinement_plate", "ImageCompositeMasked", destination=full_source, source=images, x=0, y=0, resize_source=False, mask=full_mask)
        images = node("blend_refinement", "LTXVLaplacianPyramidBlend", image_a=images, image_b=refined_plate, mask=full_mask, trim_to_shortest=False, mask_low_res_dilation=6)
        images = node("crop_refinement", "ImageCrop", image=images, width=width, height=height, x=0, y=0)
    if r.get("export_uncomposited"):
        # Opt-in diagnostic: same sampled frames before plate preservation.
        node("save_uncomposited", "OpenFrameSaveVideo", images=images, fps=fps, frames=frames,
             filename_prefix=str(r.get("job_id", "OpenFrame")) + "_uncomposited",
             preserve_outside_mask=False, preserve_audio=bool(r.get("preserve_audio", True)),
             source_filename=files["source"], trim_start=float(r.get("trim_start", 0)), export_mask=False)
    finish = {}
    if editing and r["task"] == "inpaint":
        finish.update(source=source, mask=blend, match_lighting=r["effect_id"] == "remove-object")
    if audio:
        finish["audio"] = audio
    node("save", "OpenFrameSaveVideo", images=images, fps=fps, frames=frames, filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=bool(r.get("preserve_outside_mask", True)), preserve_audio=bool(r.get("preserve_audio", True)), source_filename=files["source"] if editing else "", trim_start=float(r.get("trim_start", 0)), export_mask=bool(r.get("export_mask", True)), **finish)
    return graph
