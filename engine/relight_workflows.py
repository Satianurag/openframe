"""Active native Relight template lowered to portable source/sphere file inputs.

The disconnected Gemma API, preprocess and generated-audio preview nodes are
intentionally absent. FP8 Gemma is the explicitly disclosed cache substitution.
"""
from .relight_models import CHECKPOINT, ENCODER, DISTILL, ADAPTER


def normalize_relight(r, error):
    if r["effect_id"] != "relight" or r["task"] != "restyle":
        raise error("Sphere Relight is available only for the relight operation.")
    if not r.get("reference_asset_id") or r.get("reference_asset_ids") or r.get("mask_asset_id"):
        raise error("Sphere Relight needs one prepared lighting-sphere PNG and no mask.")
    if (r["width"], r["height"], r["fps"], r["steps"], r["guidance"], r["strength"]) != (1280, 704, 24, 8, 1, 1):
        raise error("The released Relight recipe uses 1280×704, 24 fps, 8 steps, CFG 1 and guide strength 1.")
    if r.get("enhance_prompt") or r.get("audio_mode") == "generated":
        raise error("Sphere Relight uses the literal caption and source or silent audio.")
    r["video_refinement"] = "single"
    r["enhance_prompt"] = False
    r["audio_mode"] = r.get("audio_mode") or ("source" if r.get("preserve_audio", True) else "silent")
    r["generate_audio"] = False
    r["preserve_audio"] = r["audio_mode"] == "source"
    if not r["prompt"].lower().startswith("relight the video to match the light-direction ball."):
        raise error("Start the Relight caption with ‘relight the video to match the light-direction ball.’ followed by the matching look and direction.")


def build_relight_workflow(r, assets=None):
    files = {"source": "source.mp4", "reference": "reference.png", **(assets or {})}
    graph = {}
    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    # Preserve source-native geometry for the released ImageScale center crop.
    # The portable video reader resamples the selected interval to the chosen FPS.
    width, height = int(r.get("source_width") or 1280), int(r.get("source_height") or 704)
    if max(width, height) > 2048:
        factor = 2048 / max(width, height)
        width, height = round(width * factor), round(height * factor)
    source = node("source", "OpenFrameVideoInput", filename=files["source"], width=width, height=height,
        frames=r["frames"], fps=24, trim_start=r.get("trim_start", 0), mask_filename="", track_mask=False,
        tracking_method="static", mask_dilation=0, mask_feather=0)
    source = node("center_source", "ImageScale", image=source, upscale_method="lanczos", width=1280, height=704, crop="center")
    sphere = node("relight_sphere", "OpenFrameRelightSphere", filename=files["reference"])
    sphere = node("sphere_scale", "ImageScale", image=sphere, upscale_method="area", width=143, height=143, crop="disabled")
    reference = node("sphere_overlay", "ImageCompositeMasked", destination=source, source=sphere, x=1115, y=22, resize_source=False)
    reference = node("guide_size", "ResizeImageMaskNode", input=reference,
        resize_type="scale shorter dimension", **{"resize_type.shorter_size": 704}, scale_method="lanczos")
    base = node("model", "CheckpointLoaderSimple", ckpt_name=CHECKPOINT)
    vae = ["model", 2]
    model = node("distill", "LoraLoaderModelOnly", model=base, lora_name=DISTILL, strength_model=.5)
    model = node("adapter", "LTXICLoRALoaderModelOnly", model=model, lora_name=ADAPTER, strength_model=1)
    clip = node("text_encoder", "LTXAVTextEncoderLoader", text_encoder=ENCODER, ckpt_name=CHECKPOINT, device="default")
    audio_vae = node("audio_vae", "LTXVAudioVAELoader", ckpt_name=CHECKPOINT)
    prompt = node("prompt_record", "OpenFrameRecordVideoPrompt", original=r["prompt"], model_prompt=r["prompt"], enhanced=False)
    positive = node("positive", "CLIPTextEncode", clip=clip, text=prompt)
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    node("condition", "LTXVConditioning", positive=positive, negative=negative, frame_rate=24)
    latent = node("empty", "EmptyLTXVLatentVideo", width=1280, height=704, length=r["frames"], batch_size=1)
    audio = node("empty_audio", "LTXVEmptyLatentAudio", audio_vae=audio_vae, frames_number=r["frames"], frame_rate=24, batch_size=1)
    node("guide", "LTXAddVideoICLoRAGuide", positive=["condition", 0], negative=["condition", 1], vae=vae,
        latent=latent, image=reference, frame_idx=0, strength=1, latent_downscale_factor=["adapter", 1],
        crop="disabled", use_tiled_encode=False, tile_size=256, tile_overlap=64)
    av = node("av", "LTXVConcatAVLatent", video_latent=["guide", 2], audio_latent=audio)
    guider = node("guider", "CFGGuider", model=model, positive=["guide", 0], negative=["guide", 1], cfg=1)
    noise = node("noise", "RandomNoise", noise_seed=r["seed"])
    sampler = node("sampler", "KSamplerSelect", sampler_name="euler_ancestral_cfg_pp")
    sigmas = node("sigmas", "ManualSigmas", sigmas="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0")
    node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=av)
    node("separate", "LTXVSeparateAVLatent", av_latent=["sample", 0])
    node("crop_guides", "LTXVCropGuides", positive=["guide", 0], negative=["guide", 1], latent=["separate", 0])
    images = node("decode", "LTXVTiledVAEDecode", vae=vae, latents=["crop_guides", 2],
        horizontal_tiles=2, vertical_tiles=2, overlap=6, last_frame_fix=False, working_device="auto", working_dtype="auto")
    node("save", "OpenFrameSaveVideo", images=images, fps=24, frames=r["frames"],
        filename_prefix=r.get("job_id", "OpenFrameRelight"), source_filename=files["source"],
        preserve_audio=r["preserve_audio"], trim_start=r.get("trim_start", 0),
        preserve_outside_mask=False, export_mask=False, match_lighting=False,
        encoding_quality=r.get("encoding_quality", "standard"))
    return graph
