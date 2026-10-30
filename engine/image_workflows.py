"""Native FLUX.2 Klein image graphs, adapted from official Comfy templates."""


def build_image_workflow(request, assets=None):
    r, files, graph = request, dict(assets or {}), {}
    def node(name, class_type, **inputs):
        graph[name] = {"class_type": class_type, "inputs": inputs, "_meta": {"title": class_type}}
        return [name, 0]

    if r["model_id"] == "birefnet":
        image = node("image", "LoadImage", image=files.get("source", "source.png"))
        model = node("model", "LoadBackgroundRemovalModel", bg_removal_name="birefnet.safetensors")
        foreground = node("foreground", "RemoveBackground", bg_removal_model=model, image=image)
        # JoinImageWithAlpha follows Comfy's inverse-alpha mask convention.
        inverse = node("inverse_alpha", "InvertMask", mask=foreground)
        rgba = node("alpha", "JoinImageWithAlpha", image=image, alpha=inverse)
        prefix = "".join(c for c in str(r.get("job_id", "OpenFrame")) if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        node("save", "SaveImage", images=rgba, filename_prefix="openframe/" + prefix)
        return graph

    model = node("model", "UNETLoader", unet_name="flux-2-klein-4b-fp8.safetensors", weight_dtype="default")
    clip = node("text_encoder", "CLIPLoader", clip_name="qwen_3_4b.safetensors", type="flux2", device="default")
    vae = node("vae", "VAELoader", vae_name="flux2-vae.safetensors")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "ConditioningZeroOut", conditioning=positive)
    references = []
    if r["task"] == "image-edit":
        references.append(("image", files.get("source", "source.png")))
    if files.get("reference") or r.get("reference_asset_id"):
        references.append(("reference", files.get("reference", "reference.png")))
    count = len(r.get("reference_asset_ids") or [])
    for index in range(max(count, sum(key.startswith("reference_") for key in files))):
        role = f"reference_{index}"
        references.append((role, files.get(role, role + ".png")))
    if len(references) > 4:
        raise ValueError("FLUX.2 Klein accepts at most four reference images in this build, including the source image.")
    for name, filename in references:
        image = node(name, "LoadImage", image=filename)
        # References keep their own aspect ratio; canvas size is independent.
        image = node(name + "_resize", "ImageScaleToTotalPixels", image=image, upscale_method="lanczos", megapixels=1.0, resolution_steps=1)
        latent = node(name + "_encode", "VAEEncode", pixels=image, vae=vae)
        positive = node(name + "_positive", "ReferenceLatent", conditioning=positive, latent=latent)
        negative = node(name + "_negative", "ReferenceLatent", conditioning=negative, latent=latent)
    latent = node("empty", "EmptyFlux2LatentImage", width=r["width"], height=r["height"], batch_size=r["batch_size"])
    noise = node("noise", "RandomNoise", noise_seed=r["seed"])
    guider = node("guider", "CFGGuider", model=model, positive=positive, negative=negative, cfg=r["guidance"])
    sampler = node("sampler", "KSamplerSelect", sampler_name="euler")
    sigmas = node("sigmas", "Flux2Scheduler", steps=r["steps"], width=r["width"], height=r["height"])
    latent = node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=latent)
    image = node("decode", "VAEDecode", samples=latent, vae=vae)
    prefix = "".join(c for c in str(r.get("job_id", "OpenFrame")) if c.isalnum() or c in "-_")[:80] or "OpenFrame"
    node("save", "SaveImage", images=image, filename_prefix="openframe/" + prefix)
    return graph
