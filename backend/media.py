"""Media ingestion and previews; never use an inference preview as a final asset."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .store import Store, now

Image.MAX_IMAGE_PIXELS = 80_000_000
IMAGE_SUFFIXES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "TIFF": ".tiff"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_media(path: Path) -> dict:
    try:
        with Image.open(path) as image:
            if image.format not in IMAGE_SUFFIXES:
                raise ValueError("Use PNG, JPEG, WebP, GIF or TIFF images")
            fmt = image.format
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("This image exceeds the 80-megapixel ingestion limit")
            image.verify()
        with Image.open(path) as image:
            oriented = ImageOps.exif_transpose(image)
            width, height = oriented.size
        return {"kind": "image", "width": width, "height": height, "duration": None, "fps": None,
                "suffix": IMAGE_SUFFIXES[fmt], "mime_type": Image.MIME.get(fmt, "image/png"), "has_audio": False}
    except Image.DecompressionBombError as exc:
        raise ValueError("This image exceeds the 80-megapixel ingestion limit") from exc
    except (UnidentifiedImageError, OSError):
        pass
    if not shutil.which("ffprobe"):
        raise ValueError("Video ingestion requires ffmpeg/ffprobe. Install ffmpeg and restart the studio.")
    try:
        process = subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
        ], capture_output=True, timeout=30, check=True)
        data = json.loads(process.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError("This file could not be read as an image or video") from exc
    stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), None)
    if not stream:
        raise ValueError("Upload an image or a video containing a video stream")
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    if width < 1 or height < 1 or width * height > 80_000_000:
        raise ValueError("Unsupported video dimensions")
    rotation = next((item.get("rotation", 0) for item in stream.get("side_data_list", []) if "rotation" in item), 0)
    if abs(int(rotation)) % 180 == 90:
        width, height = height, width
    try:
        fps = float(Fraction(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0"))
    except (ValueError, ZeroDivisionError):
        fps = 0
    duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
    container = data.get("format", {}).get("format_name", "")
    suffix = ".webm" if "webm" in container else ".mp4" if "mp4" in container or "mov" in container else ".mkv"
    return {"kind": "video", "width": width, "height": height, "duration": duration,
            "fps": fps, "has_audio": any(item.get("codec_type") == "audio" for item in data.get("streams", [])),
            "suffix": suffix, "mime_type": mimetypes.guess_type("video" + suffix)[0] or "video/mp4",
            "codec": stream.get("codec_name"), "rotation": rotation}


def frame_bytes(path: Path, timestamp: float = 0, *, thumbnail: bool = False) -> bytes:
    try:
        with Image.open(path) as image:
            frame = ImageOps.exif_transpose(image).convert("RGBA")
            if thumbnail:
                frame.thumbnail((640, 640))
            buffer = io.BytesIO()
            frame.save(buffer, "PNG")
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError):
        pass
    if not shutil.which("ffmpeg"):
        raise ValueError("Frame extraction requires ffmpeg")
    args = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(max(0, timestamp)), "-i", str(path), "-frames:v", "1"]
    if thumbnail:
        args += ["-vf", "scale=640:640:force_original_aspect_ratio=decrease"]
    args += ["-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    try:
        result = subprocess.run(args, capture_output=True, timeout=30, check=True)
    except subprocess.SubprocessError as exc:
        raise ValueError("Could not decode the requested video frame") from exc
    if not result.stdout:
        raise ValueError("No frame exists at that time")
    return result.stdout


def public_asset(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in {"path", "thumbnail_path"}}


def register_asset(store: Store, path: Path, name: str, *, move: bool = False, source_job_id: str | None = None) -> dict:
    """Validate before registration. Upload temporaries move; generated files stay in their job directory."""
    digest = sha256_file(path)
    previous = store.by_hash(digest)
    if previous and Path(previous["path"]).is_file():
        if move and path != Path(previous["path"]):
            path.unlink(missing_ok=True)
        return previous
    details = inspect_media(path)
    ident = uuid.uuid4().hex
    media_root = store.root / "assets"
    media_root.mkdir(exist_ok=True, mode=0o700)
    if move:
        target = media_root / f"{ident}{details.pop('suffix')}"
        path.replace(target)
    else:
        target = path.resolve()
        details.pop("suffix", None)
    thumb_path = media_root / f"{ident}.thumb.jpg"
    try:
        if details["kind"] == "image":
            with Image.open(target) as image:
                thumbnail = ImageOps.exif_transpose(image).convert("RGB")
                thumbnail.thumbnail((640, 640))
                thumbnail.save(thumb_path, "JPEG", quality=85)
        else:
            with Image.open(io.BytesIO(frame_bytes(target, thumbnail=True))) as image:
                image.convert("RGB").save(thumb_path, "JPEG", quality=85)
    except (OSError, ValueError):
        thumb_path.unlink(missing_ok=True)
    record = {
        "id": ident, "name": Path(name.replace("\\", "/")).name[:200] or "Untitled",
        "created_at": now(), "sha256": digest, "size": target.stat().st_size,
        "path": str(target), "url": f"/api/assets/{ident}/file",
        "thumbnail_path": str(thumb_path) if thumb_path.exists() else None,
        "thumbnail_url": f"/api/assets/{ident}/thumbnail" if thumb_path.exists() else None,
        "source_job_id": source_job_id, **details,
    }
    store.insert("assets", record)
    return record
