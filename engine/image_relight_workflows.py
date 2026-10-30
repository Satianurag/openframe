"""Released dx8152 two-image multi-angle lighting graph; no prompt-only substitute."""
import math


def validate_image_brightness(r, model):
    value = float(r.get("image_brightness", 0))
    if not math.isfinite(value) or not -100 <= value <= 100:
        raise ValueError("Post-render brightness must be from -100 to 100 percent")
    if value and not model.get("supports_image_brightness"):
        raise ValueError("This model does not implement post-render image brightness")


def image_relight_size(width, height):
    """Native ImageScaleToTotalPixels(1 MP, step 1), then VAEEncode's 8-grid crop."""
    if not width or not height:
        raise ValueError("Image relighting requires the original source dimensions")
    scale = math.sqrt(1024 * 1024 / (width * height))
    return tuple(int(round(axis * scale)) // 8 * 8 for axis in (width, height))


def validate_image_relight(r):
    if r.get("task") != "image-edit" or r.get("effect_id") != "relight-image":
        raise ValueError("The directional lighting profile is only for Relight Image")
    if r.get("mask_asset_id") or r.get("reference_asset_ids") or r.get("image_layout") or r.get("character_adapter_id") or r.get("image_preservation", "none") != "none":
        raise ValueError("Directional relighting uses one subject and one lighting-map PNG, without masks, extra references, layout or adapters")
    if r.get("steps") != 8 or r.get("guidance") != 1 or r.get("batch_size", 1) != 1 or r.get("strength") != 1:
        raise ValueError("The released lighting recipe uses 8 steps, CFG 1, denoise 1 and one output")
    if r.get("negative_prompt", "").strip():
        raise ValueError("The released lighting recipe uses an empty negative prompt")
    if r.get("source_width") and r.get("source_height"):
        expected = image_relight_size(r["source_width"], r["source_height"])
        if (r["width"], r["height"]) != expected:
            raise ValueError(f"The released 1 MP lighting recipe outputs {expected[0]} × {expected[1]}")


def build_image_relight_workflow(r, assets=None):
    files = assets or {}
    graph = {
        "image": {"class_type": "LoadImage", "inputs": {"image": files.get("source", "source.png")}},
        "reference": {"class_type": "LoadImage", "inputs": {"image": files.get("reference", "lighting-map.png")}},
        "source_scale": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["image", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 1}},
        "map_scale": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["reference", 0], "upscale_method": "lanczos", "megapixels": 1.0, "resolution_steps": 1}},
        "model": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors", "weight_dtype": "default"}},
        "lightning": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["lighting", 0], "lora_name": "Qwen-Image-Lightning-8steps-V1.1.safetensors", "strength_model": 1.0}},
        "lighting": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["model", 0], "lora_name": "qwen-multi-angle-lighting-251121.safetensors", "strength_model": 1.0}},
        "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["lightning", 0], "shift": 3.0}},
        "norm": {"class_type": "CFGNorm", "inputs": {"model": ["sampling", 0], "strength": 1.0}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "positive": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "vae": ["vae", 0], "prompt": r["prompt"], "image1": ["source_scale", 0], "image2": ["map_scale", 0]}},
        "negative": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["clip", 0], "vae": ["vae", 0], "prompt": "", "image1": ["source_scale", 0], "image2": ["map_scale", 0]}},
        "latent": {"class_type": "VAEEncode", "inputs": {"pixels": ["source_scale", 0], "vae": ["vae", 0]}},
        "sample": {"class_type": "KSampler", "inputs": {"model": ["norm", 0], "positive": ["positive", 0], "negative": ["negative", 0], "latent_image": ["latent", 0], "seed": r["seed"], "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": str(r.get("job_id", "OpenFrame-Relight"))}},
    }
    if r.get("image_brightness", 0):
        graph["image_brightness"] = {"class_type": "OpenFrameImageBrightness", "inputs": {
            "image": ["decode", 0], "brightness": float(r["image_brightness"]),
        }}
        graph["save"]["inputs"]["images"] = ["image_brightness", 0]
    return graph
