"""Bounded, frame-accurate media editing inside ComfyUI, without model downloads."""
import json
from pathlib import Path
import subprocess
import time
import uuid

import folder_paths
import comfy.model_management

from .media import video_encoding_args


def video_info(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_frames:format=duration", "-of", "json", str(path)],
        capture_output=True, timeout=30, check=True)
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise ValueError("Choose a video file")
    stream = data["streams"][0]
    numerator, denominator = stream["avg_frame_rate"].split("/")
    fps = float(numerator) / float(denominator) if float(denominator) else 0
    if fps <= 0:
        raise ValueError("The source video has no readable frame rate")
    return stream | {"fps": fps, "duration": float(data["format"]["duration"])}


class OpenFrameVideoEdit:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "filename": ("STRING", {"default": "source.mp4"}),
            "operation": (["trim-video", "video-reframe"],),
            "width": ("INT", {"default": 1280, "min": 64, "max": 4096, "step": 2}),
            "height": ("INT", {"default": 720, "min": 64, "max": 4096, "step": 2}),
            "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120}),
            "frames": ("INT", {"default": 97, "min": 1, "max": 2401}),
            "trim_start": ("FLOAT", {"default": 0, "min": 0, "max": 86400}),
            "fit": (["crop", "pad"],),
            "anchor_x": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "anchor_y": ("FLOAT", {"default": .5, "min": 0, "max": 1}),
            "preserve_audio": ("BOOLEAN", {"default": True}),
            "encoding_quality": (["standard", "high"],),
            "filename_prefix": ("STRING", {"default": "OpenFrame"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_NODE = True
    FUNCTION = "edit"
    CATEGORY = "OpenFrame/Video"

    def edit(self, filename, operation, width, height, fps, frames, trim_start,
             fit, anchor_x, anchor_y, preserve_audio, encoding_quality, filename_prefix):
        from .nodes import _input_path
        source = _input_path(filename)
        info = video_info(source)
        if abs(info["fps"] - fps) > .001:
            raise ValueError("Trim Video and Reframe retain source FPS. Use the source frame rate; interpolation is a separate operation.")
        duration = frames / fps
        if trim_start + duration > info["duration"] + .001:
            raise ValueError("The selected interval extends beyond the source video")
        if width % 2 or height % 2:
            raise ValueError("H.264 output width and height must be even")
        if operation == "trim-video":
            if (width, height) != (info["width"], info["height"]):
                raise ValueError("Trim Video preserves source dimensions. Use Reframe to change framing.")
            geometry = []
        elif operation == "video-reframe" and fit == "crop":
            geometry = [f"scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2",
                        f"crop={width}:{height}:(iw-ow)*{anchor_x}:(ih-oh)*{anchor_y}"]
        elif operation == "video-reframe" and fit == "pad":
            geometry = [f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                        f"pad={width}:{height}:(ow-iw)*{anchor_x}:(oh-ih)*{anchor_y}:color=black"]
        else:
            raise ValueError("Unsupported video edit")
        filters = [f"fps={fps}", f"trim=end_frame={frames}", "setpts=PTS-STARTPTS", *geometry]
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        name = f"{stem}_{uuid.uuid4().hex[:10]}.mp4"
        target = output / name
        partial = target.with_suffix(".partial.mp4")
        # The trim filter bounds video frames. A second -frames:v limit can
        # terminate muxing before the AAC tail is flushed on FFmpeg 5.
        command = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-xerror", "-ss", str(trim_start), "-i", str(source),
                   "-map", "0:v:0", "-vf", ",".join(filters), "-t", str(duration)]
        if preserve_audio:
            command += ["-map", "0:a:0?", "-af", f"asetpts=PTS-STARTPTS,atrim=duration={duration}", "-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        command += ["-c:v", "libx264", "-threads", "2", "-preset", "medium"]
        command += video_encoding_args(width, height, fps, encoding_quality)
        command += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial)]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        started = time.monotonic()
        try:
            while True:
                comfy.model_management.throw_exception_if_processing_interrupted()
                if time.monotonic() - started > 1800:
                    raise ValueError("Video editing exceeded its 30-minute execution limit")
                try:
                    _, error = process.communicate(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise ValueError("Video editing failed: " + error.decode(errors="replace")[-1500:])
            measured = video_info(partial)
            if int(measured.get("nb_frames", 0)) != frames or (measured["width"], measured["height"]) != (width, height):
                raise ValueError("The output does not match the requested frame count and dimensions")
            comfy.model_management.throw_exception_if_processing_interrupted()
            partial.replace(target)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
            if process.stderr:
                process.stderr.close()
            partial.unlink(missing_ok=True)
        return {"ui": {"videos": [{"filename": name, "subfolder": "openframe", "type": "output", "format": "video/mp4", "fps": fps, "role": "result"}]}, "result": (str(target),)}
