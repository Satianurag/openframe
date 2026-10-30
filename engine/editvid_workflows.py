"""Pinned native EditVid inference; no model, sampler or provider substitution."""


def validate_editvid(r):
    if r.get("model_id") != "flux-klein-editvid":
        if r.get("restyle_source_prompt"):
            raise ValueError("A separate source-scene description is only consumed by EditVid.")
        return
    if r.get("provider", "local") != "local" or r.get("effect_id") != "restyle":
        raise ValueError("EditVid is an optional Local ComfyUI restyling profile with non-commercial 9B weights; no hosted route is supplied.")
    if not str(r.get("restyle_source_prompt", "")).strip():
        raise ValueError("Describe the original source scene separately from the desired style for EditVid inversion.")
    if any(r.get(key) for key in ("reference_asset_id", "reference_asset_ids", "mask_asset_id", "audio_asset_id", "image_layout", "character_adapter_id")):
        raise ValueError("EditVid uses the selected source video and two text descriptions; extra images, masks, recordings, layouts and adapters are unsupported.")
    if r.get("negative_prompt", "").strip() or r.get("enhance_prompt") or r.get("generate_audio") or r.get("restyle_method", "latent") != "latent":
        raise ValueError("The native EditVid recipe uses direct descriptions, no negative prompt, enhancer, Canny/Water method or generated audio.")
    if r["steps"] != 4 or r["guidance"] != 1 or r["strength"] != 1 or r.get("batch_size", 1) != 1:
        raise ValueError("This matched EditVid profile uses four steps, CFG 1, strength 1 and one result; temporal anchoring is fixed at the native 0.6 preset.")
    if r.get("audio_mode") not in {None, "source", "silent"}:
        raise ValueError("EditVid retains source audio or produces silence; it does not generate audio.")
    if r.get("source_width") and r.get("source_height") and r["source_width"] * r["source_height"] > 2097152:
        raise ValueError("This bounded EditVid profile accepts native source frames up to 2,097,152 pixels. Prepare an explicitly resized source before use.")


def build_editvid_workflow(r, assets=None):
    validate_editvid(r)
    source = (assets or {}).get("source", "source.mp4")
    return {
        "model": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-9b.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_8b.safetensors", "type": "flux2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "flux3-package-vae.safetensors"}},
        "source_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": r["restyle_source_prompt"]}},
        "edit_text": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": r["prompt"]}},
        "source": {"class_type": "OpenFrameEditVidInput", "inputs": {"filename": source, "frames": r["frames"], "fps": r["fps"], "trim_start": r.get("trim_start", 0)}},
        "resize": {"class_type": "ImageScale", "inputs": {"image": ["source", 0], "upscale_method": "lanczos", "width": r["width"], "height": r["height"], "crop": "center"}},
        "encode": {"class_type": "VAEEncode", "inputs": {"pixels": ["resize", 0], "vae": ["vae", 0]}},
        "sigmas": {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": r["width"], "height": r["height"]}},
        "sample": {"class_type": "EditVidSampler", "inputs": {"model": ["model", 0], "source": ["source_text", 0], "edit": ["edit_text", 0], "latent_video": ["encode", 0], "sigmas": ["sigmas", 0], "seed": r["seed"], "chunk_size": 4, "anchor_strength": .6, "correspondence_threshold": .4, "cycle_radius": 1.5, "token_keep_fraction": .5}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "OpenFrameSaveVideo", "inputs": {"images": ["decode", 0], "fps": r["fps"], "frames": r["frames"], "filename_prefix": str(r.get("job_id", "OpenFrame-EditVid")), "preserve_outside_mask": False, "preserve_audio": r.get("preserve_audio", True), "source_filename": source, "trim_start": r.get("trim_start", 0), "export_mask": False, "encoding_quality": r.get("encoding_quality", "high")}},
    }
