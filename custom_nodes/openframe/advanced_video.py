"""Small local-only media adapters for published Comfy video model nodes."""
from pathlib import Path
import json
import subprocess
import uuid

import folder_paths
import torch
import comfy.model_management
import numpy as np
import cv2
from .media import decode_frames, encode_mask_video


def _input(filename):
    path = Path(folder_paths.get_annotated_filepath(filename)).resolve()
    if not path.is_relative_to(Path(folder_paths.get_input_directory()).resolve()) or not path.is_file():
        raise ValueError("The source must be an existing file in ComfyUI/input.")
    return path


def _streams(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)], capture_output=True, timeout=30, check=True)
    return json.loads(result.stdout)["streams"]


class OpenFrameSourceAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename": ("STRING",), "frames": ("INT", {"min": 1, "max": 2401}), "fps": ("FLOAT", {"min": 1, "max": 120}), "trim_start": ("FLOAT", {"default": 0, "min": 0}), "enabled": ("BOOLEAN", {"default": True})}}

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Video"

    def load(self, filename, frames, fps, trim_start, enabled):
        rate, count = 48000, round(frames / fps * 48000)
        samples = np.zeros((count, 2), np.float32)
        path = _input(filename)
        if enabled and any(s.get("codec_type") == "audio" for s in _streams(path)):
            result = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(trim_start), "-i", str(path), "-t", str(frames / fps), "-map", "0:a:0", "-ac", "2", "-ar", str(rate), "-f", "f32le", "pipe:1"], capture_output=True, timeout=180, check=True)
            decoded = np.frombuffer(result.stdout, np.float32).reshape(-1, 2)
            samples[:min(count, len(decoded))] = decoded[:count]
        return ({"waveform": torch.from_numpy(samples.T.copy()).unsqueeze(0), "sample_rate": rate},)


class OpenFrameCanvasVideo:
    """Retain original framing for native-resolution matting and spatial outpaint."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename": ("STRING",), "width": ("INT", {"min": 32, "max": 4096}), "height": ("INT", {"min": 32, "max": 4096}), "frames": ("INT", {"min": 1, "max": 241}), "fps": ("FLOAT", {"min": 1, "max": 120}), "trim_start": ("FLOAT", {"min": 0}), "mode": (["pad-original", "upscale-2x", "outpaint"],), "source_scale": ("FLOAT", {"default": 1, "min": .1, "max": 1}), "anchor_x": ("FLOAT", {"default": .5, "min": 0, "max": 1}), "anchor_y": ("FLOAT", {"default": .5, "min": 0, "max": 1})}}

    RETURN_TYPES = ("IMAGE", "MASK", "IMAGE")
    RETURN_NAMES = ("canvas", "new_canvas_mask", "original_rgb")
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Video"

    def load(self, filename, width, height, frames, fps, trim_start, mode, source_scale, anchor_x, anchor_y):
        path = _input(filename)
        info = next(s for s in _streams(path) if s.get("codec_type") == "video")
        sw, sh = int(info["width"]), int(info["height"])
        rotation = next((item.get("rotation", 0) for item in info.get("side_data_list", []) if "rotation" in item), 0)
        if abs(int(rotation)) % 180 == 90:
            sw, sh = sh, sw
        original = decode_frames(path, sw, sh, fps, frames, trim_start)
        if mode in {"pad-original", "upscale-2x"}:
            multiple = 16 if mode == "upscale-2x" else 32
            if mode == "upscale-2x":
                width, height = width // 2, height // 2
            if (width, height) != (((sw + multiple - 1) // multiple) * multiple, ((sh + multiple - 1) // multiple) * multiple):
                raise ValueError("Inference dimensions must pad the original video without resizing; check source dimensions and the selected operation.")
            canvas = np.pad(original, ((0, 0), (0, height - sh), (0, width - sw), (0, 0)), mode="edge")
            mask = np.zeros((frames, height, width), np.float32)
        else:
            scale = min(1.0, width / sw, height / sh) * source_scale
            iw, ih = max(1, round(sw * scale)), max(1, round(sh * scale))
            if iw == width and ih == height:
                raise ValueError("Outpaint requires additional canvas. Increase the output dimensions or reduce source scale.")
            x, y = round((width - iw) * anchor_x), round((height - ih) * anchor_y)
            canvas = np.zeros((frames, height, width, 3), np.uint8)
            mask = np.ones((frames, height, width), np.float32)
            for i, frame in enumerate(original):
                canvas[i, y:y + ih, x:x + iw] = cv2.resize(frame, (iw, ih), interpolation=cv2.INTER_LANCZOS4)
            mask[:, y:y + ih, x:x + iw] = 0
        return torch.from_numpy(canvas).float() / 255, torch.from_numpy(mask), torch.from_numpy(original).float() / 255


class OpenFrameRestoreContext:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "context": ("IMAGE",)}, "optional": {"last_image": ("IMAGE",), "placement": (["start", "end"], {"default": "start"})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "restore"
    CATEGORY = "OpenFrame/Video"

    def restore(self, images, context, last_image=None, placement="start"):
        if context.shape[0] >= images.shape[0] or context.shape[1:] != images.shape[1:]:
            raise ValueError("The source context must match output dimensions and leave at least one new frame.")
        result = images.clone()
        if placement == "end":
            result[-len(context):] = context.to(result)
        elif placement == "start":
            result[:len(context)] = context.to(result)
        else:
            raise ValueError("Unknown context placement")
        if last_image is not None:
            if last_image.shape[1:] != images.shape[1:]:
                raise ValueError("The final image must match output dimensions.")
            result[-1:] = last_image[-1:].to(result)
        return (result,)


class OpenFrameExtendAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"context_audio": ("AUDIO",), "frames": ("INT", {"min": 1, "max": 241}), "fps": ("FLOAT", {"min": 1, "max": 120}), "generate_audio": ("BOOLEAN", {"default": True})}, "optional": {"generated_audio": ("AUDIO",), "placement": (["start", "end"], {"default": "start"})}}

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "combine"
    CATEGORY = "OpenFrame/Video"

    def combine(self, context_audio, frames, fps, generate_audio, generated_audio=None, placement="start"):
        import torchaudio.functional
        rate = context_audio["sample_rate"]
        original = context_audio["waveform"].cpu()
        waveform = torch.zeros((1, original.shape[1], round(frames / fps * rate)), dtype=original.dtype)
        if generate_audio and generated_audio is not None:
            generated = torchaudio.functional.resample(generated_audio["waveform"].cpu(), generated_audio["sample_rate"], rate)
            if generated.shape[1] == 1 and waveform.shape[1] == 2:
                generated = generated.repeat(1, 2, 1)
            waveform[..., :min(waveform.shape[-1], generated.shape[-1])] = generated[..., :waveform.shape[-1]]
        if original.shape[-1] >= waveform.shape[-1]:
            raise ValueError("The selected audio context must leave room for newly generated footage")
        if placement == "end":
            waveform[..., -original.shape[-1]:] = original
        elif placement == "start":
            waveform[..., :original.shape[-1]] = original
        else:
            raise ValueError("Unknown context placement")
        return ({"waveform": waveform, "sample_rate": rate},)


class OpenFrameSaveAlphaVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"original": ("IMAGE",), "matte": ("IMAGE",), "fps": ("FLOAT", {"min": 1, "max": 120}), "filename_prefix": ("STRING", {"default": "OpenFrame_alpha"})}, "optional": {"source_filename": ("STRING", {"default": ""}), "trim_start": ("FLOAT", {"default": 0, "min": 0}), "preserve_audio": ("BOOLEAN", {"default": True})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Video"

    def save(self, original, matte, fps, filename_prefix, source_filename="", trim_start=0, preserve_audio=True):
        count, height, width = original.shape[:3]
        if matte.shape[0] < count or matte.shape[1] < height or matte.shape[2] < width:
            raise ValueError("The generated matte does not cover the original video.")
        folder = Path(folder_paths.get_output_directory()) / "openframe"
        folder.mkdir(exist_ok=True)
        stem = "".join(c for c in Path(filename_prefix).name if c.isalnum() or c in "-_")[:100] or "OpenFrame"
        stem += "_" + uuid.uuid4().hex[:10]
        output, mask_path = folder / (stem + "_alpha.webm"), folder / (stem + "_matte.mp4")
        # Streaming avoids a second full-size RGBA clip in host memory.
        command = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
        source = _input(source_filename) if preserve_audio and source_filename else None
        if source and any(s.get("codec_type") == "audio" for s in _streams(source)):
            command += ["-ss", str(trim_start), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "libopus", "-b:a", "192k", "-t", str(count / fps)]
        else:
            command += ["-an"]
        command += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-lossless", "1", "-row-mt", "1", "-cpu-used", "4", "-metadata:s:v:0", "alpha_mode=1", str(output)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        alpha = matte[:count, :height, :width, :3].float().mean(dim=-1).clamp(0, 1).cpu().numpy()
        try:
            for i in range(count):
                comfy.model_management.throw_exception_if_processing_interrupted()
                rgb = (original[i, :, :, :3].float().clamp(0, 1).cpu().numpy() * 255).round().astype(np.uint8)
                frame = np.concatenate((rgb, (alpha[i] * 255).round().astype(np.uint8)[..., None]), axis=-1)
                process.stdin.write(frame.tobytes())
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180):
                raise ValueError("Could not encode transparent video: " + error.decode(errors="replace")[-1000:])
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.stderr:
                process.stderr.close()
        encode_mask_video(mask_path, alpha, width, height, fps)
        return {"ui": {"videos": [{"filename": output.name, "subfolder": "openframe", "type": "output", "role": "result", "alpha": True}, {"filename": mask_path.name, "subfolder": "openframe", "type": "output", "role": "mask"}]}, "result": (str(output),)}


class OpenFrameWhisperLoader:
    @classmethod
    def INPUT_TYPES(cls):
        path = Path(folder_paths.models_dir) / "audio_encoders/longcat-whisper-large-v3"
        ready = all((path / name).is_file() for name in ("model.safetensors", "config.json", "preprocessor_config.json"))
        return {"required": {"precision": (["bf16", "fp16"], {"default": "bf16", "openframe_longcat_whisper_available": ready})}}

    RETURN_TYPES = ("WHISPERMODEL",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Audio conditioning"

    def load(self, precision):
        from transformers import WhisperModel, WhisperFeatureExtractor
        path = Path(folder_paths.models_dir) / "audio_encoders/longcat-whisper-large-v3"
        if not all((path / name).is_file() for name in ("model.safetensors", "config.json", "preprocessor_config.json")):
            raise ValueError("LongCat Whisper files are missing. Provision the longcat-avatar-1.5 model profile first.")
        comfy.model_management.unload_all_models()
        dtype = torch.bfloat16 if precision == "bf16" else torch.float16
        model = WhisperModel.from_pretrained(str(path), dtype=dtype, local_files_only=True).eval()
        extractor = WhisperFeatureExtractor.from_pretrained(str(path), local_files_only=True)
        return ({"model": model, "feature_extractor": extractor, "dtype": dtype},)


class OpenFrameLongCat15Scheduler:
    """Avatar 1.5's released DMD schedule, not the wrapper's older 1.0 grid."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("WANVIDEOSCHEDULER",)
    FUNCTION = "build"
    CATEGORY = "OpenFrame/Audio conditioning"

    def build(self):
        from diffusers import FlowMatchEulerDiscreteScheduler
        # Official pipeline_longcat_video_avatar.py at 6b3f4b8582a8bc3f20f795735f5383716c4ba794,
        # and the published Avatar-1.5 scheduler_config.json (shift 7).
        indices = 1000 - (torch.arange(1, 9, dtype=torch.float32) * 125).round().long()
        sigmas = torch.flip(torch.flip(torch.linspace(0, 1, 1000), [0])[indices], [0]).float()
        scheduler = FlowMatchEulerDiscreteScheduler(shift=7.0, time_shift_type="linear", use_dynamic_shifting=False)
        scheduler.set_timesteps(8, sigmas=sigmas, device=comfy.model_management.get_torch_device())
        scheduler.full_sigmas = scheduler.sigmas.clone()
        scheduler.all_timesteps = scheduler.timesteps.clone()
        return ({"sample_scheduler": scheduler, "timesteps": scheduler.timesteps, "start_step": 0},)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (OpenFrameWhisperLoader, OpenFrameLongCat15Scheduler, OpenFrameSourceAudio, OpenFrameCanvasVideo, OpenFrameRestoreContext, OpenFrameExtendAudio, OpenFrameSaveAlphaVideo)}
NODE_DISPLAY_NAME_MAPPINGS = {name: "OpenFrame · " + name.removeprefix("OpenFrame") for name in NODE_CLASS_MAPPINGS}
