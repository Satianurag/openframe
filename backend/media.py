"""Media ingestion and previews; never use an inference preview as a final asset."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import math
import shutil
import subprocess
import uuid
import zipfile
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
    with path.open("rb") as stream:
        if stream.read(4).startswith(b"PK"):
            raise ValueError("Archives are generated download artifacts, not accepted source uploads")
    if not shutil.which("ffprobe"):
        raise ValueError("Video ingestion requires ffmpeg/ffprobe. Install ffmpeg and restart the studio.")
    try:
        process = subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
        ], capture_output=True, timeout=30, check=True)
        data = json.loads(process.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError("This file could not be read as an image or video") from exc
    stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video" and not item.get("disposition", {}).get("attached_pic")), None)
    if not stream:
        audio = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), None)
        if not audio:
            raise ValueError("Upload an image, video or audio recording")
        container = data.get("format", {}).get("format_name", "")
        suffix = next((extension for format_name, extension in [("mp3", ".mp3"), ("wav", ".wav"), ("flac", ".flac"), ("ogg", ".ogg"), ("mp4", ".m4a"), ("webm", ".webm"), ("aac", ".aac")] if format_name in container), None)
        duration = float(audio.get("duration") or data.get("format", {}).get("duration") or 0)
        if not suffix or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Use a readable WAV, MP3, M4A, FLAC, OGG, WebM or AAC recording with a known duration")
        return {"kind": "audio", "width": None, "height": None, "duration": duration, "fps": None,
                "suffix": suffix, "mime_type": {".m4a": "audio/mp4", ".webm": "audio/webm"}.get(suffix, mimetypes.guess_type("audio" + suffix)[0] or "application/octet-stream"),
                "has_audio": True, "codec": audio.get("codec_name"), "sample_rate": int(audio.get("sample_rate", 0)), "channels": int(audio.get("channels", 0))}
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
    # FFprobe shares a demuxer name for Matroska/WebM; FFV1 is not a WebM codec.
    suffix = ".mkv" if "matroska" in container and stream.get("codec_name") not in {"vp8", "vp9", "av1"} else ".webm" if "webm" in container else ".mp4" if "mp4" in container or "mov" in container else ".mkv"
    return {"kind": "video", "width": width, "height": height, "duration": duration,
            "fps": fps, "has_audio": any(item.get("codec_type") == "audio" for item in data.get("streams", [])),
            "suffix": suffix, "mime_type": mimetypes.guess_type("video" + suffix)[0] or "video/mp4",
            "codec": stream.get("codec_name"), "rotation": rotation,
            "frame_count": int(stream["nb_frames"]) if str(stream.get("nb_frames", "")).isdigit() else None}


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


def public_asset(record: dict, store: Store | None = None) -> dict:
    result = {key: value for key, value in record.items() if key not in {"path", "thumbnail_path"}}
    if store and "role" not in result and record.get("source_job_id"):
        job = store.get("jobs", record["source_job_id"])
        for output in (job or {}).get("outputs", []):
            if output.get("id") == record["id"] and output.get("role"):
                result["role"] = output["role"]
                break
    return result


def register_generated_archive(store: Store, path: Path, name: str, *, source_job_id: str, role: str = "result") -> dict:
    """Register only our bounded HDR EXR archive; never decode it with ffprobe."""
    path = path.resolve()
    if not path.is_relative_to(store.root / "renders" / source_job_id) or not 0 < path.stat().st_size <= 5 * 1024**3:
        raise ValueError("Generated archive is outside its job directory or exceeds the bounded HDR export size")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if len(members) > 243 or len(set(names)) != len(names):
            raise ValueError("HDR archive has duplicate or excessive members")
        if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > 65536:
            raise ValueError("HDR archive is missing its bounded colour/frame manifest")
        manifest = json.loads(archive.read("manifest.json"))
        width, height, frames, fps = (manifest.get(key) for key in ("width", "height", "frames", "fps"))
        if (any(type(value) is not int for value in (width, height, frames))
                or not 1 <= frames <= 241 or min(width, height) < 1 or min(width, height) > 1088 or max(width, height) > 1920
                or width * height > 1920 * 1088 or width * height * frames * 6 > 4 * 1024**3
                or not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 1 <= fps <= 120
                or manifest.get("color_space") != "linear ACEScg" or manifest.get("bit_depth") != "16-bit float"
                or manifest.get("frame_pattern") != "frames/frame_%06d.exr"):
            raise ValueError("HDR archive manifest does not match the supported linear ACEScg half-float frame contract")
        expected = {f"frames/frame_{index:06d}.exr" for index in range(1, frames + 1)} | {"manifest.json"}
        if set(names) - {"frames/"} != expected:
            raise ValueError("HDR archive must contain exactly its declared frame sequence and manifest")
        for item in members:
            if item.flag_bits & 1 or item.compress_type != zipfile.ZIP_STORED or item.file_size > width * height * 8 + 1024**2:
                raise ValueError("Unexpected encrypted, compressed or oversized outer ZIP entry")
            if item.filename.endswith(".exr"):
                with archive.open(item) as frame:
                    if frame.read(4) != b"\x76\x2f\x31\x01":
                        raise ValueError("An HDR frame is missing the OpenEXR file signature")
    digest = sha256_file(path)
    previous = store.by_hash(digest)
    if previous and previous.get("kind") == "archive" and Path(previous["path"]).is_file():
        return previous
    ident = uuid.uuid4().hex
    record = {"id": ident, "name": Path(name.replace("\\", "/")).name[:200] or "HDR-frames.zip", "created_at": now(),
              "kind": "archive", "mime_type": "application/zip", "path": str(path), "size": path.stat().st_size, "sha256": digest,
              "url": f"/api/assets/{ident}/file", "thumbnail_url": None, "thumbnail_path": None,
              "source_job_id": source_job_id, "role": role, "width": width, "height": height, "frame_count": frames,
              "fps": fps, "duration": frames / fps, "has_audio": False, "archive_manifest": manifest}
    store.insert("assets", record)
    return record


def register_asset(store: Store, path: Path, name: str, *, move: bool = False, source_job_id: str | None = None, role: str | None = None) -> dict:
    """Validate before registration. Upload temporaries move; generated files stay in their job directory."""
    digest = sha256_file(path)
    previous = store.by_hash(digest)
    if previous and previous.get("kind") == "archive":
        raise ValueError("Archives are generated download artifacts, not accepted source uploads")
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
        elif details["kind"] == "video":
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
    if role is not None:
        record["role"] = role
    store.insert("assets", record)
    return record
