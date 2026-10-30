"""LongCat Avatar 1.5's actual Whisper/DMD path through the pinned Wan wrapper."""


def build_longcat_workflow(request, assets=None):
    r, graph = request, {}
    files = {"source": "source.png", "audio": "speech.wav", **(assets or {})}

    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    image = node("image", "LoadImage", image=files["source"])
    image = node("portrait_fit", "ImageScale", image=image, upscale_method="lanczos", width=r["width"], height=r["height"], crop="center")
    speech = node("speech", "LoadAudio", audio=files["audio"])
    speech = node("speech_range", "TrimAudioDuration", audio=speech, start_index=r.get("audio_start", 0), duration=r["frames"] / r["fps"])
    whisper = node("whisper", "OpenFrameWhisperLoader", precision="bf16")
    features = node("speech_features", "LongCatAvatarWhisperEmbeds", whisper_model=whisper, audio_1=speech, normalize_loudness=True, num_frames=r["frames"], fps=r["fps"], audio_scale=r.get("audio_conditioning_strength", 1.0), audio_cfg_scale=1.0, multi_audio_type="para")
    # Native CLIP plus the wrapper's published bridge reuses the cached scaled
    # UMT5. Its own legacy T5 loader explicitly rejects scaled FP8 checkpoints.
    clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    text = node("text_bridge", "WanVideoTextEmbedBridge", positive=positive, negative=negative)
    vae = node("vae", "WanVideoVAELoader", model_name="wan_2.1_vae.safetensors", precision="bf16", use_cpu_cache=False)
    reference = node("portrait_latent", "WanVideoEncode", vae=vae, image=image, enable_vae_tiling=False, tile_x=512, tile_y=512, tile_stride_x=256, tile_stride_y=256, noise_aug_strength=0.0, latent_strength=1.0)
    conditioning = node("condition", "WanVideoLongCatAvatarExtendEmbeds", prev_latents=reference, audio_embeds=features, num_frames=r["frames"], overlap=1, frames_processed=0, if_not_enough_audio="pad_with_start", ref_frame_index=10, ref_mask_frame_range=3, ref_latent=reference)
    # The pinned low-memory merge crashes inside an in-place parameter copy.
    # Use the wrapper's normal replacement path for offloaded weights instead.
    lora = node("distill", "WanVideoLoraSelect", lora="LongCat-Avatar-15_dmd_distill_lora_rank128_bf16.safetensors", strength=1.0, low_mem_load=False, merge_loras=True)
    model = node("model", "WanVideoModelLoader", model="LongCat-Avatar-15_bf16.safetensors", base_precision="bf16", quantization="disabled", load_device="offload_device", attention_mode="sdpa", lora=lora, rms_norm_function="default")
    scheduler = node("scheduler", "OpenFrameLongCat15Scheduler")
    latent = node("sample", "WanVideoSamplerv2", model=model, image_embeds=conditioning, text_embeds=text, cfg=r["guidance"], seed=r["seed"], force_offload=True, scheduler=scheduler, add_noise_to_samples=False)
    images = node("decode", "WanVideoDecode", vae=vae, samples=latent, enable_vae_tiling=False, tile_x=512, tile_y=512, tile_stride_x=256, tile_stride_y=256, normalization="default")
    # Conditioning uses normalized speech features; final audio retains the
    # original trimmed recording rather than silently changing its loudness.
    node("save", "OpenFrameSaveVideo", images=images, audio=speech, fps=r["fps"], frames=r["frames"], filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=False, preserve_audio=True, source_filename="", trim_start=0, export_mask=False, encoding_quality=r.get("encoding_quality", "standard"))
    return graph
