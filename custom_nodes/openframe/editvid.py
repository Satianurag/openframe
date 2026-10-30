"""Bounded interval input for the separately installed Apache native EditVid port."""
import hashlib
import json
import subprocess
from pathlib import Path

import torch
import folder_paths
import comfy.model_management


class OpenFrameEditVidInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename": ("STRING", {"default": "source.mp4"}),
            "frames": ("INT", {"default": 49, "min": 9, "max": 241}),
            "fps": ("FLOAT", {"default": 24, "min": 24, "max": 24}),
            "trim_start": ("FLOAT", {"default": 0, "min": 0, "max": 36000})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Video"

    def load(self, filename, frames, fps, trim_start):
        path = Path(folder_paths.get_annotated_filepath(filename)).resolve()
        if not path.is_relative_to(Path(folder_paths.get_input_directory()).resolve()) or not path.is_file():
            raise ValueError("EditVid source must be a regular media file inside ComfyUI/input.")
        if not 9 <= frames <= 241 or fps != 24 or not 0 <= trim_start <= 36000:
            raise ValueError("EditVid interval must contain 9–241 frames at 24 FPS with a nonnegative start.")
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(path)], timeout=30))
        stream = probe["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        rotation = float(stream.get("tags", {}).get("rotate", 0)) or next((float(v.get("rotation", 0)) for v in stream.get("side_data_list", []) if v.get("rotation")), 0)
        if rotation % 360 or width * height > 2097152:
            raise ValueError("Prepare an upright source of at most 2,097,152 native pixels before EditVid; no implicit source rotation/resizing is applied.")
        # Keep only the required float IMAGE batch and one decoded RGB frame;
        # do not capture a second whole native-resolution clip or write an FFV1 copy.
        images = torch.empty((frames, height, width, 3), dtype=torch.float32, device="cpu")
        command = ["ffmpeg", "-v", "error", "-nostdin", "-ss", str(trim_start), "-i", str(path),
                   "-map", "0:v:0", "-an", "-vf", f"fps={fps}", "-frames:v", str(frames),
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            size = width * height * 3
            for index in range(frames):
                comfy.model_management.throw_exception_if_processing_interrupted()
                raw = process.stdout.read(size)
                if len(raw) != size:
                    raise ValueError(f"Source supplied only {index} frames in the selected interval; choose a shorter interval. No frames are looped or padded.")
                images[index].copy_(torch.frombuffer(bytearray(raw), dtype=torch.uint8).reshape(height, width, 3)).div_(255)
            if process.wait(timeout=30):
                raise ValueError("FFmpeg could not decode the selected EditVid interval.")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        return {"result": (images,), "ui": {"openframe_editvid": [{
            "source_sha256": digest, "source_width": width, "source_height": height,
            "frames": frames, "fps": fps, "trim_start": trim_start,
            "selection": "FFmpeg fps selection at native dimensions; no frame padding or looping",
            "resize": "Following native ImageScale applies Lanczos and an explicit centered crop to the requested output canvas",
        }]}}
