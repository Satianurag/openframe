"""Extract real media endpoints and assemble a generated transition without loops."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
import torch
import folder_paths
import comfy.model_management

from .media import encode_video, video_encoding_args


def _run(command, timeout=180):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    started = time.monotonic()
    try:
        while True:
            comfy.model_management.throw_exception_if_processing_interrupted()
            if time.monotonic() - started > timeout:
                raise ValueError("Transition media processing exceeded its bounded execution time.")
            try:
                output, error = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ValueError("Transition media processing failed: " + error.decode(errors="replace")[-1200:])
        return output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()


def _info(path):
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            return {"kind": "image", "width": image.width, "height": image.height, "duration": 0, "has_audio": False}
    except UnidentifiedImageError:
        pass
    data = json.loads(_run(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,width,height,avg_frame_rate,duration,nb_frames:stream_side_data=rotation:format=duration", "-of", "json", str(path)], 30))
    video = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("Transition inputs must be images or videos.")
    numerator, denominator = video.get("avg_frame_rate", "0/1").split("/")
    fps = float(numerator) / float(denominator) if float(denominator) else 0
    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
    width, height = video["width"], video["height"]
    rotation = next((item.get("rotation", 0) for item in video.get("side_data_list", []) if "rotation" in item), 0)
    if abs(int(rotation)) % 180 == 90:
        width, height = height, width
    return {"kind": "video", "width": width, "height": height, "duration": duration, "fps": fps,
            "frames": int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None,
            "has_audio": any(stream.get("codec_type") == "audio" for stream in data["streams"])}


def _valid_input(info):
    if info["kind"] == "video" and (not 0 < info["duration"] <= 5.001 or not 0 < info["fps"] <= 120):
        raise ValueError("Each transition video must be no longer than five seconds and no faster than 120 fps. Trim it explicitly first.")


def _geometry(width, height, fit, anchor_x, anchor_y):
    if fit == "crop":
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-ow)*{anchor_x}:(ih-oh)*{anchor_y}"
    if fit == "pad":
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)*{anchor_x}:(oh-ih)*{anchor_y}:color=black"
    raise ValueError("Choose crop or pad for transition framing.")


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            comfy.model_management.throw_exception_if_processing_interrupted()
            digest.update(chunk)
    return digest.hexdigest()


def _endpoint(path, last, width, height, fit, anchor_x, anchor_y):
    info = _info(path)
    _valid_input(info)
    index, timestamp = 0, None
    if info["kind"] == "video":
        timestamps = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)], 30)).get("frames", [])
        if not timestamps or len(timestamps) > 601:
            raise ValueError("The transition clip has no readable bounded frame sequence.")
        index = len(timestamps) - 1 if last else 0
        stamp = timestamps[index].get("best_effort_timestamp_time")
        timestamp = float(stamp) if stamp is not None else None
        info["decoded_frames"] = len(timestamps)
    # Selecting by decoded index handles variable-rate clips; it never estimates
    # the last frame by seeking an arbitrary fraction before container duration.
    selected = f"select=eq(n\\,{index})," if info["kind"] == "video" else ""
    pixels = _run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-an", "-vf",
        selected + _geometry(width, height, fit, anchor_x, anchor_y), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    if len(pixels) != width * height * 3:
        raise ValueError("Could not extract the exact transition endpoint frame.")
    image = np.frombuffer(pixels, np.uint8).reshape(height, width, 3).copy()
    record = {**info, "filename": path.name, "input_sha256": _hash(path), "selected_frame_index": index,
              "selected_timestamp": timestamp, "endpoint": "last" if last else "first", "fit": fit,
              "anchor": [anchor_x, anchor_y], "canvas": [width, height], "fitted_rgb_sha256": hashlib.sha256(pixels).hexdigest()}
    return torch.from_numpy(image.astype(np.float32) / 255).unsqueeze(0), record


class OpenFrameTransitionInputs:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"source_filename": ("STRING",), "end_filename": ("STRING",),
            "width": ("INT", {"default": 768, "min": 256, "max": 1920}),
            "height": ("INT", {"default": 512, "min": 256, "max": 1920}),
            "fit": (["crop", "pad"],), "anchor_x": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "anchor_y": ("FLOAT", {"default": .5, "min": 0, "max": 1})},
            "optional": {"fit_on_load": ("BOOLEAN", {"default": True})}}
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("start", "end")
    FUNCTION = "load"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Video"

    def load(self, source_filename, end_filename, width, height, fit, anchor_x, anchor_y, fit_on_load=True):
        from .nodes import _input_path
        source_path, end_path = _input_path(source_filename), _input_path(end_filename)
        source_size = end_size = (width, height)
        if not fit_on_load:
            source_info, end_info = _info(source_path), _info(end_path)
            source_size = (source_info["width"], source_info["height"])
            end_size = (end_info["width"], end_info["height"])
        start, first = _endpoint(source_path, True, *source_size, fit, anchor_x, anchor_y)
        end, second = _endpoint(end_path, False, *end_size, fit, anchor_x, anchor_y)
        if not fit_on_load:
            for item in (first, second):
                item.update(fit_on_load=False, framing="Native-size endpoint; downstream native ResizeImageMaskNode performs the recorded resize.")
        return {"ui": {"openframe_transition_inputs": [{"source": first, "end": second}]}, "result": (start, end)}


class OpenFrameTransitionGuide:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("STRING", {"default": "reference.png"}),
            "width": ("INT", {"default": 768, "min": 256, "max": 1920}),
            "height": ("INT", {"default": 512, "min": 256, "max": 1920}),
            "fit": (["crop", "pad"],), "anchor_x": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "anchor_y": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "frame_idx": ("INT", {"default": 60, "min": 1, "max": 240}),
            "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Video"

    def load(self, image, width, height, fit, anchor_x, anchor_y, frame_idx, fps):
        from .nodes import _input_path
        path = _input_path(image)
        if _info(path)["kind"] != "image":
            raise ValueError("The transition midpoint guide must be a still image.")
        fitted, record = _endpoint(path, False, width, height, fit, anchor_x, anchor_y)
        record.update(endpoint="midpoint", conditioning_frame=frame_idx,
                      conditioning_seconds=frame_idx / fps, strength=1.0,
                      pixel_restoration=False)
        return {"ui": {"openframe_transition_guide": [record]}, "result": (fitted,)}


class OpenFrameSaveTransition:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "fps": ("FLOAT", {"default": 24}),
            "frames": ("INT", {"default": 121, "min": 1, "max": 241}),
            "source_filename": ("STRING",), "end_filename": ("STRING",),
            "include_inputs": ("BOOLEAN", {"default": False}), "preserve_audio": ("BOOLEAN", {"default": True}),
            "fit": (["crop", "pad"],), "anchor_x": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "anchor_y": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "encoding_quality": (["legacy", "standard", "high"],), "filename_prefix": ("STRING", {"default": "OpenFrame"})},
            "optional": {"audio": ("AUDIO",)}}
    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "save"
    CATEGORY = "OpenFrame/Video"

    def save(self, images, fps, frames, source_filename, end_filename, include_inputs, preserve_audio,
             fit, anchor_x, anchor_y, encoding_quality, filename_prefix, audio=None):
        from .nodes import _input_path
        if fps != 24 or frames not in {121, 241} or len(images) != frames:
            raise ValueError("The generated bridge must contain exactly 121 or 241 frames at 24 fps.")
        height, width = images.shape[1:3]
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        stem += "_" + uuid.uuid4().hex[:10]
        bridge = output / (stem + "_bridge.mp4")
        audio_data = None if audio is None else {"waveform": audio["waveform"].detach().cpu().float()[0].numpy(), "sample_rate": audio["sample_rate"]}
        encode_video(bridge, (np.rint(frame[..., :3].detach().cpu().numpy().clip(0, 1) * 255).astype(np.uint8) for frame in images),
            width, height, fps, frames, audio=audio_data, encoding_quality=encoding_quality,
            check_cancelled=comfy.model_management.throw_exception_if_processing_interrupted)
        segments = []
        first, last = _input_path(source_filename), _input_path(end_filename)
        first_info, last_info = _info(first), _info(last)
        _valid_input(first_info); _valid_input(last_info)
        if include_inputs and first_info["kind"] == "video":
            segments.append((first, first_info, preserve_audio, "source"))
        segments.append((bridge, {"kind": "video", "duration": frames / fps, "fps": fps, "frames": frames, "has_audio": audio is not None}, True, "generated-bridge"))
        if include_inputs and last_info["kind"] == "video":
            segments.append((last, last_info, preserve_audio, "end"))
        target = bridge
        if len(segments) > 1:
            target = output / (stem + "_assembled.mp4")
            partial = target.with_suffix(".partial.mp4")
            command = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-xerror"]
            for path, _, _, _ in segments:
                command += ["-i", str(path)]
            audio_enabled = any(info["has_audio"] and keep for _, info, keep, _ in segments)
            filters, concat = [], []
            for index, (_, info, keep, _) in enumerate(segments):
                filters.append(f"[{index}:v:0]fps={fps}," + _geometry(width, height, fit, anchor_x, anchor_y) + f",setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v{index}]")
                concat.append(f"[v{index}]")
                if audio_enabled:
                    prefix = f"[{index}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad" if info["has_audio"] and keep else "anullsrc=channel_layout=stereo:sample_rate=48000"
                    filters.append(prefix + f",atrim=duration={info['duration']}[a{index}]")
                    concat.append(f"[a{index}]")
            filters.append("".join(concat) + f"concat=n={len(segments)}:v=1:a={int(audio_enabled)}[v]" + ("[a]" if audio_enabled else ""))
            command += ["-filter_complex", ";".join(filters), "-map", "[v]"]
            command += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"] if audio_enabled else ["-an"]
            command += ["-c:v", "libx264", "-threads", "2", "-preset", "medium", *video_encoding_args(width, height, fps, encoding_quality), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial)]
            try:
                _run(command, 600)
                measured = _info(partial)
                if abs(measured["duration"] - sum(info["duration"] for _, info, _, _ in segments)) > max(.15, len(segments) / fps):
                    raise ValueError("Assembled transition duration differs from its actual input segments.")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        measured = _info(target)
        media = [{"filename": target.name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "role": "result"}]
        if target != bridge:
            media.append({"filename": bridge.name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "role": "bridge"})
        record = {"bridge_frames": frames, "bridge_fps": fps, "bridge_duration": frames / fps,
            "include_input_clips": include_inputs, "measured_output": measured,
            "segments": [{"role": role, "duration": info["duration"], "source_fps": info["fps"], "output_fps": fps,
                          "resampled": abs(info["fps"] - fps) > .000001, "audio_kept": keep and info["has_audio"]} for _, info, keep, role in segments],
            "note": "Source clips are fitted and explicitly resampled for concatenation; images are endpoint guides, not looped footage. No source is stretched or repeated to fill a requested duration."}
        return {"ui": {"videos": media, "openframe_transition": [record]}, "result": (str(target),)}
