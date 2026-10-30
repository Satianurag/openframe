"""Reviewed sequence narration, captions and bounded assembly filters."""
import html
import hashlib
import os
import shutil
import struct
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


@lru_cache(maxsize=1)
def caption_ffmpeg():
    """Select a libass-enabled encoder only for captioned assembly."""
    configured = os.environ.get("OPENFRAME_CAPTION_FFMPEG")
    candidates = [configured] if configured else [shutil.which("ffmpeg"),
        "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg"]
    for candidate in dict.fromkeys(item for item in candidates if item):
        if not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and any(len(parts := line.split()) > 1 and parts[1] == "subtitles" for line in result.stdout.splitlines()):
            return candidate
    raise ValueError("Caption burn-in requires FFmpeg with libass/subtitles support. Install a libass-enabled build (Homebrew: brew install ffmpeg-full), or set OPENFRAME_CAPTION_FFMPEG to its executable. SRT/VTT exports do not require it.")


class NarrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=1200)
    voice: Literal["US_Emma", "UK_George", "灵小柔", "灵楷"] = "US_Emma"
    language: Literal["English", "Chinese"] = "English"
    speed: float = Field(default=1, ge=.75, le=1.5)
    start: float = Field(default=0, ge=0, le=300)


class CaptionCue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: float = Field(ge=0, le=300)
    end: float = Field(gt=0, le=300.1)
    text: str = Field(min_length=1, max_length=300)

    @field_validator("text")
    @classmethod
    def clean_text(cls, text):
        if not text.strip() or "-->" in text or any(not line.strip() for line in text.strip().splitlines()) or any(ord(char) < 32 and char not in "\n\t" for char in text):
            raise ValueError("Caption text must be readable and cannot contain subtitle control sequences")
        return text.strip()


class CaptionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["none", "narration", "soundtrack", "manual"] = "none"
    language: Literal["English", "Chinese"] = "English"
    burn_in: bool = False
    cues: list[CaptionCue] = Field(default_factory=list, max_length=1000)


class CaptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    cues: list[CaptionCue] = Field(max_length=1000)
    burn_in: bool = False
    reassemble: bool = False


class NarrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    narration: NarrationInput


class EpisodeAudioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    expected_document_revision: int | None = Field(default=None, ge=1)
    audio_asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    audio_start: float = Field(default=0, ge=0, le=86400)
    pad_audio_silence: bool = False
    audio_provider: Literal["local"] | None = None
    keep_shot_audio: bool = False
    background_audio_asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    background_audio_start: float = Field(default=0, ge=0, le=86400)
    background_gain: float = Field(default=.15, ge=0, le=2)
    duck_background: bool = True
    narration_gain: float = Field(default=1, ge=0, le=2)
    shot_audio_gain: float = Field(default=1, ge=0, le=2)
    reassemble: bool = False


def finalize_streaming_wav(asset, directory):
    """Finalize an unknown-length PCM/float RIFF header in a derived file only."""
    source = Path(asset["path"])
    size = source.stat().st_size
    with source.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            return asset, None
        unknown_riff = struct.unpack_from("<I", header, 4)[0] == 0xffffffff
        block_align = rate = 0
        data_position = data_size = None
        unknown_data = False
        while stream.tell() + 8 <= size:
            chunk_position = stream.tell()
            kind, length = struct.unpack("<4sI", stream.read(8))
            if kind == b"fmt ":
                fmt = stream.read(min(length, 40))
                if len(fmt) < 16:
                    raise ValueError("WAV format header is truncated; export a finalized recording")
                encoding, channels, rate, _, block_align, bits = struct.unpack_from("<HHIIHH", fmt)
                if encoding == 0xfffe and len(fmt) >= 40:
                    encoding = struct.unpack_from("<H", fmt, 24)[0]
                if encoding not in {1, 3}:
                    block_align = 0
            if kind == b"data":
                data_position = chunk_position + 8
                unknown_data = length == 0xffffffff
                data_size = size - data_position if unknown_data else length
                break
            if length == 0xffffffff or chunk_position + 8 + length > size:
                raise ValueError("WAV metadata is truncated; export a finalized recording")
            stream.seek(chunk_position + 8 + length + (length % 2))
    if not unknown_riff and not unknown_data:
        return asset, None
    if data_position is None or not block_align or not rate or data_size <= 0 or data_size % block_align or data_position + data_size > size or size - 8 >= 0xffffffff:
        raise ValueError("This streaming WAV cannot be finalized safely. Re-export it as a finalized PCM WAV and replace the episode audio.")
    frames = data_size // block_align
    if abs(frames / rate - float(asset["duration"])) > max(.001, 1 / rate):
        raise ValueError("Streaming WAV sample count differs from the recorded duration; replace the recording")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{asset['sha256']}.wav"
    if not target.exists():
        partial = target.with_suffix(".partial.wav")
        try:
            with source.open("rb") as reader, partial.open("wb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
            with partial.open("r+b") as writer:
                writer.seek(4); writer.write(struct.pack("<I", size - 8))
                writer.seek(data_position - 4); writer.write(struct.pack("<I", data_size))
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with target.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return {**asset, "path": str(target)}, {"asset_id": asset["id"], "source_sha256": asset["sha256"],
        "derived_sha256": digest.hexdigest(), "method": "Finalized unknown-length RIFF/data headers; sample payload unchanged",
        "sample_frames": frames, "sample_rate": rate, "source_bytes": size}


def validate_cues(cues, duration):
    previous_end = 0
    for cue in cues:
        CaptionCue.model_validate(cue)
        if not cue["start"] < cue["end"] <= duration + .001 or cue["start"] < previous_end - .001:
            raise ValueError("Captions must be ordered, non-overlapping and contained in the measured episode")
        previous_end = cue["end"]
    return cues


def cues_from_words(words, offset=0, language="English"):
    cues, group = [], []
    def flush():
        if not group:
            return
        text = ("" if language == "Chinese" else " ").join(item["text"] for item in group)
        start, end = group[0]["start"] + offset, max(item["end"] for item in group) + offset
        if end <= start:
            raise ValueError("Recognized words have no usable duration; edit captions manually")
        cues.append({"start": start, "end": end, "text": text})
        group.clear()
    for word in words:
        if group and (len(group) >= 7 or sum(len(item["text"]) + 1 for item in group) + len(word["text"]) > 70
                      or word["end"] - group[0]["start"] > 4):
            flush()
        group.append(word)
    flush()
    return cues


def caption_text(cues, fmt):
    def stamp(seconds):
        value = round(seconds * 1000)
        hours, value = divmod(value, 3600000)
        minutes, value = divmod(value, 60000)
        seconds, millis = divmod(value, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02}{',' if fmt == 'srt' else '.'}{millis:03}"
    lines = ["WEBVTT", ""] if fmt == "vtt" else []
    for index, cue in enumerate(cues, 1):
        lines += [str(index), f"{stamp(cue['start'])} --> {stamp(cue['end'])}", html.escape(cue["text"], quote=False), ""]
    return "\n".join(lines) + "\n"


def mix_audio(command, filters, episode, narration_tracks, duration, input_count, foreground, background):
    """Append real audio inputs and explicit gain/ducking, returning the mapped label."""
    labels = []
    if foreground:
        gain = episode.get("shot_audio_gain", 1) if episode.get("keep_shot_audio") else 1
        filters.append(f"[outa]volume={gain},aformat=sample_fmts=fltp:channel_layouts=stereo[baseaudio]")
        labels.append("baseaudio")
    for index, track in enumerate(narration_tracks):
        command += ["-i", track["asset"]["path"]]
        label = f"narration{index}"
        filters.append(f"[{input_count}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={episode.get('narration_gain', 1)},adelay={round(track['offset'] * 48000)}S:all=1,apad,atrim=duration={duration:.9f}[{label}]")
        labels.append(label); input_count += 1
    if labels:
        filters.append("".join(f"[{label}]" for label in labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[foreground]")
    if background:
        command += ["-ss", str(episode.get("background_audio_start", 0)), "-i", background["path"]]
        filters.append(f"[{input_count}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,atrim=duration={duration:.9f},volume={episode.get('background_gain', .15)}[background]")
        if labels and episode.get("duck_background", True):
            filters += ["[foreground]asplit=2[foregroundmix][duckkey]", "[background][duckkey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=250[ducked]",
                        "[foregroundmix][ducked]amix=inputs=2:normalize=0:duration=longest[mixed]"]
        elif labels:
            filters.append("[foreground][background]amix=inputs=2:normalize=0:duration=longest[mixed]")
        else:
            filters.append("[background]anull[mixed]")
    elif labels:
        filters.append("[foreground]anull[mixed]")
    else:
        return None
    filters.append(f"[mixed]alimiter=limit=0.95:level=false:latency=true,atrim=duration={duration:.9f},asetpts=PTS-STARTPTS[finalaudio]")
    return "finalaudio"
