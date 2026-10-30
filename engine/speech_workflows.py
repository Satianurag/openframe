"""Native Wan S2V: real wav2vec speech features and portrait conditioning."""


def build_speech_workflow(request, assets=None):
    r, graph = request, {}
    files = {"source": "source.png", "audio": "speech.wav", **(assets or {})}
    def node(name, class_type, **inputs):
        graph[name] = {"class_type": class_type, "inputs": inputs, "_meta": {"title": class_type}}
        return [name, 0]

    portrait = node("image", "LoadImage", image=files["source"])
    speech = node("speech", "LoadAudio", audio=files["audio"])
    speech = node("speech_range", "TrimAudioDuration", audio=speech, start_index=float(r.get("audio_start", 0)), duration=r["frames"] / r["fps"])
    encoder = node("audio_encoder", "AudioEncoderLoader", audio_encoder_name="wav2vec2_large_english_fp16.safetensors")
    features = node("encode_speech", "AudioEncoderEncode", audio_encoder=encoder, audio=speech)
    model = node("model", "UNETLoader", unet_name="wan2.2_s2v_14B_bf16.safetensors", weight_dtype="default")
    model = node("shift", "ModelSamplingSD3", model=model, shift=8.0)
    clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    node("condition", "WanSoundImageToVideo", positive=positive, negative=negative, vae=vae, width=r["width"], height=r["height"], length=r["frames"], batch_size=1, audio_encoder_output=features, ref_image=portrait)
    latent = node("sample", "KSampler", model=model, positive=["condition", 0], negative=["condition", 1], latent_image=["condition", 2], seed=r["seed"], steps=r["steps"], cfg=r["guidance"], sampler_name="uni_pc", scheduler="simple", denoise=1.0)
    # The official Comfy S2V template duplicates the first latent and trims
    # three decoded frames to avoid its overbaked opening-frame VAE artifact.
    first = node("first_latent", "LatentCut", samples=latent, dim="t", index=0, amount=1)
    latent = node("decode_padding", "LatentConcat", samples1=first, samples2=latent, dim="t")
    images = node("decode", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    images = node("trim_decode", "ImageFromBatch", image=images, batch_index=3, length=r["frames"])
    node("save", "OpenFrameSaveVideo", images=images, audio=speech, fps=r["fps"], frames=r["frames"], filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=False, preserve_audio=True, source_filename="", trim_start=0, export_mask=False)
    return graph
