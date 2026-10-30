"""CPU media primitives shared by Comfy nodes and hosted-provider pre/post processing.

This module deliberately has no ComfyUI or Torch dependency. Model inference is
still performed by ComfyUI; these helpers only prepare masks and encode media.
"""
from pathlib import Path
import subprocess
import wave

import cv2
import numpy as np
from PIL import Image, ImageOps

def decode_frames(path, width, height, fps, count, start=0):
    command = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path), "-an", "-vf", f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}", "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    result = subprocess.run(command, capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError("Could not decode source video: " + result.stderr.decode(errors="replace")[-1200:])
    n = len(result.stdout) // (width * height * 3)
    if n < count:
        raise ValueError(f"Source supplies {n} frames at {fps:g} fps; requested {count}. Choose a shorter duration or earlier start.")
    return np.frombuffer(result.stdout, np.uint8).reshape(n, height, width, 3).copy()


def fit_mask(image, width, height):
    image = ImageOps.exif_transpose(image).convert("L")
    return np.array(ImageOps.fit(image, (width, height), Image.Resampling.NEAREST), dtype=np.float32) / 255.0


def feather_mask(mask, width, method):
    if not width:
        return mask
    if method == "gaussian":
        return cv2.GaussianBlur(mask, (2 * width + 1, 2 * width + 1), 0) * mask
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    if method == "smooth-inward":
        if not mask.any() or mask.all():
            return mask
        outside = cv2.distanceTransform((1 - mask).astype(np.uint8), cv2.DIST_L2, 5)
        # Smooth the contour, not the footage. A distance ramp alone follows
        # every stair step in a rasterized/slightly upscaled diagonal mask.
        distance = cv2.GaussianBlur(inside - outside, (0, 0), float(width))
        ramp = np.clip((distance - width / 2) / width, 0, 1)
        # Keep small holes and concave boundaries feathered too; smoothing a
        # distance field must not fill them or create an opacity jump there.
        ramp = np.minimum(ramp, np.clip((inside - 1) / width, 0, 1))
    else:
        # Keep the original inward method reproducible for saved graphs.
        ramp = np.clip((inside - 1) / width, 0, 1)
    return (ramp * ramp * (3 - 2 * ramp)) * mask


def match_plate_lighting(generated, original, alpha):
    """Match low-frequency illumination without importing the old object's texture."""
    selected = (alpha > 0).astype(np.uint8) * 255
    if not selected.any():
        return original
    if selected.all():
        return generated
    _, _, width, height = cv2.boundingRect(selected)
    if min(width, height) < 3:
        return generated
    # Extend holes which touch the image edge into generated padding. Anchoring
    # the solve at the original image edge would leave the old shadow there.
    pad = 32
    source = cv2.copyMakeBorder(generated, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
    target = source.copy()
    target[pad:-pad, pad:-pad] = original
    mask = cv2.copyMakeBorder(selected, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
    mask[[0, -1]] = 0
    mask[:, [0, -1]] = 0
    x, y, width, height = cv2.boundingRect(mask)
    result = cv2.seamlessClone(source, target, mask, (x + width // 2, y + height // 2), cv2.NORMAL_CLONE)
    return result[pad:-pad, pad:-pad]


def propagate_mask(images, first, method="static", check_cancelled=lambda: None):
    """Propagate a first-frame mask; SAM2 is supplied by an optional model runtime."""
    if method not in {"static", "flow"}:
        raise ValueError("SAM2 tracking requires a local SAM2 runtime; select static or optical flow when it is unavailable.")
    masks = np.repeat(first[None], len(images), axis=0)
    if method == "flow" and len(images) > 1:
        height, width = images.shape[1:3]
        yy, xx = np.mgrid[:height, :width].astype(np.float32)
        previous_gray = cv2.cvtColor(images[0], cv2.COLOR_RGB2GRAY)
        for i in range(1, len(images)):
            check_cancelled()
            gray = cv2.cvtColor(images[i], cv2.COLOR_RGB2GRAY)
            backward = cv2.calcOpticalFlowFarneback(gray, previous_gray, None, .5, 3, 21, 3, 5, 1.2, 0)
            masks[i] = cv2.remap(masks[i - 1], xx + backward[..., 0], yy + backward[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            previous_gray = gray
    return masks


def prepare_masks(masks, dilation, feather, method="smooth-inward", edit_margin=0):
    masks = (masks >= .5).astype(np.float32)
    generation, blend = [], []
    for mask in masks:
        # A tracker may return the tight semantic silhouette even when the
        # initial brush selection included a buffer. Keep feathering outside
        # that silhouette rather than restoring the original object's edge.
        if edit_margin:
            mask = cv2.dilate(mask, np.ones((2 * edit_margin + 1, 2 * edit_margin + 1), np.uint8))
        generation.append(cv2.dilate(mask, np.ones((2 * dilation + 1, 2 * dilation + 1), np.uint8)) if dilation else mask)
        blend.append(feather_mask(mask, feather, method))
    return np.stack(generation), np.stack(blend)


def composite_frame(generated, original=None, alpha=None, match_lighting=False):
    """Convert RGB floats in [0,1] into a composited uint8 frame, without blur."""
    if original is None or alpha is None:
        return (np.clip(generated, 0, 1) * 255).round().astype(np.uint8)
    opacity = alpha[..., None] if alpha.ndim == 2 else alpha
    if not match_lighting:
        frame = generated * opacity + original * (1 - opacity)
        return (np.clip(frame, 0, 1) * 255).round().astype(np.uint8)
    pixels = (np.clip(generated, 0, 1) * 255).round().astype(np.uint8)
    plate = (np.clip(original, 0, 1) * 255).round().astype(np.uint8)
    matched = match_plate_lighting(pixels, plate, opacity[..., 0])
    return (matched * opacity + plate * (1 - opacity)).round().clip(0, 255).astype(np.uint8)


def video_encoding_args(width, height, fps, quality="legacy"):
    if quality == "legacy":
        return ["-crf", "17"]
    if quality not in {"standard", "high"}:
        raise ValueError("Choose Standard or High video bitrate")
    # An explicit average-rate target; actual VBR depends on scene complexity.
    rate = max(1_000_000, round(width * height * fps * (.16 if quality == "high" else .09)))
    return ["-b:v", str(rate), "-maxrate", str(rate * 2), "-bufsize", str(rate * 4)]


def encode_video(target, frames, width, height, fps, count, source_audio=None,
                 trim_start=0, audio=None, check_cancelled=lambda: None, encoding_quality="legacy"):
    """Stream uint8 RGB frames to H264, preserving source or supplied float audio."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
    audio_temp = None
    if source_audio:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(source_audio)], capture_output=True, timeout=30, check=True)
        if not probe.stdout.strip():
            source_audio = None
    if source_audio:
        cmd += ["-ss", str(trim_start), "-i", str(source_audio), "-map", "0:v:0", "-map", "1:a:0"]
    elif audio is not None:
        audio_temp = target.with_suffix(".wav")
        waveform = np.clip(audio["waveform"], -1, 1)
        with wave.open(str(audio_temp), "wb") as wav:
            wav.setnchannels(waveform.shape[0]); wav.setsampwidth(2); wav.setframerate(int(audio["sample_rate"]))
            wav.writeframes((waveform.T * 32767).astype("<i2").tobytes())
        cmd += ["-i", str(audio_temp), "-map", "0:v:0", "-map", "1:a:0"]
    cmd += ["-c:v", "libx264", "-preset", "medium"] + video_encoding_args(width, height, fps, encoding_quality)
    cmd += ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", str(count / fps), "-movflags", "+faststart", str(target)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            check_cancelled()
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode(errors="replace")
        if process.wait(timeout=180):
            raise RuntimeError("Video encoding failed: " + error[-1500:])
    except BaseException:
        process.kill(); process.wait(); target.unlink(missing_ok=True)
        raise
    finally:
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
        if process.stderr is not None:
            process.stderr.close()
        if audio_temp:
            audio_temp.unlink(missing_ok=True)
    return target


def encode_mask_video(target, masks, width, height, fps):
    mask_bytes = (np.clip(masks, 0, 1) * 255).round().astype(np.uint8).tobytes()
    encoded = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)], input=mask_bytes, capture_output=True, timeout=120)
    if encoded.returncode:
        raise RuntimeError("Mask video encoding failed: " + encoded.stderr.decode(errors="replace")[-1000:])
