"""Explicit Comfy graphs for deterministic video utilities."""
import math


def build_video_tool_workflow(request, assets=None):
    files = assets or {}
    return {"save": {"class_type": "OpenFrameVideoEdit", "inputs": {
        "filename": files.get("source", "source.mp4"),
        "operation": request["task"], "width": request["width"], "height": request["height"],
        "fps": request["fps"], "frames": request["frames"], "trim_start": request.get("trim_start", 0),
        "fit": request.get("reframe_fit", "crop"),
        "anchor_x": request.get("anchor_x", .5), "anchor_y": request.get("anchor_y", .5),
        "preserve_audio": request.get("preserve_audio", True),
        "encoding_quality": request.get("encoding_quality", "high"),
        "filename_prefix": str(request.get("job_id", "OpenFrame")),
    }}}


def build_interpolation_workflow(request, assets=None):
    files = assets or {}
    source = files.get("source", "source.mp4")
    source_fps = float(request["input_fps"])
    return {
        "source": {"class_type": "OpenFrameVideoInput", "inputs": {
            "filename": source, "width": request["width"], "height": request["height"],
            "frames": request["input_frames"], "fps": source_fps, "trim_start": request.get("trim_start", 0),
            "mask_filename": "", "track_mask": False, "mask_dilation": 0, "mask_feather": 0,
            "tracking_method": "static", "edit_margin": 0,
        }},
        "model": {"class_type": "OpenFrameLoadLDF", "inputs": {"tile_size": 256, "tile_overlap": 64}},
        "interpolate": {"class_type": "LDFVFIInterpolate", "inputs": {
            "images": ["source", 0], "model": ["model", 0],
            "temporal_factor": math.ceil(request["fps"] / source_fps),
            "sampling_steps": request["steps"], "t_shift": 8.0, "t_cond": .1,
            "seed": request["seed"] % (2**31), "offload_after": True,
            "source_fps": source_fps, "target_fps": request["fps"],
        }},
        "save": {"class_type": "OpenFrameSaveVideo", "inputs": {
            "images": ["interpolate", 0], "fps": request["fps"], "frames": request["frames"],
            "filename_prefix": str(request.get("job_id", "OpenFrame")), "preserve_outside_mask": False,
            "preserve_audio": request.get("preserve_audio", True), "source_filename": source,
            "trim_start": request.get("trim_start", 0), "export_mask": False,
            "encoding_quality": request.get("encoding_quality", "high"),
        }},
    }
