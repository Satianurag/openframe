"""Released temporal depth profiles, with code and weight licenses kept separate."""
VDA_COMMIT = "4f5ae23172ba60fd7bc11ef671cca678842c7072"
VIGEO_COMMIT = "1b2a48324759f34c323358084f7d60a9c5fbf2a7"
DEPTH_PACKAGES = {
    "video-depth-small": {"repository": "https://github.com/DepthAnything/Video-Depth-Anything.git", "revision": VDA_COMMIT, "directory": "openframe_depth/vda-source", "patch": "setup_depth_source.py", "license": "Apache-2.0"},
    "vigeo-1.1": {"repository": "https://github.com/aigc3d/ViGeo.git", "revision": VIGEO_COMMIT, "directory": "openframe_depth/vigeo-source", "license": "Apache-2.0 code; CC-BY-NC-4.0 weights"},
}
DEPTH_MODEL_FILES = {
    "video-depth-small": [{"repo": "depth-anything/Video-Depth-Anything-Small", "revision": "256875362cff76724b920335dfb4b29dd611f66e",
        "file": "video_depth_anything_vits.pth", "category": "depth/vda-small", "size_bytes": 116440756,
        "expected_sha256": "13379300b739e659f076a59d52e9801bd8d38c541a7e71f73bbca4dcfb013609", "license": "Apache-2.0"}],
    "vigeo-1.1": [{"repo": "pkqbajng/ViGeo1.1", "revision": "49103e6eeab888bae974251d3578b496bec711d7",
        "file": "vigeo.pt", "category": "depth/vigeo-1.1", "size_bytes": 5054751381,
        "expected_sha256": "39400cd96ff76c33b286e25c305779f839406512c875ba461d0203c4b8cf7e98", "license": "CC-BY-NC-4.0",
        "source_note": "Official weight card is noncommercial despite the separate Apache source-code license."}],
}
_COMMON = {"family": "Depth", "tasks": ["video-depth"], "output_kind": "video", "aspect_ratios": [],
    "default_width": 768, "default_height": 512, "default_frames": 97, "default_fps": 24,
    "default_steps": 1, "fixed_steps": 1, "default_guidance": 1, "fixed_guidance": 1,
    "min_frames": 2, "max_frames": 300, "frame_multiple": 1, "dimension_multiple": 2,
    "min_width": 64, "min_height": 64, "max_width": 1280, "max_height": 1280,
    "default_task_limits": {"max_long_side": 1280, "max_pixels": 921600},
    "supports_audio": False, "supports_mask": False, "supports_reference": False, "reference_tasks": [],
    "requires_prompt": False, "preserve_source_fps": True, "preserve_source_aspect": True,
    "supported_providers": ["local"], "recommended_provider": "local", "requires_cuda": True,
    "depth_outputs": ["near-white grayscale preview", "lossless 16-bit relative map with scale metadata"],
    "validation_status": "awaiting-validation"}
DEPTH_MODELS = [
    {**_COMMON, "id": "video-depth-small", "name": "Video Depth Anything Small", "badge": "Apache temporal baseline",
     "description": "Permissive temporal video depth using the official overlapping-window inference. Relative inverse depth, not metres. Default depth profile.",
     "license": "Apache-2.0", "license_url": "https://huggingface.co/depth-anything/Video-Depth-Anything-Small", "research_only": False},
    {**_COMMON, "id": "vigeo-1.1", "name": "ViGeo 1.1 · Research", "badge": "Noncommercial weights",
     "depth_inference_modes": ["chunk", "offline"], "depth_offline_max_frames": 64,
     "description": "Released temporal geometry model with chunk16 cached inference and a valid-region head. Strong published long-video results; weights restrict use to noncommercial purposes.",
     "license": "CC-BY-NC-4.0", "license_url": "https://huggingface.co/pkqbajng/ViGeo1.1", "research_only": True},
]


def depth_effect(effect):
    result = effect("video-depth", "Video depth", "Estimate temporally conditioned relative depth for compositing; no metric-distance claim.",
                    "VFX", "video-depth", "", [model["id"] for model in DEPTH_MODELS], video=True)
    result["prompt_policy"] = "empty"
    result["default_model_id"] = "video-depth-small"
    return result
