"""Frame-accurate media, optical-flow mask propagation and plate preservation."""
from pathlib import Path
import uuid
import tempfile
import gc
import importlib.util
from contextlib import nullcontext

import numpy as np
from PIL import Image
import torch
import folder_paths
import comfy.model_management
import comfy.utils
from .media import (decode_frames as _frames, fit_mask as _fit_mask,
                    feather_mask as _feather_mask, match_plate_lighting as _match_plate_lighting,
                    propagate_mask, prepare_masks, composite_frame, encode_video, encode_mask_video)


def _input_path(filename):
    base = Path(folder_paths.get_input_directory()).resolve()
    path = Path(folder_paths.get_annotated_filepath(filename)).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("The source must be an existing file in ComfyUI/input.")
    return path


def _sam2_masks(images, first):
    from sam2.build_sam import build_sam2_video_predictor
    checkpoint = Path(folder_paths.models_dir) / "sam2/sam2.1_hiera_small.pt"
    if not checkpoint.is_file():
        raise ValueError("SAM2 weights are missing. Provision the sam2 profile or select optical flow/static tracking.")
    comfy.model_management.unload_all_models()
    device = comfy.model_management.get_torch_device()
    predictor = state = None
    masks = np.zeros(images.shape[:3], dtype=np.float32)
    bar = comfy.utils.ProgressBar(len(images))
    try:
        with tempfile.TemporaryDirectory(prefix="openframe-sam2-", dir=folder_paths.get_temp_directory()) as folder:
            for index, frame in enumerate(images):
                Image.fromarray(frame).save(Path(folder) / f"{index:06d}.jpg", quality=95)
            predictor = build_sam2_video_predictor("configs/sam2.1/sam2.1_hiera_s.yaml", str(checkpoint), device=str(device), apply_postprocessing=False)
            precision = torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext()
            with torch.inference_mode(), precision:
                state = predictor.init_state(video_path=folder, offload_video_to_cpu=True, offload_state_to_cpu=True)
                predictor.add_new_mask(state, frame_idx=0, obj_id=1, mask=first >= .5)
                for frame_index, object_ids, logits in predictor.propagate_in_video(state, start_frame_idx=0, max_frame_num_to_track=len(images)):
                    comfy.model_management.throw_exception_if_processing_interrupted()
                    if frame_index < len(images):
                        masks[frame_index] = (logits[0, 0] > 0).float().cpu().numpy()
                        bar.update_absolute(frame_index + 1, len(images))
            masks[0] = (first >= .5).astype(np.float32)
    finally:
        del state, predictor
        gc.collect()
        comfy.model_management.soft_empty_cache()
    return masks


class OpenFrameRecordVideoPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"original": ("STRING", {"multiline": True}),
                             "model_prompt": ("STRING", {"multiline": True}),
                             "enhanced": ("BOOLEAN", {"default": False})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "record"
    CATEGORY = "OpenFrame/Video"
    OUTPUT_NODE = True

    def record(self, original, model_prompt, enhanced):
        record = {"original": original, "model_prompt": model_prompt,
                  "expanded": model_prompt if enhanced else "",
                  "mode": "expand" if enhanced else "caption",
                  "expander": "TextGenerateLTX2Prompt" if enhanced else None}
        return {"ui": {"text": [model_prompt], "openframe_prompt": [record]}, "result": (model_prompt,)}


class OpenFrameVideoInput:
    @classmethod
    def INPUT_TYPES(cls):
        sam2_ready = importlib.util.find_spec("sam2") is not None and (Path(folder_paths.models_dir) / "sam2/sam2.1_hiera_small.pt").is_file()
        return {"required": {"filename": ("STRING", {"default": "source.mp4"}), "width": ("INT", {"default": 512, "min": 64, "max": 2048}), "height": ("INT", {"default": 288, "min": 64, "max": 2048}), "frames": ("INT", {"default": 49, "min": 1, "max": 241}), "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120}), "mask_filename": ("STRING", {"default": ""}), "track_mask": ("BOOLEAN", {"default": True}), "mask_dilation": ("INT", {"default": 8, "min": 0, "max": 64}), "mask_feather": ("INT", {"default": 3, "min": 0, "max": 32}), "trim_start": ("FLOAT", {"default": 0, "min": 0, "max": 36000}), "tracking_method": (["sam2", "flow", "static"], {"default": "sam2", "openframe_sam2_available": sam2_ready, "openframe_sam2_checkpoint": "sam2.1_hiera_small.pt"})}, "optional": {"feather_method": (["gaussian", "inward", "smooth-inward"], {"default": "gaussian"}), "edit_margin": ("INT", {"default": 0, "min": 0, "max": 64})}}
    RETURN_TYPES = ("IMAGE", "MASK", "MASK")
    RETURN_NAMES = ("source_frames", "generation_mask", "blend_mask")
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Video"

    def load(self, filename, width, height, frames, fps, mask_filename="", track_mask=True, mask_dilation=8, mask_feather=3, trim_start=0, tracking_method="sam2", feather_method="gaussian", edit_margin=0):
        images = _frames(_input_path(filename), width, height, fps, frames, trim_start)
        if mask_filename:
            mask_path = _input_path(mask_filename)
            if mask_path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
                masks = _frames(mask_path, width, height, fps, frames, trim_start).mean(axis=-1) / 255.0
            else:
                with Image.open(mask_path) as image:
                    first = _fit_mask(image, width, height)
                if not np.any(first > .5):
                    raise ValueError("The supplied mask is empty. Paint white over the area to change.")
                if track_mask and tracking_method == "sam2" and frames > 1:
                    masks = _sam2_masks(images, first)
                else:
                    masks = propagate_mask(images, first, tracking_method if track_mask and frames > 1 else "static", comfy.model_management.throw_exception_if_processing_interrupted)
        else:
            masks = np.ones((frames, height, width), dtype=np.float32)
        generation, blend = prepare_masks(masks, mask_dilation, mask_feather, feather_method, edit_margin=edit_margin)
        return torch.from_numpy(images).float() / 255, torch.from_numpy(generation).float(), torch.from_numpy(blend).float()


class OpenFrameGreenFill:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "mask": ("MASK",)}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "fill"
    CATEGORY = "OpenFrame/VFX"

    def fill(self, images, mask):
        alpha = mask.to(images.device).unsqueeze(-1)
        colour = torch.tensor([102 / 255, 1.0, 0.0], device=images.device, dtype=images.dtype)
        return (images[..., :3] * (1 - alpha) + colour * alpha,)


class OpenFramePadForRefinement:
    """Preserve aspect and pixels while making half-size latent dimensions valid."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "mask": ("MASK",)}, "optional": {"multiple": ("INT", {"default": 64, "min": 64, "max": 128, "step": 64})}}
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "pad"
    CATEGORY = "OpenFrame/VFX"

    def pad(self, images, mask, multiple=64):
        import torch.nn.functional as F
        if multiple not in {64, 128}:
            raise ValueError("Refinement padding must use a 64 or 128 pixel multiple.")
        height, width = images.shape[1:3]
        right, bottom = (-width) % multiple, (-height) % multiple
        if not right and not bottom:
            return images, mask
        padded = F.pad(images.movedim(-1, 1), (0, right, 0, bottom), mode="replicate").movedim(1, -1)
        return padded, F.pad(mask, (0, right, 0, bottom), value=0)


class OpenFrameSaveVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120}), "frames": ("INT", {"default": 49, "min": 1, "max": 2401}), "filename_prefix": ("STRING", {"default": "OpenFrame"}), "preserve_outside_mask": ("BOOLEAN", {"default": True}), "preserve_audio": ("BOOLEAN", {"default": True}), "source_filename": ("STRING", {"default": ""}), "trim_start": ("FLOAT", {"default": 0, "min": 0, "max": 36000}), "export_mask": ("BOOLEAN", {"default": True})}, "optional": {"source": ("IMAGE",), "mask": ("MASK",), "audio": ("AUDIO",), "match_lighting": ("BOOLEAN", {"default": False}), "encoding_quality": (["legacy", "standard", "high"], {"default": "legacy"})}}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_NODE = True
    FUNCTION = "save"
    CATEGORY = "OpenFrame/Video"

    def save(self, images, fps, frames, filename_prefix, preserve_outside_mask, preserve_audio, source_filename="", trim_start=0, source=None, mask=None, audio=None, export_mask=True, match_lighting=False, encoding_quality="legacy"):
        if len(images) < frames:
            raise ValueError(f"Model returned {len(images)} frames, fewer than the requested {frames}.")
        images = images[:frames, ..., :3].detach().cpu()
        original = alpha = None
        if source is not None and mask is not None and preserve_outside_mask:
            original = source[:frames, ..., :3].detach().cpu()
            alpha = mask[:frames].detach().cpu()
            if original.shape != images.shape or alpha.shape != images.shape[:3]:
                raise ValueError("Generated footage, source and mask must have exactly matching dimensions and frame counts.")
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        name = f"{stem}_{uuid.uuid4().hex[:10]}.mp4"
        target = output / name
        height, width = images.shape[1:3]
        def pixels():
            for index, frame in enumerate(images):
                yield composite_frame(frame.numpy(), original[index].numpy() if original is not None else None,
                                      alpha[index].numpy() if alpha is not None else None, match_lighting)
        audio_data = None
        if audio is not None:
            audio_data = {"waveform": audio["waveform"].detach().cpu().float()[0].numpy(), "sample_rate": audio["sample_rate"]}
        encode_video(target, pixels(), width, height, fps, frames,
                     source_audio=_input_path(source_filename) if preserve_audio and source_filename else None,
                     trim_start=trim_start, audio=audio_data,
                     check_cancelled=comfy.model_management.throw_exception_if_processing_interrupted, encoding_quality=encoding_quality)
        outputs = [{"filename": name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "fps": fps, "role": "result"}]
        if export_mask and mask is not None:
            mask_name = "mask_" + name
            encode_mask_video(output / mask_name, mask[:frames].detach().cpu().numpy(), width, height, fps)
            outputs.append({"filename": mask_name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "fps": fps, "role": "mask"})
        return {"ui": {"videos": outputs}, "result": (str(target),)}


NODE_CLASS_MAPPINGS = {"OpenFrameVideoInput": OpenFrameVideoInput, "OpenFrameGreenFill": OpenFrameGreenFill, "OpenFramePadForRefinement": OpenFramePadForRefinement, "OpenFrameSaveVideo": OpenFrameSaveVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"OpenFrameVideoInput": "OpenFrame · Video + Tracked Mask", "OpenFrameGreenFill": "OpenFrame · LTX Inpaint Guide", "OpenFramePadForRefinement": "OpenFrame · Pad for Two-Stage Refinement", "OpenFrameSaveVideo": "OpenFrame · Preserve Plate + Save Video"}
NODE_CLASS_MAPPINGS["OpenFrameRecordVideoPrompt"] = OpenFrameRecordVideoPrompt
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameRecordVideoPrompt"] = "OpenFrame · Record Model Prompt"
from .speech import OpenFrameKokoroSpeech, OpenFrameSaveAudio
NODE_CLASS_MAPPINGS.update(OpenFrameKokoroSpeech=OpenFrameKokoroSpeech, OpenFrameSaveAudio=OpenFrameSaveAudio)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameKokoroSpeech="OpenFrame · Kokoro CPU Speech", OpenFrameSaveAudio="OpenFrame · Save WAV")

from .image import OpenFrameFlux3Prompt, OpenFrameSaveImage
from .video_tools import OpenFrameVideoEdit
NODE_CLASS_MAPPINGS.update(OpenFrameFlux3Prompt=OpenFrameFlux3Prompt, OpenFrameSaveImage=OpenFrameSaveImage, OpenFrameVideoEdit=OpenFrameVideoEdit)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameFlux3Prompt="OpenFrame · FLUX3 Caption + Layout", OpenFrameSaveImage="OpenFrame · Preserve Pixels + Save PNG", OpenFrameVideoEdit="OpenFrame · Trim + Reframe")

from .advanced_video import NODE_CLASS_MAPPINGS as ADVANCED_VIDEO_NODES, NODE_DISPLAY_NAME_MAPPINGS as ADVANCED_VIDEO_NAMES
NODE_CLASS_MAPPINGS.update(ADVANCED_VIDEO_NODES)
NODE_DISPLAY_NAME_MAPPINGS.update(ADVANCED_VIDEO_NAMES)

from .image_canvas import OpenFrameExpandImageCanvas, OpenFrameImageEditCanvas, OpenFrameLoadImageMask, OpenFrameImageRegionInfo
NODE_CLASS_MAPPINGS["OpenFrameImageRegionInfo"] = OpenFrameImageRegionInfo
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameImageRegionInfo"] = "OpenFrame · Image Region Provenance"
NODE_CLASS_MAPPINGS["OpenFrameExpandImageCanvas"] = OpenFrameExpandImageCanvas
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameExpandImageCanvas"] = "OpenFrame · Expand Image Canvas"
NODE_CLASS_MAPPINGS["OpenFrameImageEditCanvas"] = OpenFrameImageEditCanvas
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameImageEditCanvas"] = "OpenFrame · Image Preservation Canvas"
NODE_CLASS_MAPPINGS["OpenFrameLoadImageMask"] = OpenFrameLoadImageMask
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameLoadImageMask"] = "OpenFrame · Exact Image Mask"

from .training import NODE_CLASS_MAPPINGS as TRAINING_NODES, NODE_DISPLAY_NAME_MAPPINGS as TRAINING_NAMES
NODE_CLASS_MAPPINGS.update(TRAINING_NODES)
NODE_DISPLAY_NAME_MAPPINGS.update(TRAINING_NAMES)

from .hdr_output import OpenFrameSaveHDRVideo
NODE_CLASS_MAPPINGS["OpenFrameSaveHDRVideo"] = OpenFrameSaveHDRVideo
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameSaveHDRVideo"] = "OpenFrame · HDR export"

from .interpolation import OpenFrameLoadLDF
NODE_CLASS_MAPPINGS.update(OpenFrameLoadLDF=OpenFrameLoadLDF)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameLoadLDF="OpenFrame · Load LDF-VFI")

from .transitions import OpenFrameTransitionInputs, OpenFrameTransitionGuide, OpenFrameSaveTransition
NODE_CLASS_MAPPINGS.update(OpenFrameTransitionInputs=OpenFrameTransitionInputs, OpenFrameTransitionGuide=OpenFrameTransitionGuide, OpenFrameSaveTransition=OpenFrameSaveTransition)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameTransitionInputs="OpenFrame · Transition Endpoints", OpenFrameTransitionGuide="OpenFrame · Transition Midpoint Guide", OpenFrameSaveTransition="OpenFrame · Save Transition")

from .depth import OpenFrameVideoDepth
NODE_CLASS_MAPPINGS.update(OpenFrameVideoDepth=OpenFrameVideoDepth)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameVideoDepth="OpenFrame · Temporal Video Depth")

from .layers import OpenFrameSaveLayers
NODE_CLASS_MAPPINGS.update(OpenFrameSaveLayers=OpenFrameSaveLayers)
NODE_DISPLAY_NAME_MAPPINGS.update(OpenFrameSaveLayers="OpenFrame · Save RGBA Layers")

from .narration import NODE_CLASS_MAPPINGS as NARRATION_CLASSES, NODE_DISPLAY_NAME_MAPPINGS as NARRATION_NAMES
NODE_CLASS_MAPPINGS.update(NARRATION_CLASSES)
NODE_DISPLAY_NAME_MAPPINGS.update(NARRATION_NAMES)

from .semantic_matte import OpenFrameSemanticMatte
NODE_CLASS_MAPPINGS["OpenFrameSemanticMatte"] = OpenFrameSemanticMatte
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameSemanticMatte"] = "OpenFrame · Prompted soft video matte"

from .restyle import OpenFrameCannyGuide, OpenFrameRestyleFirstFrame
NODE_CLASS_MAPPINGS["OpenFrameCannyGuide"] = OpenFrameCannyGuide
NODE_CLASS_MAPPINGS["OpenFrameRestyleFirstFrame"] = OpenFrameRestyleFirstFrame
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameRestyleFirstFrame"] = "OpenFrame · Weather First Frame"
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameCannyGuide"] = "OpenFrame · Canny Video Guide"

from .inpaint_reference import OpenFrameInpaintFirstFrame
NODE_CLASS_MAPPINGS["OpenFrameInpaintFirstFrame"] = OpenFrameInpaintFirstFrame
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameInpaintFirstFrame"] = "OpenFrame · Edited Inpaint Starting Frame"

from .reference_sheet import OpenFrameReferenceSheet
NODE_CLASS_MAPPINGS["OpenFrameReferenceSheet"] = OpenFrameReferenceSheet
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameReferenceSheet"] = "OpenFrame · Ingredients Reference Sheet"

from .recast import OpenFrameRecastMasks, OpenFrameRecastOfficialSupport
from .reference_foreground import OpenFrameReferenceForeground
NODE_CLASS_MAPPINGS["OpenFrameReferenceForeground"] = OpenFrameReferenceForeground
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameReferenceForeground"] = "OpenFrame · Clean Reference Edges"
NODE_CLASS_MAPPINGS["OpenFrameRecastMasks"] = OpenFrameRecastMasks
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameRecastMasks"] = "OpenFrame · Recast Mask Guard and Plate Support"

NODE_CLASS_MAPPINGS["OpenFrameRecastOfficialSupport"] = OpenFrameRecastOfficialSupport
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameRecastOfficialSupport"] = "OpenFrame · Official SAM3.1 Composite Support"

from .relight_sphere import OpenFrameRelightSphere
NODE_CLASS_MAPPINGS["OpenFrameRelightSphere"] = OpenFrameRelightSphere
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameRelightSphere"] = "OpenFrame · Prepared Lighting Sphere"

from .plate_fit import OpenFrameFitPlate
NODE_CLASS_MAPPINGS["OpenFrameFitPlate"] = OpenFrameFitPlate
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameFitPlate"] = "OpenFrame · Fit Generated Lighting to Plate"

from .planner import OpenFrameVisualPlanner
NODE_CLASS_MAPPINGS["OpenFrameVisualPlanner"] = OpenFrameVisualPlanner
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameVisualPlanner"] = "OpenFrame · Visual Shot Planner"

from .image_brightness import OpenFrameImageBrightness
NODE_CLASS_MAPPINGS["OpenFrameImageBrightness"] = OpenFrameImageBrightness
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameImageBrightness"] = "OpenFrame · Post-render Brightness"

from .editvid import OpenFrameEditVidInput
NODE_CLASS_MAPPINGS["OpenFrameEditVidInput"] = OpenFrameEditVidInput
NODE_DISPLAY_NAME_MAPPINGS["OpenFrameEditVidInput"] = "OpenFrame · Selected EditVid Interval"

from .portrait_alpha import OpenFramePortraitAlphas
NODE_CLASS_MAPPINGS['OpenFramePortraitAlphas'] = OpenFramePortraitAlphas
NODE_DISPLAY_NAME_MAPPINGS['OpenFramePortraitAlphas'] = 'Portrait alpha refinement (source + generated)'
from .portrait_alpha import OpenFrameImageAlpha
NODE_CLASS_MAPPINGS['OpenFrameImageAlpha'] = OpenFrameImageAlpha
NODE_DISPLAY_NAME_MAPPINGS['OpenFrameImageAlpha'] = 'Image alpha refinement (ViTMatte)'
