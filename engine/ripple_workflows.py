"""PaintAPlate/Ripple's native FFAF graph with OpenFrame media I/O.

Adapted from AInVFX/ainvfx-paintaplate, Apache-2.0, revision
1f4a5706e4fbec2f6bb5ae763460d03551392d15, tools/build_workflows.py:shot.
See docs/licenses/PaintAPlate-LICENSE.txt and docs/research/genjutsu-replacement.md.
The mask is used only for the final composite, never to green-fill the guide.
"""
from .ripple_models import RIPPLE_FILE, RIPPLE_PROMPT


def build_ripple_workflow(r, assets=None):
    from .workflows import WorkflowError
    if not r.get("reference_asset_id"):
        raise WorkflowError("Ripple requires an edited full starting frame, not only a text description.")
    files = {"source": "source.mp4", "mask": "mask.png", "reference": "reference.png", **(assets or {})}
    graph = {}

    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    w, h, frames, fps = r["width"], r["height"], r["frames"], r["fps"]
    prefix = "".join(c for c in str(r.get("job_id", "OpenFrame")) if c.isalnum() or c in "-_")[:100] or "OpenFrame"
    source = node("source", "OpenFrameVideoInput", filename=files["source"], width=w, height=h,
        frames=frames, fps=fps, trim_start=r.get("trim_start", 0), mask_filename=files["mask"],
        track_mask=r.get("mask_tracking", True), tracking_method=r["mask_tracking_method"],
        mask_dilation=0, mask_feather=r.get("mask_feather", 6), feather_method="smooth-inward",
        edit_margin=r["mask_edit_margin"])
    hero = node("reference", "LoadImage", image=files["reference"])
    hero = node("fit_reference", "ImageScale", image=hero, upscale_method="lanczos", width=w, height=h, crop="center")
    rest = node("source_after_first", "ImageFromBatch", image=source, batch_index=1, length=frames - 1)
    # The fixed two-input native ImageBatch is equivalent to upstream's dynamic
    # BatchImagesNode. It keeps guide length exactly equal to the source count.
    reference = node("reference_video", "ImageBatch", image1=hero, image2=rest)
    model = node("model", "UNETLoader", unet_name="ltx-2.5-22b-distilled-transformer-bf16.safetensors", weight_dtype="default")
    model = node("ripple", "LoraLoaderModelOnly", model=model, lora_name=RIPPLE_FILE, strength_model=1.35)
    clip = node("text_encoder", "CLIPLoader", clip_name="gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", type="ltxv", device="default")
    vae = node("vae", "VAELoader", vae_name="ltx-2.5-video-vae-bf16.safetensors")
    audio_vae = node("audio_vae", "VAELoader", vae_name="ltx-2.5-audio-vae-bf16.safetensors")
    prompt = node("prompt_record", "OpenFrameRecordVideoPrompt", original=r["prompt"],
        model_prompt=RIPPLE_PROMPT + ("\nChanged first frame: " + r["prompt"] if r["prompt"].strip() else ""), enhanced=False)
    positive = node("positive", "CLIPTextEncode", text=prompt, clip=clip)
    negative = node("negative", "CLIPTextEncode", text=r["negative_prompt"], clip=clip)
    node("condition", "LTXVConditioning", positive=positive, negative=negative, frame_rate=fps)
    latent = node("empty", "EmptyLTXVLatentVideo", width=w, height=h, length=frames, batch_size=1)
    node("guide", "LTXAddVideoICLoRAGuide", positive=["condition", 0], negative=["condition", 1],
        vae=vae, latent=latent, image=reference, frame_idx=0, strength=1.0,
        latent_downscale_factor=1.0, crop="disabled", use_tiled_encode=False,
        tile_size=256, tile_overlap=64, use_streaming=False, tile_frames=97)
    audio = node("empty_audio", "LTXVEmptyLatentAudio", audio_vae=audio_vae, frames_number=frames, frame_rate=fps, batch_size=1)
    noise = node("noise", "RandomNoise", noise_seed=r["seed"])
    guider = node("guider", "CFGGuider", model=model, positive=["guide", 0], negative=["guide", 1], cfg=r["guidance"])
    sampler = node("sampler", "KSamplerSelect", sampler_name="euler")
    schedule = node("schedule", "BasicScheduler", model=model, scheduler="simple", steps=r["steps"], denoise=1.0)
    av = node("av", "LTXVConcatAVLatent", video_latent=["guide", 2], audio_latent=audio)
    sampled = node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=schedule, latent_image=av)
    video = node("separate", "LTXVSeparateAVLatent", av_latent=sampled)
    node("crop_guides", "LTXVCropGuides", positive=["guide", 0], negative=["guide", 1], latent=video)
    decoded = node("decode", "VAEDecode", samples=["crop_guides", 2], vae=vae)
    common = dict(images=decoded, fps=fps, frames=frames, preserve_audio=r.get("preserve_audio", True),
        source_filename=files["source"], trim_start=r.get("trim_start", 0), encoding_quality=r.get("encoding_quality", "standard"))
    if r.get("export_uncomposited"):
        node("save_uncomposited", "OpenFrameSaveVideo", filename_prefix=prefix + "_uncomposited",
            preserve_outside_mask=False, export_mask=False, **common)
    node("save", "OpenFrameSaveVideo", filename_prefix=prefix, source=source, mask=["source", 2],
        preserve_outside_mask=r.get("preserve_outside_mask", True), match_lighting=False,
        export_mask=r.get("export_mask", True), **common)
    return graph
