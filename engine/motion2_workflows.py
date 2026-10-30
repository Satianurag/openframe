"""Native Wan Animate 2 driving-frame conditioning; no pose-extractor substitute."""


def build_motion2_workflow(request, assets=None):
    r, graph = request, {}
    files = {"source": "source.mp4", "reference": "reference.png", **(assets or {})}

    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    source = node("source", "OpenFrameVideoInput", filename=files["source"], width=r["width"], height=r["height"], frames=r["frames"], fps=r["fps"], mask_filename="", track_mask=False, mask_dilation=0, mask_feather=0, trim_start=r.get("trim_start", 0), tracking_method="static")
    reference = node("reference", "LoadImage", image=files["reference"])
    # Official template node590 fits the reference before BOTH VAE and vision
    # conditioning; otherwise those branches see different subject framing.
    reference = node("reference_fit", "ImageScale", image=reference, upscale_method="area",
                     width=r["width"], height=r["height"], crop="center")
    distilled = r["model_id"] == "wan-animate-2-distilled"
    filename = "wan_animate_2_distill_bf16.safetensors" if distilled else "wan_animate_2_bf16.safetensors"
    model = node("model", "UNETLoader", unet_name=filename, weight_dtype="default")
    model = node("shift", "ModelSamplingSD3", model=model, shift=5.0)
    # Keep full-precision cached pose features in system RAM. The published
    # single-GPU Comfy path supports this without four-GPU streaming claims.
    model = node("pose_cache", "WanAnimate2Cache", model=model, device="cpu", dtype="default")
    clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
    vision = node("vision", "CLIPVisionLoader", clip_name="clip_vision_h.safetensors")
    identity = node("reference_vision", "CLIPVisionEncode", clip_vision=vision, image=reference, crop="none")
    first = node("source_first", "ImageFromBatch", image=source, batch_index=0, length=1)
    motion_vision = node("motion_vision", "CLIPVisionEncode", clip_vision=vision, image=first, crop="none")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    # A missing driving-motion caption is empty in the native template. Target
    # appearance text must not be copied into this separate conditioning branch.
    motion = node("motion_prompt", "CLIPTextEncode", clip=clip, text=r.get("motion_prompt") or "")
    node("condition", "WanAnimate2ToVideo", positive=positive, negative=negative, vae=vae, width=r["width"], height=r["height"], length=r["frames"], batch_size=1, reference_image=reference, pose_video=source, clip_vision_output=identity, clip_vision_output_pose=motion_vision, positive_pose=motion, video_frame_offset=0, pose_strength=r.get("pose_strength", 1.0), pose_start_percent=r.get("pose_start_percent", 0.0), pose_end_percent=r.get("pose_end_percent", 1.0), reference_image_strength=r.get("reference_strength", 1.0))
    latent = node("sample", "KSampler", model=model, positive=["condition", 0], negative=["condition", 1], latent_image=["condition", 2], seed=r["seed"], steps=r["steps"], cfg=r["guidance"], sampler_name="euler", scheduler="simple", denoise=1.0)
    latent = node("trim_reference", "TrimVideoLatent", samples=latent, trim_amount=["condition", 3])
    images = node("decode", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    node("save", "OpenFrameSaveVideo", images=images, fps=r["fps"], frames=r["frames"], filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=False, preserve_audio=bool(r.get("preserve_audio", True)), source_filename=files["source"], trim_start=r.get("trim_start", 0), export_mask=False, encoding_quality=r.get("encoding_quality", "standard"))
    return graph
