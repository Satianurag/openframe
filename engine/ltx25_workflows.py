"""Explicit LTX 2.5 graphs adapted from the pinned upstream 2.5 templates.

Each editing operation selects its trained adapter. Temporal continuation uses
native video guide tokens; it is not the spatial outpainting adapter.
"""
from .workflows import _sigmas
from .catalog import allows_restyle_first_frame, model_by_id


def build_ltx25_workflow(r, assets=None):
    files = {"source": "source.png" if r["task"] == "image-to-video" else "source.mp4", "mask": "mask.png", **(assets or {})}
    graph = {}

    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    w, h, frames, fps, task = r["width"], r["height"], r["frames"], r["fps"], r["task"]
    prefix = "".join(c for c in str(r.get("job_id", "OpenFrame")) if c.isalnum() or c in "-_")[:100] or "OpenFrame"
    editing = task not in {"text-to-video", "image-to-video", "transition-video"}
    # Absent mode deliberately preserves historical editing graphs, which froze
    # source audio (or silence) regardless of the old generate_audio checkbox.
    generated_edit_audio = r.get("audio_mode") == "generated" and task in {"inpaint", "restyle"}
    masked = task in {"inpaint", "video-outpaint"}
    plate_fit = r.get("inpaint_composite_mode") == "plate-fit"
    canny = task == "restyle" and r.get("restyle_method") == "canny"
    water = task == "restyle" and r.get("restyle_method") == "water"
    if canny and (files.get("reference") or r.get("reference_asset_id")) and not allows_restyle_first_frame(model_by_id(r["model_id"]), r):
        raise ValueError("Edited first-frame Union-Control conditioning is unavailable for this operation.")
    tiled = task == "video-upscale" and r.get("upscale_mode") == "tiled-refine"
    refine = canny or r.get("video_refinement", "two-stage") == "two-stage" and task in {"text-to-video", "image-to-video", "transition-video", "inpaint", "video-outpaint"}
    multiple = 128 if canny else 64  # half-size generation, then half-size IC-LoRA reference latents
    fw, fh = (((w + multiple - 1) // multiple) * multiple, ((h + multiple - 1) // multiple) * multiple) if refine else (w, h)
    sw, sh = (fw // 2, fh // 2) if refine else (w, h)
    source = mask = blend = original = source_audio = final_image = midpoint = restyle_reference = None

    if task == "image-to-video":
        source = node("image", "LoadImage", image=files["source"])
        source = node("fit_image", "ImageScale", image=source, upscale_method="lanczos", width=w, height=h, crop="center")
    elif task == "transition-video":
        from .transitions import prepare_transition_images
        source, final_image = prepare_transition_images(node, r, files)
        if files.get("reference") or r.get("reference_asset_id"):
            midpoint = node("reference", "OpenFrameTransitionGuide", image=files.get("reference", "reference.png"),
                width=w, height=h, fit=r.get("reframe_fit", "crop"), anchor_x=r.get("anchor_x", .5),
                anchor_y=r.get("anchor_y", .5), frame_idx=(frames-1)//2, fps=fps)
    elif task in {"alpha-matte", "video-outpaint"} or task == "video-upscale" and not tiled:
        mode = {"alpha-matte": "pad-original", "video-outpaint": "outpaint", "video-upscale": "upscale-2x"}[task]
        source = node("source", "OpenFrameCanvasVideo", filename=files["source"], width=w, height=h, frames=frames, fps=fps, trim_start=r.get("trim_start", 0), mode=mode, source_scale=r.get("outpaint_scale", 1.0), anchor_x=r.get("outpaint_anchor_x", .5), anchor_y=r.get("outpaint_anchor_y", .5))
        mask, blend, original = ["source", 1], ["source", 1], ["source", 2]
    elif editing:
        scale = min(1, 1920 / max(w, h)) if tiled else 1
        source = node("source", "OpenFrameVideoInput", filename=files["source"], width=round(w * scale), height=round(h * scale), frames=r.get("context_frames", 17) if task == "video-extend" else frames, fps=fps, trim_start=r.get("trim_start", 0), mask_filename=files["mask"] if task == "inpaint" else "", track_mask=task == "inpaint" and r.get("mask_tracking", True), tracking_method=r["mask_tracking_method"] if task == "inpaint" else "static", mask_dilation=r.get("mask_dilation", 8) if task == "inpaint" else 0, mask_feather=r.get("mask_feather", 3) if task == "inpaint" else 0, feather_method="smooth-inward", edit_margin=r["mask_edit_margin"] if task == "inpaint" else 0)
        mask, blend = ["source", 1], ["source", 2]
        if tiled:
            source = node("upscale_reference", "ImageScale", image=source, upscale_method="lanczos", width=w, height=h, crop="disabled")
    if editing:
        source_audio = node("source_audio", "OpenFrameSourceAudio", filename=files["source"], frames=r.get("context_frames", 17) if task == "video-extend" else frames, fps=fps, trim_start=r.get("trim_start", 0), enabled=r.get("preserve_audio", True))

    model = node("model", "UNETLoader", unet_name="ltx-2.5-22b-distilled-transformer-bf16.safetensors", weight_dtype="default")
    vae = node("vae", "VAELoader", vae_name="ltx-2.5-video-vae-bf16.safetensors")
    audio_vae = node("audio_vae", "VAELoader", vae_name="ltx-2.5-audio-vae-bf16.safetensors")
    adapter = {
        "inpaint": "ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors",
        "video-outpaint": "ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors",
        "clean-plate": "ltx-2.5-22b-ic-lora-clean-plate-1.0.safetensors",
        "alpha-matte": "ltx-2.5-22b-ic-lora-alpha-gen-0.9.safetensors",
        "video-upscale": "ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors" if tiled else "ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors",
        "sdr-to-hdr": "ltx-2.5-22b-ic-lora-sdr-to-hdr-1.0.safetensors",
    }.get(task)
    if canny:
        adapter = "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
    elif water:
        # Water model card@7a458d0 explicitly selects the pinned official
        # V2V_ICLoRA_Single_Stage graph: full dry RGB guide, no upscaler pass.
        adapter = "ltx-2.5-22b-ic-lora-water-simulation-0.9.safetensors"
    if adapter:
        model = node("adapter", "LTXICLoRALoaderModelOnly", model=model, lora_name=adapter, strength_model=1.0)
    if task == "sdr-to-hdr":
        positive = node("positive", "LTXVLoadConditioning", file_name="ltx-2.5-22b-ic-lora-sdr-to-hdr-scene-emb.safetensors", device="cpu")
        negative = node("negative", "ConditioningZeroOut", conditioning=positive)
        source = node("hdr_input", "ImageColorSpace", image=source, source="sRGB", destination="HDR ACEScct")
    else:
        clip = node("text_encoder", "CLIPLoader", clip_name="gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", type="ltxv", device="default")
        prompt = r["prompt"]
        if r.get("enhance_prompt", True) and task != "alpha-matte":
            enhancer = node("prompt_encoder", "CLIPLoader", clip_name="gemma4_e2b_it_bf16.safetensors", type="ltxv", device="default")
            extra = {}
            if source is not None:
                extra["image"] = node("prompt_image", "ImageFromBatch", image=source, batch_index=0, length=1)
            prompt = node("enhance_prompt", "TextGenerateLTX2Prompt", clip=enhancer, prompt=prompt, max_length=600, sampling_mode="on", thinking=False, use_default_template=True, **{"sampling_mode.temperature": .01, "sampling_mode.top_k": 0, "sampling_mode.top_p": 1.0, "sampling_mode.min_p": 0.0, "sampling_mode.repetition_penalty": 1.15, "sampling_mode.seed": r["seed"], **extra})
        prompt = node("prompt_record", "OpenFrameRecordVideoPrompt", original=r["prompt"], model_prompt=prompt, enhanced=bool(r.get("enhance_prompt", True) and task != "alpha-matte"))
        positive = node("positive", "CLIPTextEncode", clip=clip, text=prompt)
        negative = node("negative", "CLIPTextEncode", clip=clip, text="" if task == "alpha-matte" else r["negative_prompt"])
    node("condition", "LTXVConditioning", positive=positive, negative=negative, frame_rate=fps)
    positive, negative = ["condition", 0], ["condition", 1]
    base_positive, base_negative = positive, negative
    full_source, full_mask = source, mask
    full_final_image = final_image
    full_midpoint = coarse_midpoint = midpoint
    inpaint_reference = None
    if task == "inpaint" and r.get("inpaint_reference_mode") == "edited-first-frame":
        # Lightricks/ComfyUI-LTXVideo@220e1d45, official2.5 Inpaint_Two_Stage:
        #3159 (compressed start image, strength.7), then5213 (uncompressed,1).
        # Fit once like the selected source interval; identical right/bottom
        # padding prevents native half-size encoding from changing the crop.
        inpaint_reference = node("reference", "OpenFrameInpaintFirstFrame",
            image=files.get("reference", "reference.png"), source_filename=files["source"],
            width=w, height=h, fps=fps, trim_start=r.get("trim_start", 0))
        reference_mask = node("reference_padding_mask", "SolidMask", value=1.0, width=w, height=h)
        inpaint_reference = node("reference_padding", "OpenFramePadForRefinement",
            images=inpaint_reference, mask=reference_mask)
    if refine and source is not None and not canny:
        if not masked:
            full_mask = node("padding_mask", "SolidMask", value=1.0, width=w, height=h)
        full_source = node("pad_refinement", "OpenFramePadForRefinement", images=source, mask=full_mask, **({"multiple": 128} if canny else {}))
        full_mask = ["pad_refinement", 1]
        if final_image is not None:
            full_final_image = node("pad_final_image", "OpenFramePadForRefinement", images=final_image, mask=["padding_mask", 0])
        if midpoint is not None:
            full_midpoint = node("pad_midpoint", "OpenFramePadForRefinement", images=midpoint, mask=["padding_mask", 0])
            coarse_midpoint = node("coarse_midpoint", "ImageScale", image=full_midpoint, upscale_method="lanczos", width=sw, height=sh, crop="disabled")
        coarse_source = node("coarse_source", "ImageScale", image=full_source, upscale_method="lanczos", width=sw, height=sh, crop="disabled")
        if masked:
            mask_image = node("mask_image", "MaskToImage", mask=full_mask)
            mask_image = node("coarse_mask_image", "ImageScale", image=mask_image, upscale_method="nearest-exact", width=sw, height=sh, crop="disabled")
            coarse_mask = node("coarse_mask", "ImageToMask", image=mask_image, channel="red")
    else:
        coarse_source, coarse_mask = source, mask
    latent = node("empty", "EmptyLTXVLatentVideo", width=sw, height=sh, length=frames, batch_size=1)

    def endpoints(stage, pos, neg, lat, first, last=None, middle=None):
        node(stage + "_first", "LTXVAddGuide", positive=pos, negative=neg, vae=vae, latent=lat, image=first, frame_idx=0, strength=1.0)
        pos, neg, lat = [stage + "_first", 0], [stage + "_first", 1], [stage + "_first", 2]
        if last is not None:
            node(stage + "_last", "LTXVAddGuide", positive=pos, negative=neg, vae=vae, latent=lat, image=last, frame_idx=-1, strength=1.0)
            pos, neg, lat = [stage + "_last", 0], [stage + "_last", 1], [stage + "_last", 2]
        if middle is not None:
            node(stage + "_middle", "LTXVAddGuide", positive=pos, negative=neg, vae=vae, latent=lat, image=middle, frame_idx=(frames-1)//2, strength=1.0)
            pos, neg, lat = [stage + "_middle", 0], [stage + "_middle", 1], [stage + "_middle", 2]
        return pos, neg, lat

    guided = bool(adapter) or task in {"video-extend", "transition-video"}
    if task == "image-to-video":
        processed = node("preprocess_image", "LTXVPreprocess", image=coarse_source, img_compression=18)
        latent = node("image_condition", "LTXVImgToVideoInplace", vae=vae, image=processed, latent=latent, strength=.7 if refine else 1.0, bypass=False)
    elif task == "video-extend" and r.get("extension_direction", "sequel") == "prequel":
        count = r["context_frames"]
        first = node("context_first", "ImageFromBatch", image=source, batch_index=0, length=1)
        node("guide_first", "LTXVAddGuide", positive=positive, negative=negative, vae=vae, latent=latent, image=first, frame_idx=frames-count, strength=1.0)
        positive, negative, latent = ["guide_first", 0], ["guide_first", 1], ["guide_first", 2]
        if count > 1:
            tail = node("context_tail", "ImageFromBatch", image=source, batch_index=1, length=count-1)
            guard = node("context_guard", "ImageFromBatch", image=source, batch_index=count-1, length=1)
            tail = node("context_tail_padded", "ImageBatch", image1=tail, image2=guard)
            # Native LTX prepends a causal VAE slot for mid-video guides and
            # crops to8n+1; the final guard is discarded, keeping all8n real frames.
            node("guide_tail", "LTXVAddGuide", positive=positive, negative=negative, vae=vae, latent=latent, image=tail, frame_idx=frames-count+1, strength=1.0)
            positive, negative, latent = ["guide_tail", 0], ["guide_tail", 1], ["guide_tail", 2]
    elif task in {"video-extend", "transition-video"}:
        positive, negative, latent = endpoints("guide", positive, negative, latent, coarse_source, full_final_image, coarse_midpoint)
    elif canny:
        # The pinned Union-Control template explicitly offers this Canny branch.
        # Keep its complete full-noise8 + latent2x/refine3 recipe, rather than
        # applying the adapter to the legacy partial-denoise source latent.
        # Annotate before any half-resolution RGB resize: upstream5026 ->4991.
        detector_source = node("canny_source_scale", "ResizeImageMaskNode", input=source, resize_type="scale shorter dimension", scale_method="lanczos", **{"resize_type.shorter_size": 544})
        edges = node("restyle_control", "OpenFrameCannyGuide", images=detector_source, low_threshold=92, high_threshold=200, resolution=512)
        # Unlike the template's annotation-derived canvas, the app has an
        # explicit output size. Align edges without cropping source geometry.
        edges = node("control_fit", "ImageScale", image=edges, upscale_method="lanczos", width=w, height=h, crop="disabled")
        control_mask = node("control_padding_mask", "SolidMask", value=1.0, width=w, height=h)
        edges = node("pad_refinement", "OpenFramePadForRefinement", images=edges, mask=control_mask, multiple=128)
        if files.get("reference") or r.get("reference_asset_id"):
            # Upstream3159 precedes IC-LoRA;4970 repeats the same image after2x.
            # Fit/pad once to the actual full canvas so native half-size encoding
            # cannot center-crop a different aspect ratio from the edge guide.
            restyle_reference = node("reference", "OpenFrameRestyleFirstFrame",
                image=files.get("reference", "reference.png"), source_filename=files["source"], width=w, height=h, fps=fps)
            restyle_reference = node("reference_padding", "OpenFramePadForRefinement",
                images=restyle_reference, mask=control_mask, multiple=multiple)
            latent = node("first_frame_condition", "LTXVImgToVideoInplace", vae=vae,
                image=restyle_reference, latent=latent, strength=1.0, bypass=False)
        node("guide", "LTXAddVideoICLoRAGuide", positive=positive, negative=negative, vae=vae, latent=latent, image=edges, frame_idx=0, strength=1.0, latent_downscale_factor=["adapter", 1], crop="disabled", use_tiled_encode=False, tile_size=256, tile_overlap=64)
        positive, negative, latent = ["guide", 0], ["guide", 1], ["guide", 2]
    elif task == "restyle" and not water:
        latent = node("source_latent", "VAEEncodeTiled", pixels=source, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    elif adapter:
        if inpaint_reference is not None:
            processed = node("preprocess_inpaint_reference", "LTXVPreprocess", image=inpaint_reference, img_compression=18)
            latent = node("inpaint_first_frame", "LTXVImgToVideoInplace", vae=vae,
                image=processed, latent=latent, strength=.7, bypass=False)
        guide = node("green_guide", "OpenFrameGreenFill", images=coarse_source, mask=coarse_mask) if masked else source
        node("guide", "LTXAddVideoICLoRAGuide", positive=positive, negative=negative, vae=vae, latent=latent, image=guide, frame_idx=0, strength=r["strength"] if masked else 1.0, latent_downscale_factor=2.0 if task == "video-upscale" and not tiled else 1.0, crop="disabled", use_tiled_encode=True, tile_size=256, tile_overlap=64, use_streaming=tiled, tile_frames=97)
        positive, negative, latent = ["guide", 0], ["guide", 1], ["guide", 2]

    noise = node("noise", "RandomNoise", noise_seed=r["seed"])
    sampler = node("sampler", "KSamplerSelect", sampler_name="euler" if tiled else "euler_ancestral")
    sigmas = node("sigmas", "ManualSigmas", sigmas=_sigmas(r["steps"], r["strength"] if task == "restyle" and not canny and not water else 1.0))
    audio_samples = None
    if tiled:
        latent = node("sample", "LTXVTiledFusionSampler", model=model, positive=positive, negative=negative, latents=latent, sigmas=sigmas, sampler=sampler, seed=r["seed"], cfg=r["guidance"], tile_width=576 if h > w else 1024, tile_height=1024 if h > w else 576, overlap_frac=.5, blend_var=.05, grid_cycle=1, tile_frames=97, vae=vae)
    else:
        audio_latent = node("audio_latent", "LTXVEmptyLatentAudio", frames_number=frames, frame_rate=fps, batch_size=1, audio_vae=audio_vae)
        if editing and task != "video-extend" and not generated_edit_audio:
            audio_latent = node("encode_source_audio", "VAEEncodeAudio", audio=source_audio, vae=audio_vae)
            node("freeze_audio", "LTXVSetAudioRefTokens", positive=positive, negative=negative, audio_latent=audio_latent)
            positive, negative, audio_latent = ["freeze_audio", 0], ["freeze_audio", 1], ["freeze_audio", 2]
        latent = node("av_latent", "LTXVConcatAVLatent", video_latent=latent, audio_latent=audio_latent)
        guider = node("guider", "CFGGuider", model=model, positive=positive, negative=negative, cfg=r["guidance"])
        node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=latent)
        latent = node("separate", "LTXVSeparateAVLatent", av_latent=["sample", 1])
        audio_samples = ["separate", 1]
        if guided:
            node("crop_guides", "LTXVCropGuides", positive=positive, negative=negative, latent=latent)
            positive, negative, latent = ["crop_guides", 0], ["crop_guides", 1], ["crop_guides", 2]
    if refine:
        if masked:
            coarse = node("decode_coarse", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
            plate = node("coarse_plate", "ImageCompositeMasked", destination=coarse_source, source=coarse, mask=coarse_mask, x=0, y=0, resize_source=False)
            coarse = node("blend_coarse", "LTXVLaplacianPyramidBlend", image_a=coarse, image_b=plate, mask=coarse_mask, trim_to_shortest=False, mask_low_res_dilation=5)
            enlarged = node("upscale_refinement", "ImageScale", image=coarse, upscale_method="lanczos", width=fw, height=fh, crop="disabled")
            latent = node("encode_refinement", "VAEEncodeTiled", pixels=enlarged, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
            if inpaint_reference is not None:
                latent = node("refined_inpaint_first_frame", "LTXVImgToVideoInplace", vae=vae,
                    image=inpaint_reference, latent=latent, strength=1.0, bypass=False)
        else:
            upscaler = node("upscale_model", "LatentUpscaleModelLoader", model_name="ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors")
            latent = node("upscale_refinement", "LTXVLatentUpsampler", samples=latent, upscale_model=upscaler, vae=vae)
            if canny and restyle_reference is not None:
                latent = node("refined_first_frame_condition", "LTXVImgToVideoInplace", vae=vae,
                    image=restyle_reference, latent=latent, strength=1.0, bypass=False)
            if task == "image-to-video":
                latent = node("refined_image_condition", "LTXVImgToVideoInplace", vae=vae, image=full_source, latent=latent, strength=1.0, bypass=False)
            elif task == "transition-video":
                positive, negative, latent = endpoints("refinement_guide", base_positive, base_negative, latent, full_source, full_final_image, full_midpoint)
        node("freeze_refinement_audio", "LTXVSetAudioRefTokens", positive=positive, negative=negative, audio_latent=audio_samples)
        positive, negative = ["freeze_refinement_audio", 0], ["freeze_refinement_audio", 1]
        latent = node("refinement_av", "LTXVConcatAVLatent", video_latent=latent, audio_latent=["freeze_refinement_audio", 2])
        guider = node("refinement_guider", "CFGGuider", model=model, positive=positive, negative=negative, cfg=r["guidance"])
        schedule = node("refinement_sigmas", "ManualSigmas", sigmas="0.725, 0.421875, 0" if masked else "0.909375, 0.725, 0.421875, 0")
        fine_sampler = node("refinement_sampler", "KSamplerSelect", sampler_name="euler" if masked or canny else "euler_ancestral")
        node("sample_refinement", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=fine_sampler, sigmas=schedule, latent_image=latent)
        latent = node("separate_refinement", "LTXVSeparateAVLatent", av_latent=["sample_refinement", 1])
        audio_samples = ["separate_refinement", 1]
        if task == "transition-video":
            node("crop_refinement_guides", "LTXVCropGuides", positive=positive, negative=negative, latent=latent)
            latent = ["crop_refinement_guides", 2]
    images = node("decode", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    uncomposited = images
    if r.get("export_uncomposited") and refine and (fw, fh) != (w, h):
        uncomposited = node("crop_uncomposited", "ImageCrop", image=images, width=w, height=h, x=0, y=0)
    if refine and masked and not plate_fit:
        plate = node("refinement_plate", "ImageCompositeMasked", destination=full_source, source=images, mask=full_mask, x=0, y=0, resize_source=False)
        images = node("blend_refinement", "LTXVLaplacianPyramidBlend", image_a=images, image_b=plate, mask=full_mask, trim_to_shortest=False, mask_low_res_dilation=6)
    if refine and (fw, fh) != (w, h):
        images = node("crop_refinement", "ImageCrop", image=images, width=w, height=h, x=0, y=0)
    if task == "alpha-matte":
        node("save", "OpenFrameSaveAlphaVideo", original=original, matte=images, fps=fps, filename_prefix=prefix, source_filename=files["source"], trim_start=r.get("trim_start", 0), preserve_audio=r.get("preserve_audio", True))
        return graph
    if task == "video-upscale" and not tiled:
        images = node("crop_upscale", "ImageCrop", image=images, width=r["source_width"] * 2, height=r["source_height"] * 2, x=0, y=0)
    audio = None
    if audio_samples is not None and r.get("generate_audio", True) and (not editing or generated_edit_audio):
        audio = node("decode_audio", "LTXVAudioVAEDecode", samples=audio_samples, audio_vae=audio_vae)
    if task == "video-extend":
        placement = "end" if r.get("extension_direction", "sequel") == "prequel" else "start"
        images = node("restore_context", "OpenFrameRestoreContext", images=images, context=source, placement=placement)
        audio_args = {}
        if r.get("generate_audio", True):
            audio_args["generated_audio"] = node("decode_audio", "LTXVAudioVAEDecode", samples=audio_samples, audio_vae=audio_vae)
        audio = node("extend_audio", "OpenFrameExtendAudio", context_audio=source_audio, frames=frames, fps=fps, generate_audio=r.get("generate_audio", True), placement=placement, **audio_args)
    if task == "transition-video":
        from .transitions import save_transition
        images = node("restore_endpoints", "OpenFrameRestoreContext", images=images, context=source, last_image=final_image)
        save_transition(node, r, files, images, audio)
        return graph
    if task == "sdr-to-hdr":
        output_format = r.get("hdr_output_format", "hevc10")
        color_space = "linear ACEScg" if output_format == "exr16" else "HDR"
        hdr = node("hdr_output", "ImageColorSpace", image=images, source="HDR ACEScct", destination=color_space)
        node("save", "OpenFrameSaveHDRVideo", images=hdr, fps=fps, frames=frames, filename_prefix=prefix + "_hdr", output_format=output_format, color_space=color_space, preserve_audio=r.get("preserve_audio", True), source_filename=files["source"], trim_start=r.get("trim_start", 0), encoding_quality=r.get("encoding_quality", "standard"))
        preview = node("hdr_preview", "ImageColorSpace", image=images, source="HDR ACEScct", destination="sRGB")
        node("save_preview", "OpenFrameSaveVideo", images=preview, fps=fps, frames=frames, filename_prefix=prefix + "_sdr_preview", preserve_outside_mask=False, preserve_audio=r.get("preserve_audio", True), source_filename=files["source"], trim_start=r.get("trim_start", 0), export_mask=False, encoding_quality=r.get("encoding_quality", "standard"))
        return graph
    finish = {"audio": audio} if audio is not None else {}
    if r.get("export_uncomposited"):
        node("save_uncomposited", "OpenFrameSaveVideo", images=uncomposited, fps=fps, frames=frames,
             filename_prefix=prefix + "_uncomposited", preserve_outside_mask=False,
             preserve_audio=r.get("preserve_audio", True), source_filename=files["source"],
             trim_start=r.get("trim_start", 0), export_mask=False,
             encoding_quality=r.get("encoding_quality", "standard"), **finish)
    if plate_fit:
        images = node("fit_plate", "OpenFrameFitPlate", images=images, source=source, mask=blend)
    if masked:
        finish.update(source=source, mask=blend, match_lighting=r["effect_id"] == "remove-object")
    node("save", "OpenFrameSaveVideo", images=images, fps=fps, frames=frames, filename_prefix=prefix, preserve_outside_mask=masked and r.get("preserve_outside_mask", True), preserve_audio=r.get("preserve_audio", True), source_filename=files["source"] if editing and task != "video-extend" else "", trim_start=r.get("trim_start", 0), export_mask=masked and r.get("export_mask", True), encoding_quality=r.get("encoding_quality", "standard"), **finish)
    return graph
