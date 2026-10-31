#!/usr/bin/env python3
"""End-to-end QA harness for Cinema Studio.

Two modes:

  --graphs-only   Import the engine, build/validate the matrix graphs, no GPU.
  --live          Submit real jobs through the running API, poll, download and
                  probe outputs, and record evidence. Requires a configured
                  ComfyUI provider for render cases; rejection/lifecycle cases
                  still run when it is unavailable.

The harness never fabricates media and never turns a skipped/blocked case into
a pass. Evidence is written to artifacts/qa-cinema/<timestamp>/ (or --out).

Examples:
  .venv/bin/python scripts/qa_cinema.py --graphs-only
  OPENFRAME_API_URL=http://127.0.0.1:8001 \
  OPENFRAME_COMFY_URL=http://127.0.0.1:8188 \
  .venv/bin/python scripts/qa_cinema.py --live

Only stdlib and ffprobe are required. Python 3.10+.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = os.environ.get("OPENFRAME_API_URL", "http://127.0.0.1:8001")
QA_DATA = Path(os.environ.get("OPENFRAME_QA_DATA", ROOT / "artifacts" / "qa-cinema"))
COMFY_URL = os.environ.get("OPENFRAME_COMFY_URL", "").strip()

PROMPT_VIDEO = (
    "A slow cinematic push through a rain-soaked alley at night. "
    "Teal and amber palette, soft key light from the left, warm practical lamps, "
    "deep shadows, fine film grain, coherent camera movement."
)
PROMPT_IMAGE = (
    "Editorial portrait of a ceramicist in a quiet studio. "
    "Color palette: teal and amber. Lighting: soft key light from the left, "
    "warm rim light on the shoulder, deep natural shadows, 85mm lens."
)
INGREDIENTS_LORA = "ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors"
INGREDIENTS_STRENGTH = 1.3
REFERENCE_GUIDE_WIDGETS = {"crop": "disabled", "use_tiled_encode": False,
                           "tile_size": 256, "tile_overlap": 64}


# --------------------------------------------------------------------------
# Declarative matrix
# --------------------------------------------------------------------------

@dataclass
class Expectation:
    outcome: str = "success"          # success | reject
    kind: str | None = None           # video | image
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    fps: float | None = None
    audio: bool | None = None
    count: int = 1
    error_any: tuple[str, ...] = ()
    graph_classes: tuple[str, ...] = ()
    references: int | None = None
    columns: int | None = None


@dataclass
class Case:
    ident: str
    title: str
    request: dict
    expect: Expectation
    graph: bool = True
    live: bool = True
    lifecycle: bool = False
    graph_assets: dict[str, str] = field(default_factory=dict)
    probes: list[dict] = field(default_factory=list)
    timeout_s: int = 1200
    required_models: tuple[str, ...] = ()


def video_request(effect: str, *, prompt: str = PROMPT_VIDEO, audio: bool = True,
                  frames: int = 49, width: int = 640, height: int = 352,
                  source: str | None = None, refs: list[str] | None = None,
                  seed: int = 20261030) -> dict:
    req = {
        "model_id": "ltx-2.5",
        "effect_id": effect,
        "provider": "local",
        "prompt": prompt,
        "negative_prompt": "",
        "seed": seed,
        "width": width,
        "height": height,
        "frames": frames,
        "fps": 24,
        "steps": 8,
        "guidance": 1,
        "generate_audio": audio,
        "preserve_audio": True,
        "batch_size": 1,
    }
    if source is not None:
        req["source_asset_id"] = source
    if refs is not None:
        req["reference_asset_ids"] = refs
    return req


def image_request(*, batch: int = 1, seed: int = 20261030) -> dict:
    return {
        "model_id": "flux3-klein",
        "effect_id": "create-image",
        "provider": "local",
        "prompt": PROMPT_IMAGE,
        "negative_prompt": "",
        "seed": seed,
        "width": 1024,
        "height": 1024,
        "frames": 1,
        "fps": 1,
        "steps": 16,
        "guidance": 1,
        "batch_size": batch,
    }


def reference_assets(count: int) -> dict[str, str]:
    return {f"reference_{index}": f"qa_ref_{index + 1}.png" for index in range(count)}


def reference_case(ident: str, count: int, *, audio: bool) -> Case:
    columns = 3 if count >= 3 else count
    noun = "reference" if count == 1 else "references"
    return Case(
        ident,
        f"Reference-to-video, {count} {noun} ({columns} column"
        f"{'' if columns == 1 else 's'}), audio {'on' if audio else 'off'}",
        video_request("reference-to-video", audio=audio,
                      refs=[f"@ref{index}" for index in range(count)]),
        Expectation(
            outcome="success", kind="video", width=640, height=352,
            frames=49, fps=24.0, audio=audio, count=1, references=count,
            columns=columns,
            graph_classes=("OpenFrameReferenceSheet", "RepeatImageBatch",
                           "LTXAddVideoICLoRAGuide", "LTXVCropGuides",
                           "OpenFrameSaveVideo")
                          + (("LTXVAudioVAEDecode",) if audio else ()),
        ),
        graph_assets=reference_assets(count),
        required_models=("ltx-2.5",),
    )


CASES: list[Case] = [
    Case(
        "01", "Text-to-video, audio on",
        video_request("text-to-video", audio=True),
        Expectation(outcome="success", kind="video", width=640, height=352,
                    frames=49, fps=24.0, audio=True, count=1,
                    graph_classes=("LTXVConditioning", "SamplerCustomAdvanced",
                                   "VAEDecodeTiled", "OpenFrameSaveVideo")),
        required_models=("ltx-2.5",),
    ),
    Case(
        "02", "Text-to-video, audio off",
        video_request("text-to-video", audio=False),
        Expectation(outcome="success", kind="video", width=640, height=352,
                    frames=49, fps=24.0, audio=False, count=1,
                    graph_classes=("SamplerCustomAdvanced", "OpenFrameSaveVideo")),
        required_models=("ltx-2.5",),
    ),
    Case(
        "03", "Image-to-video with one uploaded image",
        video_request("image-to-video", audio=True, source="@source"),
        Expectation(outcome="success", kind="video", width=640, height=352,
                    frames=49, fps=24.0, audio=True, count=1,
                    graph_classes=("LTXVImgToVideoInplace", "LTXVPreprocess",
                                   "OpenFrameSaveVideo")),
        graph_assets={"source": "qa_source_01.png"},
        required_models=("ltx-2.5",),
    ),
    reference_case("04", 1, audio=True),
    reference_case("05", 1, audio=False),
    reference_case("06", 3, audio=True),
    reference_case("07", 3, audio=False),
    reference_case("08", 9, audio=True),
    reference_case("09", 9, audio=False),
    Case(
        "10", "Reference-to-video with 10 references is rejected",
        video_request("reference-to-video", audio=True,
                      refs=[f"@ref{i}" for i in range(10)]),
        Expectation(outcome="reject", kind=None, references=10,
                    error_any=("at most 9", "one to nine", "maximum of 9",
                               "9 reference", "too many reference")),
        graph_assets=reference_assets(10),
        required_models=("ltx-2.5",),
    ),
    Case(
        "11", "Image-to-video with 2 references is rejected",
        video_request("image-to-video", audio=True, source="@source",
                      refs=["@ref1", "@ref2"]),
        Expectation(outcome="reject", kind=None,
                    error_any=("additional reference", "multiple reference",
                               "at most 1", "too many reference")),
        graph_assets={"source": "qa_source_01.png",
                      "reference_0": "qa_ref_2.png",
                      "reference_1": "qa_ref_3.png"},
        required_models=("ltx-2.5",),
    ),
    Case(
        "12", "Image generation with palette and lighting prompt controls",
        image_request(batch=1),
        Expectation(outcome="success", kind="image", width=1024, height=1024,
                    frames=1, fps=1.0, audio=None, count=1,
                    graph_classes=("OpenFrameFlux3Prompt", "OpenFrameSaveImage",
                                   "EmptyFlux2LatentImage")),
        required_models=("flux3-klein",),
    ),
    Case(
        "13", "Batch of 2 image variants",
        image_request(batch=2),
        Expectation(outcome="success", kind="image", width=1024, height=1024,
                    frames=1, fps=1.0, audio=None, count=2,
                    graph_classes=("OpenFrameFlux3Prompt", "OpenFrameSaveImage",
                                   "EmptyFlux2LatentImage")),
        required_models=("flux3-klein",),
    ),
    Case(
        "14", "Cancel queued/running job, retry, preserve history",
        video_request("text-to-video", audio=False, frames=241),
        Expectation(outcome="lifecycle", kind="video", width=640, height=352,
                    frames=241, fps=24.0, audio=False),
        graph=False, lifecycle=True, timeout_s=90, required_models=("ltx-2.5",),
    ),
    Case(
        "15", "Invalid prompt/model/effect combinations fail explicitly",
        video_request("text-to-video"),
        Expectation(outcome="reject", kind=None,
                    error_any=("describe the scene", "does not support the selected effect")),
        probes=[
            {"label": "empty prompt",
             "request": video_request("text-to-video", prompt="   "),
             "error_any": ("describe the scene", "describe the result")},
            {"label": "model/effect mismatch",
             "request": {"model_id": "flux3-klein", "effect_id": "text-to-video",
                         "provider": "local", "prompt": "x"},
             "error_any": ("does not support the selected effect",
                           "does not support the selected operation")},
            {"label": "unknown effect",
             "request": video_request("not-a-real-effect"),
             "error_any": ("does not support the selected effect",
                           "select a supported model and effect")},
        ],
        required_models=(),
    ),
]


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%H:%M:%S")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")
    print(message, flush=True)


def matches(text: str, needles: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    return any(needle.lower() in low for needle in needles)


def detail_text(value) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                loc = ".".join(str(part) for part in item.get("loc", []))
                parts.append(f"{loc}: {item.get('msg', item)}" if loc else str(item.get("msg", item)))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    if isinstance(value, (dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)[:140] or "asset"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def write_test_png(path: Path, width: int, height: int, index: int) -> None:
    """Owned synthetic test image; deterministic and visually distinct per index."""
    palette = [
        (18, 92, 120), (170, 78, 40), (52, 120, 70), (120, 70, 150),
        (190, 150, 30), (40, 90, 170), (160, 40, 80), (70, 140, 130),
        (110, 110, 110), (200, 100, 20),
    ]
    base = palette[index % len(palette)]
    accent = palette[(index + 3) % len(palette)]
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        for x in range(width):
            band = ((x // 32) + (y // 32) + index) % 3
            stripe = ((x + y + index * 17) % 64) < 8
            if stripe:
                color = accent
            elif band == 0:
                color = base
            elif band == 1:
                color = tuple(min(255, c + 28) for c in base)
            else:
                color = tuple(max(0, c - 24) for c in base)
            # A centered lighter block gives image-to-video a stable subject.
            if abs(x - width // 2) < width // 5 and abs(y - height // 2) < height // 4:
                color = tuple(min(255, c + 60) for c in color)
            raw.extend(color)
    payload = (b"\x89PNG\r\n\x1a\n" +
               png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
               png_chunk(b"IDAT", zlib.compress(bytes(raw), 6)) +
               png_chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


# --------------------------------------------------------------------------
# HTTP (stdlib)
# --------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status: int, detail, body: str = ""):
        self.status = status
        self.detail = detail
        self.body = body
        super().__init__(f"HTTP {status}: {detail_text(detail)}")


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urlparse.urljoin(self.base + "/", path.lstrip("/"))

    def request(self, method: str, path: str, payload=None, *, raw: bytes | None = None,
                headers: dict | None = None, timeout: int = 90):
        data = raw
        hdrs = dict(headers or {})
        if payload is not None:
            data = json.dumps(payload).encode()
            hdrs.setdefault("Content-Type", "application/json")
        req = urlrequest.Request(self._url(path), data=data, method=method, headers=hdrs)
        try:
            with urlrequest.urlopen(req, timeout=timeout) as response:
                body = response.read()
                if not body:
                    return {}
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {"raw": body.decode("utf-8", "replace")}
        except urlerror.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body)
                detail = parsed.get("detail", parsed)
            except json.JSONDecodeError:
                detail = body[:2000]
            raise ApiError(exc.code, detail, body) from exc
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            raise ApiError(0, f"API connection failed: {exc}") from exc

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, payload=None, **kwargs):
        return self.request("POST", path, payload=payload, **kwargs)

    def patch(self, path: str, payload=None, **kwargs):
        return self.request("PATCH", path, payload=payload, **kwargs)

    def upload(self, path: Path) -> dict:
        boundary = "----openframe-qa-" + uuid.uuid4().hex
        content_type = "image/png"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.request("POST", "/api/assets", raw=body, timeout=120, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        })

    def download(self, path: str, destination: Path) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlrequest.urlopen(self._url(path), timeout=600) as response:
                with destination.open("wb") as handle:
                    shutil.copyfileobj(response, handle, length=1024 * 1024)
        except urlerror.HTTPError as exc:
            raise ApiError(exc.code, exc.read().decode("utf-8", "replace")[:1000]) from exc
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            raise ApiError(0, f"Download failed: {exc}") from exc
        return destination.stat().st_size


# --------------------------------------------------------------------------
# ffprobe
# --------------------------------------------------------------------------

def ffprobe(path: Path) -> dict:
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-print_format", "json", str(path)],
        capture_output=True, text=True, timeout=120,
    )
    if process.returncode:
        raise RuntimeError((process.stderr or "ffprobe failed")[:1500])
    return json.loads(process.stdout)


def stream_fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        if value and value not in {"0/0", "0"}:
            try:
                return float(Fraction(value))
            except (ValueError, ZeroDivisionError):
                continue
    return 0.0


def media_summary(probe: dict) -> dict:
    streams = probe.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    fmt = probe.get("format", {})
    duration = 0.0
    if video:
        try:
            duration = float(video.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
    if not duration:
        try:
            duration = float(fmt.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
    if not duration and video:
        fps = stream_fps(video)
        frames = video.get("nb_frames")
        if fps and str(frames).isdigit():
            duration = int(frames) / fps
    return {
        "width": int(video.get("width", 0)) if video else None,
        "height": int(video.get("height", 0)) if video else None,
        "video_codec": video.get("codec_name") if video else None,
        "fps": stream_fps(video) if video else None,
        "duration": duration,
        "audio": [
            {"codec": item.get("codec_name"),
             "sample_rate": int(item.get("sample_rate", 0) or 0),
             "channels": int(item.get("channels", 0) or 0)}
            for item in audios
        ],
        "format": fmt.get("format_name"),
        "size": int(fmt.get("size", 0) or 0),
    }


# --------------------------------------------------------------------------
# Graph-only validation
# --------------------------------------------------------------------------

def iter_node_refs(value):
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
        yield value[0], value[1]


def dangling_refs(graph: dict) -> list[str]:
    problems = []
    for node_id, node in graph.items():
        for key, value in (node.get("inputs") or {}).items():
            for target, slot in iter_node_refs(value):
                if target not in graph:
                    problems.append(f"{node_id}.{key} -> missing node {target}[{slot}]")
    return problems


def graph_dimension_present(graph: dict, width: int, height: int) -> bool:
    for node in graph.values():
        if node.get("class_type") in {"EmptyLTXVLatentVideo", "ImageCrop",
                                      "EmptyFlux2LatentImage", "OpenFrameReferenceSheet"}:
            inputs = node.get("inputs", {})
            if inputs.get("width") == width and inputs.get("height") == height:
                return True
    return False


def check(checks: list, name: str, ok: bool, detail: str = "") -> bool:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def graph_assets_for(case: Case) -> dict:
    return dict(case.graph_assets)


def run_graph_case(case: Case, log_path: Path) -> dict:
    started = utcnow()
    checks: list[dict] = []
    observed: dict = {}
    status = "FAILED"
    reason = ""
    append_log(log_path, f"CASE {case.ident} {case.title}")
    append_log(log_path, f"request: {json.dumps(case.request, ensure_ascii=False)}")

    if not case.graph:
        append_log(log_path, "skipped: not a graph-buildable case (API lifecycle case)")
        return {
            "id": case.ident, "title": case.title, "status": "SKIPPED",
            "expected": asdict(case.expect), "checks": checks, "observed": observed,
            "reason": "Graph-only mode cannot exercise the queue/cancel/retry lifecycle; run --live.",
            "started_at": started, "finished_at": utcnow(),
        }

    from engine.workflows import build_workflow, normalize_request

    if case.probes:
        all_ok = True
        for probe in case.probes:
            label = probe["label"]
            try:
                normalized = normalize_request(probe["request"])
                build_workflow(normalized, {})
            except ValueError as exc:
                text = str(exc)
                ok = matches(text, probe["error_any"])
                append_log(log_path, f"probe {label!r} rejected: {text}")
                check(checks, f"probe:{label}", ok, text)
                all_ok = all_ok and ok
            else:
                append_log(log_path, f"probe {label!r} was ACCEPTED")
                check(checks, f"probe:{label}", False, "request was accepted")
                all_ok = False
        status = "PASSED" if all_ok else "FAILED"
        reason = "" if all_ok else "One or more invalid combinations were not rejected explicitly."
        return {
            "id": case.ident, "title": case.title, "status": status,
            "expected": asdict(case.expect), "checks": checks,
            "observed": {"probes": len(case.probes)}, "reason": reason,
            "started_at": started, "finished_at": utcnow(),
        }

    try:
        normalized = normalize_request(case.request)
        graph = build_workflow(normalized, graph_assets_for(case))
    except ValueError as exc:
        text = str(exc)
        append_log(log_path, f"build rejected: {text}")
        if case.expect.outcome == "reject":
            ok = matches(text, case.expect.error_any)
            check(checks, "explicit_rejection", ok, text)
            status = "PASSED" if ok else "FAILED"
            reason = "" if ok else f"Rejected with an unexpected message: {text}"
        else:
            check(checks, "build", False, text)
            reason = text
        return {
            "id": case.ident, "title": case.title, "status": status,
            "expected": asdict(case.expect), "checks": checks,
            "observed": {"error": text}, "reason": reason,
            "started_at": started, "finished_at": utcnow(),
        }

    if case.expect.outcome == "reject":
        check(checks, "explicit_rejection", False, "request was accepted and a graph was built")
        return {
            "id": case.ident, "title": case.title, "status": "FAILED",
            "expected": asdict(case.expect), "checks": checks,
            "observed": {"nodes": len(graph)}, "reason": "Expected rejection, but the request built a graph.",
            "started_at": started, "finished_at": utcnow(),
        }

    save_class = "OpenFrameSaveImage" if case.expect.kind == "image" else "OpenFrameSaveVideo"
    saves = [node for node in graph.values() if node.get("class_type") == save_class]
    check(checks, "final_save_node", len(saves) == 1,
          f"{len(saves)} x {save_class}")
    check(checks, "no_dangling_node_references", not dangling_refs(graph),
          "; ".join(dangling_refs(graph)))
    classes = {node.get("class_type") for node in graph.values()}
    for name in case.expect.graph_classes:
        check(checks, f"class:{name}", name in classes)

    if case.expect.width and case.expect.height:
        check(checks, "output_canvas",
              graph_dimension_present(graph, case.expect.width, case.expect.height),
              f"expected {case.expect.width}x{case.expect.height}")

    if case.expect.kind == "video":
        save = graph.get("save", {}).get("inputs", {})
        check(checks, "save_frames", save.get("frames") == case.expect.frames,
              f"save.frames={save.get('frames')} expected={case.expect.frames}")
        check(checks, "save_fps", float(save.get("fps", 0)) == float(case.expect.fps or 0),
              f"save.fps={save.get('fps')} expected={case.expect.fps}")
        audio_ref = save.get("audio")
        if case.expect.audio is True:
            ok = bool(audio_ref) and graph.get(audio_ref[0], {}).get("class_type") == "LTXVAudioVAEDecode"
            check(checks, "generated_audio_routing", ok, f"save.audio={audio_ref}")
        elif case.expect.audio is False:
            check(checks, "no_audio_routing", not audio_ref and "LTXVAudioVAEDecode" not in classes,
                  f"save.audio={audio_ref}")

    if case.expect.kind == "image":
        empty = graph.get("empty", {}).get("inputs", {})
        check(checks, "image_canvas",
              empty.get("width") == case.expect.width and empty.get("height") == case.expect.height,
              f"empty={empty.get('width')}x{empty.get('height')}")
        check(checks, "image_batch", empty.get("batch_size") == case.expect.count,
              f"batch_size={empty.get('batch_size')} expected={case.expect.count}")

    if case.request.get("effect_id") == "image-to-video" and case.graph_assets.get("source"):
        source_file = case.graph_assets["source"]
        loads = [n for n in graph.values() if n.get("class_type") == "LoadImage"]
        check(checks, "source_load",
              any(n["inputs"].get("image") == source_file for n in loads),
              f"{len(loads)} LoadImage nodes")
        check(checks, "source_not_counted_as_reference",
              not (normalized.get("reference_asset_ids") or normalized.get("reference_asset_id")),
              "one source accepted; no reference list")

    if case.expect.references is not None:
        count = case.expect.references
        expected_refs = case.request.get("reference_asset_ids", [])
        expected_files = [case.graph_assets[f"reference_{index}"] for index in range(count)]
        check(checks, "reference_count", len(expected_refs) == count,
              f"{len(expected_refs)} refs, expected {count}")
        check(checks, "ordered_reference_echo",
              normalized.get("reference_asset_ids") == expected_refs,
              f"{normalized.get('reference_asset_ids')}")
        loads = [n for n in graph.values() if n.get("class_type") == "LoadImage"]
        loaded_files = [n["inputs"].get("image") for n in loads]
        check(checks, "reference_load_order", loaded_files == expected_files,
              f"order={loaded_files}")
        sheet = graph.get("reference_sheet", {})
        sheet_inputs = sheet.get("inputs", {})
        check(checks, "reference_sheet", sheet.get("class_type") == "OpenFrameReferenceSheet")
        slots = sorted(key for key in sheet_inputs if key.startswith("image_"))
        check(checks, "reference_sheet_slots",
              slots == [f"image_{index + 1}" for index in range(count)],
              f"slots={slots}")
        check(checks, "reference_sheet_columns",
              sheet_inputs.get("columns") == case.expect.columns,
              f"columns={sheet_inputs.get('columns')} expected={case.expect.columns}")
        check(checks, "columns_policy",
              case.expect.columns == (3 if count >= 3 else count),
              f"{count} refs -> {case.expect.columns} columns")
        check(checks, "reference_sheet_canvas",
              sheet_inputs.get("width") == case.expect.width and
              sheet_inputs.get("height") == case.expect.height,
              f"{sheet_inputs.get('width')}x{sheet_inputs.get('height')}")
        ordered = []
        for index in range(1, count + 1):
            ref = sheet_inputs.get(f"image_{index}")
            node = graph.get(ref[0], {}) if ref else {}
            ordered.append(node.get("inputs", {}).get("image"))
        check(checks, "reference_sheet_order", ordered == expected_files,
              f"order={ordered}")
        adapter = graph.get("adapter", {}).get("inputs", {})
        check(checks, "ingredients_adapter",
              adapter.get("lora_name") == INGREDIENTS_LORA,
              f"{adapter.get('lora_name')}")
        check(checks, "ingredients_adapter_strength",
              adapter.get("strength_model") == INGREDIENTS_STRENGTH,
              f"strength={adapter.get('strength_model')} expected={INGREDIENTS_STRENGTH}")
        repeat = graph.get("repeat_reference_sheet", {})
        repeat_inputs = repeat.get("inputs", {})
        check(checks, "repeat_reference_sheet",
              repeat.get("class_type") == "RepeatImageBatch")
        check(checks, "repeat_input",
              repeat_inputs.get("image") == ["reference_sheet", 0],
              f"image={repeat_inputs.get('image')}")
        check(checks, "sheet_repeated_on_every_frame",
              repeat_inputs.get("amount") == case.expect.frames,
              f"amount={repeat_inputs.get('amount')} expected={case.expect.frames}")
        guide = graph.get("guide", {})
        guide_inputs = guide.get("inputs", {})
        check(checks, "guide_class",
              guide.get("class_type") == "LTXAddVideoICLoRAGuide")
        check(checks, "guide_image",
              guide_inputs.get("image") == ["repeat_reference_sheet", 0],
              f"image={guide_inputs.get('image')}")
        check(checks, "guide_latent_downscale",
              guide_inputs.get("latent_downscale_factor") == ["adapter", 1],
              f"{guide_inputs.get('latent_downscale_factor')}")
        for widget, expected in REFERENCE_GUIDE_WIDGETS.items():
            check(checks, f"guide_widget:{widget}",
                  guide_inputs.get(widget) == expected,
                  f"{widget}={guide_inputs.get(widget)} expected={expected}")
        check(checks, "crop_guides", "LTXVCropGuides" in classes)
        check(checks, "reference_guide_not_opening_frame",
              "LTXVImgToVideoInplace" not in classes)

    if case.expect.kind == "image":
        prompt_node = graph.get("prompt_caption", {}).get("inputs", {})
        request_text = str(prompt_node.get("request", ""))
        check(checks, "palette_in_prompt", "palette" in request_text.lower())
        check(checks, "lighting_in_prompt", "light" in request_text.lower())

    observed = {
        "nodes": len(graph),
        "classes": sorted(name for name in classes if name),
        "save": graph.get("save", {}).get("class_type"),
        "references": len(normalized.get("reference_asset_ids") or []),
        "audio_routed": bool(graph.get("save", {}).get("inputs", {}).get("audio")),
        "dimension_present": graph_dimension_present(graph, case.expect.width or 0,
                                                     case.expect.height or 0),
    }
    append_log(log_path, f"graph: {json.dumps(observed, ensure_ascii=False)}")
    ok = all(item["ok"] for item in checks)
    status = "PASSED" if ok else "FAILED"
    if not ok:
        reason = "; ".join(f"{item['name']}: {item['detail']}" for item in checks if not item["ok"])
    return {
        "id": case.ident, "title": case.title, "status": status,
        "expected": asdict(case.expect), "checks": checks,
        "observed": observed, "reason": reason,
        "started_at": started, "finished_at": utcnow(),
    }


# --------------------------------------------------------------------------
# Live execution
# --------------------------------------------------------------------------

class LiveBlocked(Exception):
    pass


def replace_assets(value, uploads: list[dict]):
    if isinstance(value, str):
        if value == "@source":
            return uploads[0]["id"]
        match = re.fullmatch(r"@ref(\d+)", value)
        if match:
            return uploads[int(match.group(1))]["id"]
        return value
    if isinstance(value, list):
        return [replace_assets(item, uploads) for item in value]
    if isinstance(value, dict):
        return {key: replace_assets(item, uploads) for key, item in value.items()}
    return value


def poll_job(api: Api, job_id: str, timeout_s: int, log_path: Path) -> dict:
    deadline = time.monotonic() + timeout_s
    last = None
    while True:
        job = api.get(f"/api/jobs/{job_id}")
        state = (job.get("status"), round(float(job.get("progress", 0)) * 100), job.get("stage"))
        if state != last:
            append_log(log_path, f"job {job_id}: {state[0]} {state[1]}% — {state[2]}")
            last = state
        if job.get("status") in {"succeeded", "failed", "cancelled"}:
            return job
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Job {job_id} did not finish within {timeout_s}s "
                f"(last: {job.get('status')} {job.get('stage')})"
            )
        time.sleep(2)


def app_job_path(document_id: str) -> str:
    return f"/api/apps/cinema-studio/documents/{document_id}/jobs"


def submit_app_job(api: Api, document: dict, request: dict, operation: str,
                   step_id: str, log_path: Path) -> dict:
    body = {
        "expected_revision": document["revision"],
        "operation": operation,
        "request": request,
        "step_id": step_id,
        "group_id": f"qa-{step_id}",
    }
    append_log(log_path, f"submit app job operation={operation} path={app_job_path(document['id'])}")
    try:
        job = api.post(app_job_path(document["id"]), body)
    except ApiError as exc:
        append_log(log_path, f"submit rejected HTTP {exc.status}: {detail_text(exc.detail)}")
        raise
    append_log(log_path, f"job accepted: {job.get('id')} status={job.get('status')}")
    return job


def download_and_validate(api: Api, case: Case, job: dict, run_dir: Path,
                          log_path: Path, checks: list[dict]) -> dict:
    media_dir = run_dir / "media" / case.ident
    outputs = [item for item in job.get("outputs", [])
               if item.get("role", "result") == "result" and item.get("kind") == case.expect.kind]
    check(checks, "result_output_count", len(outputs) == case.expect.count,
          f"{len(outputs)} {case.expect.kind} result(s), expected {case.expect.count}")
    summaries = []
    for position, asset in enumerate(outputs):
        name = safe_name(f"{position + 1}-{asset.get('name', asset['id'])}")
        destination = media_dir / name
        size = api.download(asset["url"], destination)
        digest = sha256_file(destination)
        check(checks, f"download_integrity:{position + 1}",
              size > 0 and (not asset.get("sha256") or digest == asset["sha256"]),
              f"{size} bytes sha256={digest[:16]} expected={str(asset.get('sha256'))[:16]}")
        probe = ffprobe(destination)
        write_json(media_dir / f"{name}.ffprobe.json", probe)
        summary = media_summary(probe)
        summary.update(asset_id=asset["id"], file=str(destination),
                       sha256=digest, size=size)
        summaries.append(summary)
        append_log(log_path, f"media {position + 1}: {json.dumps(summary, ensure_ascii=False)}")
        if case.expect.kind == "image":
            check(checks, f"image_dimensions:{position + 1}",
                  summary["width"] == case.expect.width and summary["height"] == case.expect.height,
                  f"{summary['width']}x{summary['height']}")
        else:
            check(checks, f"video_dimensions:{position + 1}",
                  summary["width"] == case.expect.width and summary["height"] == case.expect.height,
                  f"{summary['width']}x{summary['height']}")
            check(checks, f"video_fps:{position + 1}",
                  abs((summary["fps"] or 0) - float(case.expect.fps or 0)) <= 0.05,
                  f"fps={summary['fps']} expected={case.expect.fps}")
            expected_duration = (case.expect.frames or 0) / float(case.expect.fps or 1)
            tolerance = max(0.12, 2.0 / float(case.expect.fps or 1))
            check(checks, f"video_duration:{position + 1}",
                  abs(summary["duration"] - expected_duration) <= tolerance,
                  f"duration={summary['duration']:.4f}s expected≈{expected_duration:.4f}s")
            has_audio = bool(summary["audio"])
            if case.expect.audio is True:
                check(checks, f"audio_stream:{position + 1}", has_audio,
                      f"audio={summary['audio']}")
                check(checks, f"audio_codec:{position + 1}",
                      has_audio and bool(summary["audio"][0].get("codec")),
                      f"codec={summary['audio'][0].get('codec') if has_audio else None}")
            elif case.expect.audio is False:
                check(checks, f"no_audio_stream:{position + 1}", not has_audio,
                      f"audio={summary['audio']}")
    return {"outputs": summaries}


def validate_live_success(api: Api, case: Case, job: dict, run_dir: Path,
                          log_path: Path) -> tuple[list[dict], dict]:
    checks: list[dict] = []
    observed: dict = {"job_id": job.get("id"), "status": job.get("status")}
    check(checks, "job_succeeded", job.get("status") == "succeeded",
          f"status={job.get('status')} error={job.get('error')}")
    if job.get("status") != "succeeded":
        return checks, observed
    request_echo = job.get("request", {})
    uploads = observed.get("_uploads", [])
    if case.request.get("effect_id") == "image-to-video" and case.request.get("source_asset_id"):
        expected_source = replace_assets(case.request["source_asset_id"], uploads)
        check(checks, "single_source_echo",
              request_echo.get("source_asset_id") == expected_source
              and not request_echo.get("reference_asset_ids"),
              f"source={request_echo.get('source_asset_id')} refs={request_echo.get('reference_asset_ids')}")
    if case.expect.references is not None:
        count = case.expect.references
        expected_refs = replace_assets(case.request.get("reference_asset_ids", []), uploads)
        actual_refs = request_echo.get("reference_asset_ids") or []
        check(checks, "ordered_reference_echo", actual_refs == expected_refs,
              f"request refs={actual_refs}")
        metadata = (job.get("metadata") or {}).get("reference_sheet") or {}
        check(checks, "reference_sheet_metadata", bool(metadata),
              f"metadata={metadata}")
        if metadata:
            check(checks, "reference_sheet_count",
                  metadata.get("reference_count") == count,
                  f"count={metadata.get('reference_count')} expected={count}")
            check(checks, "reference_sheet_order",
                  metadata.get("reference_asset_ids") == expected_refs,
                  f"metadata refs={metadata.get('reference_asset_ids')}")
            check(checks, "reference_sheet_columns",
                  metadata.get("columns") == case.expect.columns,
                  f"columns={metadata.get('columns')} expected={case.expect.columns}")
            check(checks, "ingredients_adapter",
                  metadata.get("adapter") == INGREDIENTS_LORA,
                  f"adapter={metadata.get('adapter')}")
            check(checks, "ingredients_adapter_strength",
                  metadata.get("adapter_strength") == INGREDIENTS_STRENGTH,
                  f"strength={metadata.get('adapter_strength')}")
            expected_audio = "generated native audio" if case.expect.audio else "silent"
            check(checks, "reference_audio_policy",
                  metadata.get("audio_policy") == expected_audio,
                  f"audio_policy={metadata.get('audio_policy')} expected={expected_audio}")

    if case.expect.kind == "image":
        prompt = str(request_echo.get("prompt", "")).lower()
        check(checks, "palette_in_request_prompt", "palette" in prompt)
        check(checks, "lighting_in_request_prompt", "light" in prompt)
        check(checks, "batch_echo", request_echo.get("batch_size") == case.expect.count,
              f"batch_size={request_echo.get('batch_size')}")

    # Persist the executed/exported graph as evidence.
    try:
        workflow = api.get(f"/api/jobs/{job['id']}/workflow")
    except ApiError as exc:
        check(checks, "workflow_export", False, f"HTTP {exc.status}: {detail_text(exc.detail)}")
    else:
        write_json(run_dir / "cases" / case.ident / "workflow.json", workflow)
        check(checks, "workflow_export", isinstance(workflow, dict) and bool(workflow),
              f"{len(workflow) if isinstance(workflow, dict) else 0} nodes")
        if case.expect.references is not None and isinstance(workflow, dict):
            count = case.expect.references
            sheet = workflow.get("reference_sheet", {})
            sheet_inputs = sheet.get("inputs", {})
            check(checks, "workflow_reference_sheet",
                  sheet.get("class_type") == "OpenFrameReferenceSheet" and
                  bool(sheet_inputs.get(f"image_{count}")) and
                  sheet_inputs.get("columns") == case.expect.columns,
                  f"sheet columns={sheet_inputs.get('columns')} nodes={list(sheet_inputs)}")
            repeat = workflow.get("repeat_reference_sheet", {}).get("inputs", {})
            check(checks, "workflow_repeat_amount",
                  repeat.get("amount") == case.expect.frames,
                  f"amount={repeat.get('amount')} expected={case.expect.frames}")
            guide = workflow.get("guide", {}).get("inputs", {})
            check(checks, "workflow_guide_widgets",
                  guide.get("crop") == "disabled" and guide.get("use_tiled_encode") is False,
                  f"crop={guide.get('crop')} use_tiled_encode={guide.get('use_tiled_encode')}")
            adapter = workflow.get("adapter", {}).get("inputs", {})
            check(checks, "workflow_adapter_strength",
                  adapter.get("strength_model") == INGREDIENTS_STRENGTH,
                  f"strength={adapter.get('strength_model')}")
            check(checks, "workflow_crop_guides",
                  "LTXVCropGuides" in {node.get("class_type") for node in workflow.values()
                                       if isinstance(node, dict)})

    media = download_and_validate(api, case, job, run_dir, log_path, checks)
    observed.update(media)
    return checks, observed


def run_live_case(case: Case, ctx: dict, run_dir: Path) -> dict:
    started = utcnow()
    log_path = run_dir / "cases" / f"{case.ident}.log"
    checks: list[dict] = []
    observed: dict = {}
    status = "FAILED"
    reason = ""
    append_log(log_path, f"CASE {case.ident} {case.title}")
    append_log(log_path, f"request template: {json.dumps(case.request, ensure_ascii=False)}")

    api: Api = ctx["api"]
    uploads: list[dict] = ctx["uploads"]
    document: dict | None = ctx["document"]
    catalog_effects = ctx["catalog_effects"]
    app_operations = ctx["app_operations"]

    if case.lifecycle:
        if document is None:
            return blocked_result(case, checks, "No QA Cinema document could be created.", started)
        request = replace_assets(case.request, uploads)
        try:
            job = submit_app_job(api, document, request, case.request.get("effect_id", "text-to-video"),
                                 "qa-cancel", log_path)
        except ApiError as exc:
            return blocked_result(case, checks,
                                  f"Could not queue cancel/retry probe: HTTP {exc.status} {detail_text(exc.detail)}",
                                  started)
        job_id = job["id"]
        observed["job_id"] = job_id
        try:
            cancelled = api.post(f"/api/jobs/{job_id}/cancel")
        except ApiError as exc:
            cancelled = {"error": f"HTTP {exc.status}: {detail_text(exc.detail)}"}
        append_log(log_path, f"cancel response: {json.dumps(cancelled, ensure_ascii=False)}")
        try:
            final = poll_job(api, job_id, case.timeout_s, log_path)
        except TimeoutError as exc:
            check(checks, "cancel_to_terminal", False, str(exc))
            return failed_result(case, checks, observed, str(exc), started)
        observed["final_status"] = final.get("status")
        cancel_ok = final.get("status") == "cancelled"
        check(checks, "cancel_to_terminal", cancel_ok,
              f"final={final.get('status')} error={final.get('error')}")

        retry_id = None
        retry_ok = False
        history_ok = False
        try:
            replacement = api.post(f"/api/jobs/{job_id}/retry")
            retry_id = replacement.get("id")
            retry_ok = bool(retry_id and retry_id != job_id)
            append_log(log_path, f"retry created: {retry_id}")
            if retry_id:
                try:
                    api.post(f"/api/jobs/{retry_id}/cancel")
                except ApiError:
                    pass
        except ApiError as exc:
            append_log(log_path, f"retry rejected: HTTP {exc.status} {detail_text(exc.detail)}")
        check(checks, "retry_created_new_job", retry_ok,
              f"original={job_id} retry={retry_id}")

        try:
            original_now = api.get(f"/api/jobs/{job_id}")
            history = api.get(f"/api/apps/cinema-studio/jobs?document_id={document['id']}&limit=100")
            ids = {item.get("id") for item in history.get("items", [])}
            history_ok = (job_id in ids and original_now.get("status") == final.get("status")
                          and (retry_id in ids if retry_id else True))
            check(checks, "history_preserved", history_ok,
                  f"original still present={job_id in ids}, retry present={retry_id in ids if retry_id else None}")
        except ApiError as exc:
            check(checks, "history_preserved", False, f"HTTP {exc.status}: {detail_text(exc.detail)}")
        observed.update(retry_id=retry_id)

        if cancel_ok and retry_ok and history_ok:
            status = "PASSED"
        elif not cancel_ok and final.get("status") == "failed" and final.get("error"):
            status = "BLOCKED"
            reason = ("Provider unavailable before cancellation could be observed: "
                      + str(final.get("error"))[:700])
        else:
            status = "FAILED"
            reason = "; ".join(f"{item['name']}: {item['detail']}" for item in checks if not item["ok"])
        return {
            "id": case.ident, "title": case.title, "status": status,
            "expected": asdict(case.expect), "checks": checks, "observed": observed,
            "reason": reason, "started_at": started, "finished_at": utcnow(),
        }

    if case.probes:
        all_ok = True
        for probe in case.probes:
            label = probe["label"]
            request = replace_assets(probe["request"], uploads)
            try:
                job = api.post("/api/jobs", request)
            except ApiError as exc:
                ok = exc.status == 422 and matches(detail_text(exc.detail), probe["error_any"])
                append_log(log_path, f"probe {label}: HTTP {exc.status} {detail_text(exc.detail)}")
                check(checks, f"probe:{label}", ok,
                      f"HTTP {exc.status}: {detail_text(exc.detail)}")
                all_ok = all_ok and ok
            else:
                append_log(log_path, f"probe {label}: ACCEPTED job {job.get('id')}")
                try:
                    api.post(f"/api/jobs/{job['id']}/cancel")
                except ApiError:
                    pass
                check(checks, f"probe:{label}", False, "request was accepted")
                all_ok = False
        status = "PASSED" if all_ok else "FAILED"
        reason = "" if all_ok else "One or more invalid combinations were not rejected explicitly."
        return {
            "id": case.ident, "title": case.title, "status": status,
            "expected": asdict(case.expect), "checks": checks,
            "observed": {"probes": len(case.probes)}, "reason": reason,
            "started_at": started, "finished_at": utcnow(),
        }

    effect_id = case.request.get("effect_id")
    request = replace_assets(case.request, uploads)
    observed["request"] = request

    # Rejection cases only need the running API to know the effect.
    if case.expect.outcome == "reject":
        if effect_id not in catalog_effects:
            return blocked_result(
                case, checks,
                f"Running API catalog does not expose effect '{effect_id}'. "
                f"Current effects: {sorted(catalog_effects)}", started)
        path = "/api/jobs"
        if effect_id in app_operations and document is not None:
            try:
                job = submit_app_job(api, document, request, effect_id,
                                     f"qa-{case.ident}", log_path)
            except ApiError as exc:
                ok = exc.status == 422 and matches(detail_text(exc.detail), case.expect.error_any)
                check(checks, "explicit_rejection", ok,
                      f"HTTP {exc.status}: {detail_text(exc.detail)}")
                status = "PASSED" if ok else "FAILED"
                reason = "" if ok else f"Unexpected rejection: {detail_text(exc.detail)}"
                return {
                    "id": case.ident, "title": case.title, "status": status,
                    "expected": asdict(case.expect), "checks": checks,
                    "observed": observed, "reason": reason,
                    "started_at": started, "finished_at": utcnow(),
                }
            else:
                try:
                    api.post(f"/api/jobs/{job['id']}/cancel")
                except ApiError:
                    pass
                check(checks, "explicit_rejection", False, "request was accepted")
                return {
                    "id": case.ident, "title": case.title, "status": "FAILED",
                    "expected": asdict(case.expect), "checks": checks,
                    "observed": observed, "reason": "Expected rejection, but a job was created.",
                    "started_at": started, "finished_at": utcnow(),
                }
        try:
            job = api.post(path, request)
        except ApiError as exc:
            ok = exc.status == 422 and matches(detail_text(exc.detail), case.expect.error_any)
            append_log(log_path, f"rejected via {path}: HTTP {exc.status} {detail_text(exc.detail)}")
            check(checks, "explicit_rejection", ok,
                  f"HTTP {exc.status}: {detail_text(exc.detail)}")
            status = "PASSED" if ok else "FAILED"
            reason = "" if ok else f"Unexpected rejection: {detail_text(exc.detail)}"
        else:
            append_log(log_path, f"ACCEPTED via {path}: {job.get('id')}")
            try:
                api.post(f"/api/jobs/{job['id']}/cancel")
            except ApiError:
                pass
            check(checks, "explicit_rejection", False, "request was accepted")
            reason = "Expected rejection, but a job was created."
        return {
            "id": case.ident, "title": case.title, "status": status,
            "expected": asdict(case.expect), "checks": checks,
            "observed": observed, "reason": reason,
            "started_at": started, "finished_at": utcnow(),
        }

    # Success cases need a real provider, model and Cinema operation.
    blockers = list(ctx["render_blockers"])
    if effect_id not in catalog_effects:
        blockers.append(f"effect '{effect_id}' is not exposed by the running API catalog")
    if effect_id not in app_operations:
        blockers.append(f"Cinema Studio app operations do not include '{effect_id}'")
    if ctx["provider_available"]:
        installed = set(ctx["provider_check"].get("models") or [])
        missing = [model for model in case.required_models if model not in installed]
        if missing:
            blockers.append(f"provider does not report installed model(s): {', '.join(missing)}")
    if document is None:
        blockers.append("no QA Cinema document was created")
    if blockers:
        return blocked_result(case, checks, "; ".join(blockers), started)

    try:
        job = submit_app_job(api, document, request, effect_id, f"qa-{case.ident}", log_path)
    except ApiError as exc:
        return failed_result(case, checks, observed,
                             f"Submission failed HTTP {exc.status}: {detail_text(exc.detail)}", started)
    observed["job_id"] = job["id"]
    write_json(run_dir / "cases" / case.ident / "job.submitted.json", job)
    try:
        final = poll_job(api, job["id"], case.timeout_s, log_path)
    except TimeoutError as exc:
        return failed_result(case, checks, observed, str(exc), started)
    write_json(run_dir / "cases" / case.ident / "job.json", final)
    observed["final_status"] = final.get("status")

    # Give validate_live_success access to upload ids for echo checks.
    observed["_uploads"] = uploads
    checks, media = validate_live_success(api, case, final, run_dir, log_path)
    observed.pop("_uploads", None)
    observed.update(media)
    ok = all(item["ok"] for item in checks)
    status = "PASSED" if ok else "FAILED"
    if not ok:
        reason = "; ".join(f"{item['name']}: {item['detail']}" for item in checks if not item["ok"])
    return {
        "id": case.ident, "title": case.title, "status": status,
        "expected": asdict(case.expect), "checks": checks, "observed": observed,
        "reason": reason, "started_at": started, "finished_at": utcnow(),
    }


def blocked_result(case: Case, checks: list[dict], reason: str, started: str) -> dict:
    checks.append({"name": "precondition", "ok": False, "detail": reason})
    return {
        "id": case.ident, "title": case.title, "status": "BLOCKED",
        "expected": asdict(case.expect), "checks": checks, "observed": {},
        "reason": reason, "started_at": started, "finished_at": utcnow(),
    }


def failed_result(case: Case, checks: list[dict], observed: dict, reason: str,
                  started: str) -> dict:
    checks.append({"name": "execution", "ok": False, "detail": reason})
    return {
        "id": case.ident, "title": case.title, "status": "FAILED",
        "expected": asdict(case.expect), "checks": checks, "observed": observed,
        "reason": reason, "started_at": started, "finished_at": utcnow(),
    }


# --------------------------------------------------------------------------
# Live preflight
# --------------------------------------------------------------------------

def live_preflight(api: Api, args, run_dir: Path) -> dict:
    log_path = run_dir / "cases" / "00-preflight.log"
    env: dict = {"api_url": api.base, "comfy_url_env": COMFY_URL or None}
    append_log(log_path, f"API {api.base}")
    health = api.get("/api/health")
    env["health"] = health
    append_log(log_path, f"health: {json.dumps(health, ensure_ascii=False)}")
    catalog = api.get("/api/catalog")
    apps = api.get("/api/apps")
    settings = api.get("/api/settings")
    env["settings"] = {key: settings.get(key) for key in
                       ("default_provider", "comfy_url", "comfy_cloud_url")}
    env["settings"]["cloud_auth_mode"] = (settings.get("comfy_cloud_auth") or {}).get("mode")
    effects = {item["id"]: item for item in catalog.get("effects", [])}
    models = {item["id"]: item for item in catalog.get("models", [])}
    cinema = next((item for item in apps.get("items", [])
                   if item.get("id") == "cinema-studio"), None)
    operations = {item["id"]: item for item in (cinema or {}).get("operations", [])}
    env["catalog_effects"] = sorted(effects)
    env["cinema_operations"] = sorted(operations)
    append_log(log_path, f"effects: {sorted(effects)}")
    append_log(log_path, f"cinema operations: {sorted(operations)}")

    if COMFY_URL and settings.get("comfy_url") != COMFY_URL:
        if args.apply_provider_url:
            api.patch("/api/settings", {"comfy_url": COMFY_URL})
            settings = api.get("/api/settings")
            env["settings"]["comfy_url"] = settings.get("comfy_url")
            append_log(log_path, f"applied comfy_url={COMFY_URL}")
        else:
            env["provider_url_warning"] = (
                f"API comfy_url={settings.get('comfy_url')} does not match "
                f"OPENFRAME_COMFY_URL={COMFY_URL}; pass --apply-provider-url to update it."
            )
            append_log(log_path, env["provider_url_warning"])

    provider = args.provider
    if provider == "comfy-cloud" and not args.allow_cloud:
        raise SystemExit("Refusing --provider comfy-cloud without --allow-cloud (avoids spending credits).")
    try:
        provider_check = api.post(f"/api/providers/{provider}/check")
    except ApiError as exc:
        provider_check = {"available": False, "detail": f"HTTP {exc.status}: {detail_text(exc.detail)}"}
    env["provider_check"] = provider_check
    append_log(log_path, f"provider {provider}: {json.dumps(provider_check, ensure_ascii=False)[:2000]}")
    provider_available = provider_check.get("available") is True
    render_blockers: list[str] = []
    if not provider_available:
        render_blockers.append(
            f"provider '{provider}' is not available: {provider_check.get('detail', 'no detail')}")
    if env.get("provider_url_warning"):
        render_blockers.append(env["provider_url_warning"])

    # Owned test images, never private user media. Upload in numeric order so
    # @ref0..@ref8 map to qa_ref_1..qa_ref_9 for the 1/3/9-reference matrix.
    uploads = []
    inputs_dir = run_dir / "inputs"
    for index in range(10):
        path = inputs_dir / f"qa_ref_{index + 1}.png"
        write_test_png(path, 512, 512, index)
    for index in range(10):
        path = inputs_dir / f"qa_ref_{index + 1}.png"
        try:
            asset = api.upload(path)
        except ApiError as exc:
            env["upload_error"] = f"{path.name}: HTTP {exc.status} {detail_text(exc.detail)}"
            append_log(log_path, env["upload_error"])
            break
        uploads.append({"id": asset["id"], "name": asset.get("name"), "sha256": asset.get("sha256"),
                        "local": str(path)})
        append_log(log_path, f"uploaded {path.name} -> {asset['id']}")

    document = None
    if len(uploads) == 10:
        body = {
            "title": f"QA Cinema harness {run_dir.name}",
            "schema_version": 1,
            "state": {"mode": "video", "prompt": "Automated QA project; owned synthetic inputs only.",
                      "reference_asset_ids": []},
            "asset_ids": [item["id"] for item in uploads],
        }
        try:
            document = api.post("/api/apps/cinema-studio/documents", body)
            env["document"] = {"id": document["id"], "title": document["title"],
                               "revision": document["revision"]}
            append_log(log_path, f"QA document: {document['id']} ({document['title']})")
        except ApiError as exc:
            env["document_error"] = f"HTTP {exc.status}: {detail_text(exc.detail)}"
            append_log(log_path, env["document_error"])
    else:
        env["document_error"] = "Test image upload incomplete; no QA document created."

    env.update({
        "provider": provider,
        "provider_available": provider_available,
        "render_blockers": render_blockers,
        "uploads": uploads,
        "isolation": (
            "Dedicated Cinema Studio document; existing projects untouched. "
            "The running API was not restarted, so OPENFRAME_DATA_DIR isolation was not applied."
        ),
    })
    return {
        "environment": env,
        "effects": effects,
        "models": models,
        "operations": operations,
        "document": document,
        "uploads": uploads,
        "provider_check": provider_check,
        "provider_available": provider_available,
        "render_blockers": render_blockers,
        "log_path": log_path,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def repo_snapshot() -> dict:
    def run(args):
        try:
            return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {
        "commit": run(["git", "rev-parse", "HEAD"]),
        "dirty": run(["git", "status", "--porcelain"]).splitlines(),
        "engine_files": {
            name: sha256_file(ROOT / name)
            for name in ("engine/catalog.py", "engine/workflows.py", "engine/ltx25_workflows.py",
                         "backend/app.py", "backend/apps.py")
            if (ROOT / name).is_file()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--graphs-only", action="store_true",
                      help="Build and validate the matrix graphs without a GPU/API.")
    mode.add_argument("--live", action="store_true",
                      help="Submit, poll, download and probe real jobs through the API.")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--provider", default=os.environ.get("OPENFRAME_PROVIDER", "local"),
                        choices=["local", "comfy-cloud"])
    parser.add_argument("--allow-cloud", action="store_true",
                        help="Explicitly allow comfy-cloud execution (may spend credits).")
    parser.add_argument("--apply-provider-url", action="store_true",
                        help="PATCH the API comfy_url to OPENFRAME_COMFY_URL when they differ.")
    parser.add_argument("--out", type=Path, default=QA_DATA)
    parser.add_argument("--case", action="append", default=[],
                        help="Run only the given case id (repeatable).")
    parser.add_argument("--timeout", type=int, default=0,
                        help="Override per-case timeout seconds.")
    args = parser.parse_args()
    if not args.live:
        args.graphs_only = True

    selected = [case for case in CASES if not args.case or case.ident in set(args.case)]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out / run_id
    suffix = 2
    while run_dir.exists():
        run_dir = args.out / f"{run_id}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.timeout:
        for case in selected:
            case.timeout_s = args.timeout

    mode_name = "live" if args.live else "graphs-only"
    write_json(run_dir / "matrix.json", {
        "mode": mode_name,
        "generated_at": utcnow(),
        "cases": [
            {"id": case.ident, "title": case.title, "request": case.request,
             "expect": asdict(case.expect), "graph": case.graph,
             "probes": case.probes, "timeout_s": case.timeout_s}
            for case in selected
        ],
    })
    write_json(run_dir / "source.json", repo_snapshot())

    results = []
    preflight = None
    if args.live:
        api = Api(args.api_url)
        try:
            preflight = live_preflight(api, args, run_dir)
        except (ApiError, SystemExit) as exc:
            message = str(exc)
            append_log(run_dir / "cases" / "00-preflight.log", f"FATAL: {message}")
            results = [blocked_result(case, [], f"Live preflight failed: {message}", utcnow())
                       for case in selected]
            write_json(run_dir / "results.json", {
                "schema": 1, "mode": mode_name, "harness": "scripts/qa_cinema.py",
                "started_at": utcnow(), "finished_at": utcnow(),
                "api_url": args.api_url, "environment": {"preflight_error": message},
                "summary": summarize(results), "cases": results,
            })
            print(f"Live preflight failed: {message}", file=sys.stderr)
            return 2

        ctx = {
            "api": api,
            "uploads": preflight["uploads"],
            "document": preflight["document"],
            "catalog_effects": preflight["effects"],
            "app_operations": preflight["operations"],
            "provider_check": preflight["provider_check"],
            "provider_available": preflight["provider_available"],
            "render_blockers": preflight["render_blockers"],
        }
        for case in selected:
            if not case.live:
                results.append({
                    "id": case.ident, "title": case.title, "status": "SKIPPED",
                    "expected": asdict(case.expect), "checks": [], "observed": {},
                    "reason": "Case is not applicable to live mode.", "started_at": utcnow(),
                    "finished_at": utcnow(),
                })
                continue
            result = run_live_case(case, ctx, run_dir)
            results.append(result)
            write_json(run_dir / "results.json", {
                "schema": 1, "mode": mode_name, "harness": "scripts/qa_cinema.py",
                "started_at": results[0]["started_at"], "finished_at": utcnow(),
                "api_url": args.api_url, "environment": preflight["environment"],
                "summary": summarize(results), "cases": results,
            })
    else:
        for case in selected:
            result = run_graph_case(case, run_dir / "cases" / f"{case.ident}.log")
            results.append(result)
            write_json(run_dir / "results.json", {
                "schema": 1, "mode": mode_name, "harness": "scripts/qa_cinema.py",
                "started_at": results[0]["started_at"], "finished_at": utcnow(),
                "api_url": None, "environment": {"source": repo_snapshot()},
                "summary": summarize(results), "cases": results,
            })

    summary = summarize(results)
    final = {
        "schema": 1, "mode": mode_name, "harness": "scripts/qa_cinema.py",
        "started_at": results[0]["started_at"] if results else utcnow(),
        "finished_at": utcnow(), "api_url": args.api_url if args.live else None,
        "environment": (preflight["environment"] if preflight else {"source": repo_snapshot()}),
        "summary": summary, "cases": results,
    }
    write_json(run_dir / "results.json", final)
    print(f"\n{summary['passed']} passed, {summary['failed']} failed, "
          f"{summary['blocked']} blocked, {summary['skipped']} skipped")
    print(f"Evidence: {run_dir}")
    return 1 if summary["failed"] else 0


def summarize(results: list[dict]) -> dict:
    counts = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0}
    for item in results:
        key = item["status"].lower()
        if key in counts:
            counts[key] += 1
    counts["total"] = len(results)
    return counts


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
