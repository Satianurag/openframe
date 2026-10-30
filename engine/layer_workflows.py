"""Native graph following Comfy-Org's Qwen-Image-Layered blueprint."""


def build_layer_workflow(r, assets=None):
    files = assets or {}
    return {
        "source": {"class_type": "LoadImage", "inputs": {"image": files.get("source", "source.png")}},
        "resize": {"class_type": "ImageScale", "inputs": {"image": ["source", 0], "upscale_method": "lanczos", "width": r["width"], "height": r["height"], "crop": "disabled"}},
        "model": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_layered_bf16.safetensors", "weight_dtype": "default"}},
        "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["model", 0], "shift": 1.0}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_layered_vae.safetensors"}},
        "positive_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": r.get("prompt", "")}},
        "negative_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": r.get("negative_prompt", "")}},
        "encoded": {"class_type": "VAEEncode", "inputs": {"pixels": ["resize", 0], "vae": ["vae", 0]}},
        "positive": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["positive_text", 0], "latent": ["encoded", 0]}},
        "negative": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["negative_text", 0], "latent": ["encoded", 0]}},
        "latent": {"class_type": "EmptyQwenImageLayeredLatentImage", "inputs": {"width": r["width"], "height": r["height"], "layers": r["layer_count"], "batch_size": 1}},
        "sample": {"class_type": "KSampler", "inputs": {"model": ["sampling", 0], "positive": ["positive", 0], "negative": ["negative", 0], "latent_image": ["latent", 0], "seed": r["seed"], "steps": r["steps"], "cfg": r["guidance"], "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        # Keep entry zero as the regenerated full image for reconstruction checks.
        "split": {"class_type": "LatentCutToBatch", "inputs": {"samples": ["sample", 0], "dim": "t", "slice_size": 1}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["split", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "OpenFrameSaveLayers", "inputs": {"images": ["decode", 0], "source": ["resize", 0], "layer_count": r["layer_count"], "filename_prefix": str(r.get("job_id", "OpenFrame"))}},
    }
