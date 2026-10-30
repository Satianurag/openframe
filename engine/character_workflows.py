"""Wan Animate's actual pose/face conditioning and background-preserving mode."""


def build_character_workflow(request, assets=None):
    r, graph = request, {}
    files = {"source": "source.mp4", "reference": "reference.png", "mask": "mask.png", **(assets or {})}
    replacing = r["task"] == "character-replacement"
    width, height, frames, fps = r["width"], r["height"], r["frames"], r["fps"]
    def node(name, class_type, **inputs):
        graph[name] = {"class_type": class_type, "inputs": inputs, "_meta": {"title": class_type}}
        return [name, 0]

    source = node("source", "OpenFrameVideoInput", filename=files["source"], width=width, height=height, frames=frames, fps=fps, mask_filename=files["mask"] if replacing else "", track_mask=bool(r.get("mask_tracking", True)), mask_dilation=int(r.get("mask_dilation", 8)), mask_feather=int(r.get("mask_feather", 6)), trim_start=float(r.get("trim_start", 0)), tracking_method=r["mask_tracking_method"], feather_method="smooth-inward", edit_margin=r["mask_edit_margin"])
    reference = node("reference", "LoadImage", image=files["reference"])
    pose_model = node("pose_model", "OnnxDetectionModelLoader", vitpose_model="vitpose_h_wholebody_model.onnx", yolo_model="yolov10m.onnx", onnx_device="CPUExecutionProvider")
    # CPU ONNX makes the same preprocessing portable and releases GPU memory
    # before diffusion. This is actual landmark inference, not prompt guidance.
    detected = node("pose_detect", "PoseAndFaceDetection", model=pose_model, images=source, width=width, height=height, face_padding=0)
    pose = node("pose_draw", "DrawViTPose", pose_data=detected, width=width, height=height, retarget_padding=0, body_stick_width=-1, hand_stick_width=-1, draw_head=True)
    model = node("model", "UNETLoader", unet_name="Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", weight_dtype="default")
    model = node("distill", "LoraLoaderModelOnly", model=model, lora_name="lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", strength_model=1.0)
    if replacing:
        model = node("relight", "LoraLoaderModelOnly", model=model, lora_name="WanAnimate_relight_lora_fp16.safetensors", strength_model=1.0)
    model = node("shift", "ModelSamplingSD3", model=model, shift=8.0)
    clip = node("text_encoder", "CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default")
    vae = node("vae", "VAELoader", vae_name="wan_2.1_vae.safetensors")
    vision = node("vision", "CLIPVisionLoader", clip_name="clip_vision_h.safetensors")
    encoded_reference = node("vision_reference", "CLIPVisionEncode", clip_vision=vision, image=reference, crop="none")
    positive = node("positive", "CLIPTextEncode", clip=clip, text=r["prompt"])
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    extra = {}
    if replacing:
        black = node("background_black", "EmptyImage", width=width, height=height, batch_size=1, color=0)
        background = node("background", "ImageCompositeMasked", destination=source, source=black, x=0, y=0, resize_source=False, mask=["source", 1])
        extra.update(background_video=background, character_mask=["source", 1])
    node("condition", "WanAnimateToVideo", positive=positive, negative=negative, vae=vae, width=width, height=height, length=frames, batch_size=1, clip_vision_output=encoded_reference, reference_image=reference, face_video=["pose_detect", 1], pose_video=pose, continue_motion_max_frames=5, video_frame_offset=0, **extra)
    latent = node("sample", "KSampler", model=model, positive=["condition", 0], negative=["condition", 1], latent_image=["condition", 2], seed=r["seed"], steps=r["steps"], cfg=r["guidance"], sampler_name="euler", scheduler="simple", denoise=1.0)
    latent = node("trim_reference", "TrimVideoLatent", samples=latent, trim_amount=["condition", 3])
    images = node("decode", "VAEDecodeTiled", samples=latent, vae=vae, tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8)
    finish = {"source": source, "mask": ["source", 2]} if replacing else {}
    node("save", "OpenFrameSaveVideo", images=images, fps=fps, frames=frames, filename_prefix=str(r.get("job_id", "OpenFrame")), preserve_outside_mask=bool(r.get("preserve_outside_mask", True)), preserve_audio=bool(r.get("preserve_audio", True)), source_filename=files["source"], trim_start=float(r.get("trim_start", 0)), export_mask=bool(r.get("export_mask", True)), match_lighting=False, **finish)
    return graph
