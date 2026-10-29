"""Build one explicit ComfyUI API graph per selected model; no hidden inference."""
import copy
import secrets
from .catalog import model_by_id, effect_by_id


class WorkflowError(ValueError):
    pass


def normalize_request(request):
    r = copy.deepcopy(request)
    model = model_by_id(r.get("model_id", "ltx-0.9.8"))
    effect = effect_by_id(r.get("effect_id", "text-to-video"))
    if not model or not effect or model["id"] not in effect["model_ids"]:
        raise WorkflowError("This model does not support the selected effect.")
    if r.get("reference_asset_id") and effect["task"] not in model.get("reference_tasks", []):
        raise WorkflowError("This model/task does not support an additional reference image. Image-to-video uses its source image as the reference.")
    r.update(model_id=model["id"], effect_id=effect["id"], task=effect["task"])
    for key, default in [("width", 512), ("height", 288), ("frames", model["default_frames"]), ("steps", model["default_steps"])]:
        r[key] = int(r.get(key, default))
    r["fps"] = float(r.get("fps", model["default_fps"]))
    r["guidance"] = float(r.get("guidance", model["default_guidance"]))
    r["strength"] = float(r.get("strength", .8))
    r["mask_tracking_method"] = r.get("mask_tracking_method", "sam2") if r.get("mask_tracking", True) else "static"
    if r["mask_tracking_method"] not in {"sam2", "flow", "static"}:
        raise WorkflowError("Unknown mask tracking method.")
    margin = r.get("mask_edit_margin")
    if margin is None:
        margin = 12 if r["task"] == "inpaint" and r["mask_tracking_method"] != "static" else 0
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
    if not 9 <= r["frames"] <= model["max_frames"] or (r["frames"] - 1) % model["frame_multiple"]:
        raise WorkflowError(f"Frame count must be {model['frame_multiple']}n+1, from 9 to {model['max_frames']}.")
    if not 1 <= r["fps"] <= 120 or not 1 <= r["steps"] <= 50 or not .05 <= r["strength"] <= 1:
        raise WorkflowError("FPS, steps or transformation strength is outside the supported range.")
    user_prompt = str(r.get("prompt", "")).strip()
    r["prompt"] = user_prompt or effect["prompt"]
    if not r["prompt"]:
        raise WorkflowError("Describe the scene you want to generate.")
    r.setdefault("negative_prompt", "low quality, distorted anatomy, flicker, text, watermark")
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
    if assets and assets.get("reference") and r["task"] not in model_by_id(r["model_id"]).get("reference_tasks", []):
        raise WorkflowError("This model/task does not support an additional reference image.")
    files = {"source": "source.mp4" if r["task"] in {"inpaint", "restyle"} else "source.png", "mask": "mask.png", "reference": "reference.png"}
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
    if r["model_id"] == "wan-vace":
        model = node("model", "UNETLoader", unet_name="wan2.1_vace_1.3B_fp16.safetensors", weight_dtype="default")
        model = node("shift", "ModelSamplingSD3", model=model, shift=5.0)
        clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
        vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
        positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
        negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
        extra = {}
        if editing:
            control_video = source
            if r["task"] == "inpaint":
                # Official VACE inpainting blanks the selected pixels before
                # encoding both inactive and reactive conditioning streams.
                inverted = node("inverse_mask", "InvertMask", mask=mask)
                cleared = node("mask_image", "MaskToImage", mask=inverted)
                control_video = node("masked_guide", "ImageCompositeMasked", destination=source, source=cleared, x=0, y=0, resize_source=True, mask=mask)
            extra.update(control_video=control_video, control_masks=mask)
        if r["task"] == "image-to-video":
            # VACE's reference input is identity/style guidance, not an opening
            # frame. Its native control branch pads this known frame with neutral
            # video and white (generatable) masks for the remaining time steps.
            first_mask = node("first_frame_mask", "SolidMask", value=0.0, width=width, height=height)
            extra.update(control_video=source, control_masks=first_mask)
        elif assets and assets.get("reference"):
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
    finish = {}
    if editing and r["task"] == "inpaint":
        finish.update(source=source, mask=blend, match_lighting=r["effect_id"] == "remove-object")
    if audio:
        finish["audio"] = audio
    node("save", "OpenFrameSaveVideo", images=images, fps=fps, frames=frames, filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=bool(r.get("preserve_outside_mask", True)), preserve_audio=bool(r.get("preserve_audio", True)), source_filename=files["source"] if editing else "", trim_start=float(r.get("trim_start", 0)), export_mask=bool(r.get("export_mask", True)), **finish)
    return graph
