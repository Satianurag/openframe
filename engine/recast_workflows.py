"""Adapt the pinned official SCAIL-2 Base/Extend graph to existing asset/save nodes."""


def build_recast_workflow(r, assets=None):
    files = {"source": "source.mp4", "reference": "reference.png", **(assets or {})}
    graph = {}
    def node(name, cls, **inputs):
        graph[name] = {"class_type": cls, "inputs": inputs, "_meta": {"title": cls}}
        return [name, 0]

    width, height, frames = r["width"], r["height"], r["frames"]
    manual = bool(files.get("mask") or r.get("mask_asset_id"))
    source = node("source", "OpenFrameVideoInput", filename=files["source"], width=width, height=height,
                  frames=frames, fps=r["fps"], trim_start=r.get("trim_start", 0),
                  mask_filename=files.get("mask", "mask.png") if manual else "", track_mask=False,
                  tracking_method="static", mask_dilation=0, mask_feather=0, edit_margin=0,
                  feather_method="smooth-inward")
    reference = node("reference", "LoadImage", image=files["reference"])
    sam = node("sam", "CheckpointLoaderSimple", ckpt_name="sam3.1_multiplex_fp16.safetensors")
    subject = node("subject", "CLIPTextEncode", clip=["sam", 1], text="human")
    selection = {"conditioning": subject}
    if manual:
        initial_image = node("initial_mask_image", "MaskToImage", mask=["source", 1])
        first = node("initial_mask_frame", "ImageFromBatch", image=initial_image, batch_index=0, length=1)
        initial = node("initial_mask", "ImageToMask", image=first, channel="red")
        selection = {"initial_mask": initial}
    driving = node("performer_track", "SAM3_VideoTrack", images=source, model=sam,
                   detection_threshold=.5, max_objects=1, detect_interval=1, **selection)
    ref_track = node("reference_track", "SAM3_VideoTrack", images=reference, model=sam,
                     conditioning=subject, detection_threshold=.5, max_objects=1, detect_interval=1)
    colors = node("identity_colors", "SCAIL2ColoredMask", driving_track_data=driving,
                  ref_track_data=ref_track, object_indices="", sort_by="left_to_right", replacement_mode=True)
    mask = node("performer_mask", "SAM3_TrackToMask", track_data=driving, object_indices="")
    checked = node("recast_masks", "OpenFrameRecastMasks", driving_mask=mask, pose_colors=colors,
                   reference_colors=["identity_colors", 1], edit_margin=r["mask_edit_margin"],
                   feather=int(r.get("mask_feather", 6)))
    vae_reference = reference
    if r.get("recast_reference_cleanup"):
        vae_reference = node("clean_reference", "OpenFrameReferenceForeground", reference_image=reference,
                             reference_colors=["recast_masks", 1], width=width, height=height)
    model = node("model", "UNETLoader", unet_name="wan2.1_14B_SCAIL_2_fp16.safetensors", weight_dtype="default")
    model = node("dpo", "LoraLoaderModelOnly", model=model, lora_name="wan2.1_SCAIL_2_DPO_lora_bf16.safetensors", strength_model=1.0)
    model = node("shift", "ModelSamplingSD3", model=model, shift=5.0)
    vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
    clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r.get("negative_prompt", ""))
    vision = node("vision", "CLIPVisionLoader", clip_name="clip_vision_h.safetensors")
    encoded = node("vision_reference", "CLIPVisionEncode", clip_vision=vision, image=reference, crop="none")
    sampler = node("sampler", "KSamplerSelect", sampler_name="euler")
    sigmas = node("sigmas", "BasicScheduler", model=model, scheduler="simple", steps=r["steps"], denoise=1.0)

    # Native 81-frame windows with five anchored overlap frames. Source RGB and
    # masks remain the full sequence; WanSCAILToVideo slices both at its offset.
    total, chunk, merged, raw = 0, 0, None, None
    while total < frames:
        length = min(81, frames - total + (5 if chunk else 0))
        condition = "recast_condition_" + str(chunk)
        extra = {"previous_frames": merged} if chunk else {}
        node(condition, "WanSCAILToVideo", positive=positive, negative=negative, vae=vae,
             width=width, height=height, length=length, batch_size=1, pose_video=source,
             pose_video_mask=checked, replacement_mode=True, pose_strength=1.0, pose_start=0.0,
             pose_end=1.0, reference_image=vae_reference, reference_image_mask=["recast_masks", 1],
             clip_vision_output=encoded, video_frame_offset=total, previous_frame_count=5, **extra)
        latent = node("sample_" + str(chunk), "SamplerCustom", model=model, add_noise=True,
                      noise_seed=r["seed"], cfg=r["guidance"], positive=[condition, 0],
                      negative=[condition, 1], sampler=sampler, sigmas=sigmas, latent_image=[condition, 2])
        decoded = node("decode_" + str(chunk), "VAEDecode", samples=latent, vae=vae)
        if chunk:
            tail = node("previous_last_" + str(chunk), "ImageFromBatch", image=merged, batch_index=-1, length=1)
            corrected = node("color_match_" + str(chunk), "ColorTransfer", image_target=decoded,
                             image_ref=tail, method="reinhard_lab", source_stats="per_frame", strength=1.0)
            current = node("trim_overlap_" + str(chunk), "ImageFromBatch", image=corrected, batch_index=5, length=length - 5)
            raw_current = node("trim_raw_" + str(chunk), "ImageFromBatch", image=decoded, batch_index=5, length=length - 5)
            merged = node("join_" + str(chunk), "ImageBatch", image1=merged, image2=current)
            raw = node("join_raw_" + str(chunk), "ImageBatch", image1=raw, image2=raw_current)
        else:
            merged = raw = decoded
        total += length - (5 if chunk else 0)
        chunk += 1

    support = ["recast_masks", 2]
    if r.get("recast_composite_tracking", "native") in {"official", "official-union"}:
        if manual:
            raise ValueError("A manual performer mask requires native composite tracking.")
        extra = {"generated_images": merged} if r["recast_composite_tracking"] == "official-union" else {}
        support = node("composite_support", "OpenFrameRecastOfficialSupport", images=source,
                       selected_performer=mask, edit_margin=r["mask_edit_margin"], feather=int(r.get("mask_feather", 6)), **extra)

    save = dict(fps=r["fps"], frames=frames, filename_prefix=str(r.get("job_id", "OpenFrame")),
                source_filename=files["source"], trim_start=r.get("trim_start", 0), match_lighting=False,
                encoding_quality=r.get("encoding_quality", "high"))
    node("save_uncomposited", "OpenFrameSaveVideo", images=raw, preserve_outside_mask=False,
         preserve_audio=False, export_mask=False, **{**save, "filename_prefix": save["filename_prefix"] + "_raw"})
    node("save", "OpenFrameSaveVideo", images=merged, source=source, mask=support,
         preserve_outside_mask=bool(r.get("preserve_outside_mask", True)),
         preserve_audio=bool(r.get("preserve_audio", True)), export_mask=bool(r.get("export_mask", True)), **save)
    return graph
