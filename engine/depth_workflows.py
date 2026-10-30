"""One ComfyUI node wraps the selected official temporal depth implementation."""


def normalize_depth_request(request):
    mode = request.get("depth_inference_mode", "chunk")
    if mode not in {"chunk", "offline"}:
        raise ValueError("Choose chunk or offline depth inference.")
    if mode == "offline" and request["model_id"] != "vigeo-1.1":
        raise ValueError("Offline inference is available only for ViGeo; Video Depth Anything uses its native overlapping windows.")
    if mode == "offline" and request["frames"] > 64:
        raise ValueError("Offline ViGeo is bounded to 64 frames; select a shorter interval or chunk mode.")
    request["depth_inference_mode"] = mode


def build_depth_workflow(request, assets=None):
    normalize_depth_request(request)
    files = assets or {}
    return {"save": {"class_type": "OpenFrameVideoDepth", "inputs": {
        "filename": files.get("source", "source.mp4"), "profile": request["model_id"],
        "width": request["width"], "height": request["height"], "frames": request["frames"], "fps": request["fps"],
        "trim_start": request.get("trim_start", 0), "preserve_audio": request.get("preserve_audio", True),
        "encoding_quality": request.get("encoding_quality", "legacy"), "filename_prefix": str(request.get("job_id", "OpenFrame")),
        "colormap": request.get("depth_colormap", "grayscale"), "side_by_side": request.get("depth_side_by_side", False),
        "inference_mode": request["depth_inference_mode"]},
        "_meta": {"title": "Temporal depth · preview + lossless data"}}}
