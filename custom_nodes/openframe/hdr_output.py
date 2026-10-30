"""Float-preserving HDR exports; encoding runs beside ComfyUI on the render host."""
from pathlib import Path
import json
import math
import os
import selectors
import subprocess
import time
import uuid
import zipfile

import comfy.model_management
import folder_paths
import numpy as np

from .advanced_video import _input
from .media import video_encoding_args


def _cancel():
    comfy.model_management.throw_exception_if_processing_interrupted()


def _stream_encode(command, frames):
    """Bound memory and stderr while keeping pipe writes cancellable."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, bufsize=0)
    errors = bytearray()
    deadline = time.monotonic() + 900
    with selectors.DefaultSelector() as selector:
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stderr, selectors.EVENT_READ)
        iterator, pending, finished = iter(frames), memoryview(b""), False
        try:
            while selector.get_map() or process.poll() is None:
                _cancel()
                if time.monotonic() > deadline:
                    raise TimeoutError("HDR encoding exceeded its 15-minute limit")
                if not pending and not finished:
                    try:
                        pending = memoryview(next(iterator))
                    except StopIteration:
                        finished = True
                        selector.unregister(process.stdin)
                        process.stdin.close()
                for key, _ in selector.select(.25):
                    if key.fileobj is process.stdin:
                        try:
                            written = os.write(key.fd, pending[:262144])
                            pending = pending[written:]
                        except BlockingIOError:
                            pass
                    else:
                        data = os.read(key.fd, 8192)
                        if data:
                            errors.extend(data)
                            del errors[:-8192]
                        else:
                            selector.unregister(process.stderr)
            if process.wait() != 0:
                raise RuntimeError("HDR encoding failed: " + errors.decode(errors="replace")[-2000:])
        except BaseException as error:
            if process.poll() is None:
                process.kill()
            process.wait()
            if isinstance(error, BrokenPipeError):
                raise RuntimeError("HDR encoder closed its input: " + errors.decode(errors="replace")[-2000:]) from error
            raise
        finally:
            process.stdin.close()
            process.stderr.close()


class OpenFrameSaveHDRVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",), "fps": ("FLOAT", {"default": 24, "min": 1, "max": 120}),
            "frames": ("INT", {"default": 49, "min": 1, "max": 241}),
            "filename_prefix": ("STRING", {"default": "OpenFrame"}),
            "output_format": (["hevc10", "prores10", "exr16"],),
            "color_space": (["HDR", "linear ACEScg"],),
            "preserve_audio": ("BOOLEAN", {"default": True}),
        }, "optional": {
            "source_filename": ("STRING", {"default": ""}),
            "trim_start": ("FLOAT", {"default": 0, "min": 0}),
            "encoding_quality": (["standard", "high"], {"default": "standard"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Video"

    def save(self, images, fps, frames, filename_prefix, output_format, color_space,
             preserve_audio, source_filename="", trim_start=0, encoding_quality="standard"):
        if output_format not in {"hevc10", "prores10", "exr16"}:
            raise ValueError("Choose HEVC 10-bit, ProRes 10-bit, or EXR 16-bit float")
        expected_space = "linear ACEScg" if output_format == "exr16" else "HDR"
        if color_space != expected_space:
            raise ValueError(f"{output_format} requires {expected_space} input; convert ACEScct before saving")
        if images.ndim != 4 or images.shape[-1] != 3 or len(images) < frames:
            raise ValueError("HDR output requires the requested number of RGB frames")
        height, width = images.shape[1:3]
        if not 1 <= frames <= 241 or min(width, height) < 2 or max(width, height) > 1920 or min(width, height) > 1088:
            raise ValueError("HDR export is bounded to 241 frames and a 1920 by 1088 canvas, in either orientation")
        if width % 2 or height % 2 or not math.isfinite(fps) or not 1 <= fps <= 120:
            raise ValueError("HDR video requires even dimensions and a frame rate between 1 and 120")
        if not math.isfinite(trim_start) or trim_start < 0 or encoding_quality not in {"standard", "high"}:
            raise ValueError("Invalid HDR trim or encoding quality")
        raw_bytes = width * height * frames * 6
        if raw_bytes > 4 * 1024 ** 3:
            raise ValueError("The requested EXR/raw frame data exceeds the 4 GiB export limit")
        output = Path(folder_paths.get_output_directory()) / "openframe"
        output.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        suffix = {"hevc10": ".mp4", "prores10": ".mov", "exr16": ".zip"}[output_format]
        name = f"{stem}_hdr_{uuid.uuid4().hex[:10]}{suffix}"
        target = output / name
        partial = target.with_name(target.stem + ".partial" + suffix)
        metadata = {
            "format": output_format, "width": width, "height": height, "frames": frames,
            "fps": fps, "duration": frames / fps, "color_space": color_space,
            "bit_depth": "16-bit float" if output_format == "exr16" else "10-bit",
            "uncompressed_rgb16_bytes": raw_bytes, "eight_bit_intermediate": False,
        }
        try:
            if output_format == "exr16":
                # These helpers are from the pinned ComfyUI revision. Encode one
                # frame in memory and stream it into the archive; no frame directory.
                from comfy_extras.nodes_images import _encode_image, inject_exr_metadata
                metadata.update(primaries="ACEScg AP1 / D60", transfer="scene-linear",
                                reference_white_nits=203, compression="lossless EXR ZIP16",
                                frame_pattern="frames/frame_%06d.exr", first_frame=1,
                                audio_in_archive=False, audio_preserved_in_preview=bool(preserve_audio))
                with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                    for index in range(frames):
                        _cancel()
                        frame = images[index].detach().float().cpu()
                        pixels = frame.numpy()
                        if not np.isfinite(pixels).all() or np.abs(pixels).max() > 65504:
                            raise ValueError("HDR pixels cannot be represented as finite half-float EXR; values were not clipped")
                        encoded = _encode_image(frame, "exr", "16-bit float", "linear ACEScg")
                        encoded = inject_exr_metadata(encoded, None, None, colorspace="linear ACEScg")
                        archive.writestr(f"frames/frame_{index + 1:06d}.exr", encoded)
                    archive.writestr("manifest.json", json.dumps(metadata, indent=2))
                outputs = {"archives": [{"filename": name, "subfolder": "openframe", "type": "output",
                                         "format": "application/zip", "role": "result"}]}
            else:
                metadata.update(primaries="BT.2020", transfer="ARIB STD-B67 HLG", range="limited",
                                reference_display_nits=1000, clipped_channel_values=0,
                                codec="HEVC Main 10" if output_format == "hevc10" else "ProRes 422 HQ")
                command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le",
                           "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
                if preserve_audio and source_filename:
                    command += ["-ss", str(trim_start), "-i", str(_input(source_filename)),
                                "-map", "0:v:0", "-map", "1:a:0?"]
                else:
                    command += ["-map", "0:v:0", "-an"]
                pixel_format = "yuv420p10le" if output_format == "hevc10" else "yuv422p10le"
                command += ["-vf", f"scale=in_range=full:out_range=limited:out_color_matrix=bt2020,format={pixel_format},setparams=range=limited:color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc",
                            "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                            "-colorspace", "bt2020nc", "-color_range", "tv"]
                if output_format == "hevc10":
                    command += ["-c:v", "libx265", "-profile:v", "main10", "-preset", "medium",
                                "-x265-params", "log-level=error:pools=4", "-tag:v", "hvc1"]
                    command += video_encoding_args(width, height, fps, encoding_quality)
                    command += ["-c:a", "aac", "-b:a", "192k"]
                else:
                    command += ["-c:v", "prores_ks", "-profile:v", "3", "-c:a", "pcm_s24le"]
                # The iterator already supplies exactly N frames. An output
                # frame cap can stop FFmpeg before it drains the audio input.
                command += ["-t", str(frames / fps),
                            "-movflags", "+faststart", str(partial)]

                def pixels():
                    for index in range(frames):
                        _cancel()
                        rgb = images[index].detach().float().cpu().numpy()
                        if not np.isfinite(rgb).all():
                            raise ValueError("HDR contains non-finite pixel values")
                        metadata["clipped_channel_values"] += int(np.count_nonzero((rgb < 0) | (rgb > 1)))
                        yield np.rint(np.clip(rgb, 0, 1) * 65535).astype("<u2").tobytes()

                _stream_encode(command, pixels())
                outputs = {"videos": [{"filename": name, "subfolder": "openframe", "type": "output",
                                       "format": "video/mp4" if output_format == "hevc10" else "video/quicktime",
                                       "fps": fps, "role": "result"}]}
            _cancel()
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        return {"ui": {**outputs, "openframe_hdr": [metadata]}, "result": (str(target),)}
