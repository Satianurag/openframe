"""Hosted Comfy Cloud diffusion with explicit, shared CPU media processing.

API keys use the official SDK. An existing CLI OAuth session can alternatively
submit to the same hosted GPU service; neither route calls partner model APIs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

import httpx

from .workflows import build_workflow

HOSTED_URL = "https://cloud.comfy.org"
_AUTH_CACHE = {}
_SDK_LOCK = threading.Lock()


def find_cli(settings):
    explicit = settings.get("comfy_cli_path") or os.environ.get("OPENFRAME_COMFY_CLI_PATH")
    candidates = [explicit] if explicit else [shutil.which("comfy"),
        Path.home() / ".local/bin/comfy",
        Path.home() / ".local/share/uv/tools/comfy-cli/bin/comfy",
        Path.home() / ".local/share/uv/tools/comfy-mcp/bin/comfy"]
    return next((str(Path(p).expanduser().resolve()) for p in candidates
                 if p and Path(p).expanduser().is_file() and os.access(Path(p).expanduser(), os.X_OK)), None)


def _cli(settings, args, timeout=120, cancel=None):
    from .runner import ProviderError
    command = find_cli(settings)
    if not command:
        raise ProviderError("Install comfy-cli or set its executable path, then run `comfy cloud login` on the app server.")
    env = dict(os.environ, COMFY_CLOUD_BASE_URL=HOSTED_URL, COMFY_CLI_NO_REMOTE_REFRESH="1")
    try:
        process = subprocess.Popen([command, "--json", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        started = time.monotonic()
        try:
            while True:
                if cancel:
                    cancel()
                try:
                    stdout, _ = process.communicate(timeout=min(.5, max(.01, timeout - (time.monotonic() - started))))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= timeout:
                        raise
        except BaseException:
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate()
            raise
        payload = json.loads(stdout)
    except subprocess.TimeoutExpired as exc:
        raise ProviderError("Comfy CLI timed out. If submitting, inspect `comfy jobs ls --where cloud` before retrying; the request may have been accepted.") from exc
    except (OSError, ValueError) as exc:
        raise ProviderError("Comfy CLI returned an unreadable response; require comfy-cli 1.23 or newer.") from exc
    if process.returncode or not payload.get("ok"):
        error = payload.get("error") or {}
        raise ProviderError("Comfy Cloud: " + str(error.get("message", error.get("code", "CLI request failed")))[:1200])
    return payload.get("data") or {}


def auth_status(settings, refresh=False):
    """Return booleans only. The CLI's session and token fields never enter app state."""
    key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
    cli = find_cli(settings)
    if key:
        return {"mode": "api-key", "cli_installed": bool(cli), "cli_signed_in": False}
    cache_key = (cli, settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/"))
    cached = _AUTH_CACHE.get(cache_key)
    if cached and not refresh and time.monotonic() - cached[0] < 30:
        return dict(cached[1])
    signed_in = False
    if cli and settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/") == HOSTED_URL:
        try:
            status = _cli(settings, ["cloud", "whoami"], timeout=20)
            signed_in = bool(status.get("signed_in") and status.get("base_url", "").rstrip("/") == HOSTED_URL)
        except Exception:
            pass
    result = {"mode": "cli-oauth" if signed_in else "missing", "cli_installed": bool(cli), "cli_signed_in": signed_in}
    _AUTH_CACHE[cache_key] = (time.monotonic(), result)
    return dict(result)


def node_catalog(settings):
    from .runner import ProviderError
    key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
    if key:
        # The catalog is the Cloud v1 surface; the SDK handles Bearer auth on v2 jobs.
        response = httpx.get(HOSTED_URL + "/api/object_info", headers={"X-API-Key": key}, timeout=60)
        if response.status_code != 200:
            raise ProviderError(f"Hosted Comfy Cloud catalog returned HTTP {response.status_code}; check API-key access.")
        return response.json()
    cli = find_cli(settings)
    python = Path(cli).parent / "python" if cli else Path("")
    if not cli or not python.is_file():
        raise ProviderError("The CLI OAuth route needs a Python installation of comfy-cli 1.23+. Set its installed executable path.")
    result = subprocess.run([str(python), str(Path(__file__).with_name("cloud_catalog_bridge.py"))], capture_output=True, text=True,
        timeout=75, env=dict(os.environ, COMFY_CLOUD_BASE_URL=HOSTED_URL))
    if result.returncode:
        raise ProviderError("Cannot read hosted Cloud nodes with the CLI session. Run `comfy cloud login` on the app server, then check the connection again.")
    return json.loads(result.stdout)


def _options(catalog, node, field):
    schema = catalog.get(node, {}).get("input", {}).get("required", {}).get(field, [[]])
    return schema[0] if isinstance(schema[0], list) else schema[1].get("options", []) if len(schema) > 1 else []


def check_hosted(settings):
    from .cloud_tracking import tracker_status
    status = auth_status(settings, refresh=True)
    if status["mode"] == "missing":
        return {"available": False, "auth_mode": "missing", "detail": "Add a Comfy API key, or run `comfy cloud login` on the app server and check again."}
    catalog = node_catalog(settings)
    models = []
    checkpoints = _options(catalog, "CheckpointLoaderSimple", "ckpt_name")
    if "ltx-2.3-22b-dev.safetensors" in checkpoints:
        models.append("ltx-2.3")
    if "ltxv-2b-0.9.8-distilled.safetensors" in checkpoints:
        models.append("ltx-0.9.8")
    if "wan2.1_vace_1.3B_fp16.safetensors" in _options(catalog, "UNETLoader", "unet_name"):
        models.append("wan-vace")
    from .cloud_ltx25 import capability
    ltx25 = capability(catalog)
    if ltx25["available"]:
        models.append("ltx-2.5")
    tracker = tracker_status(settings)
    result = {"available": bool(models), "auth_mode": status["mode"], "models": models,
              "supported_tracking_methods": ["static", "flow"] + (["sam2"] if tracker["available"] else []),
              "local_sam2": tracker, "model_capabilities": {"ltx-2.5": ltx25},
              "detail": "Hosted Cloud nodes respond. LTX 2.5 inpaint renders native composited video; removal lighting correction additionally runs locally and retains that native preview. Older profiles use local final compositing. Source/mask preparation is local; SAM2 requires the configured local tracker. Exact graph/weights are checked before submission; this connection check does not verify rendered quality."}
    if status["mode"] == "cli-oauth":
        balance = _cli(settings, ["cloud", "status"], timeout=30)
        free = (balance.get("free_tier_balance") or {}).get("remaining")
        paid = balance.get("credit_balance_credits")
        result.update(free_runs_remaining=free, credit_balance_credits=paid)
        if free == 0 and paid == 0:
            result.update(available=False, detail="Cloud is authenticated, but this workspace has no remaining free runs or credits. No billing change was made.")
    return result


def _lossless_input(path, frames, width, height, fps, cancel):
    """RGB lossless H.264 avoids a colour/subsampling change in prepared inputs."""
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264rgb", "-preset", "fast", "-crf", "0", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            cancel(); process.stdin.write(frame.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode(errors="replace")
        if process.wait(timeout=180):
            raise ValueError("Lossless Cloud input encoding failed: " + error[-1000:])
    except BaseException:
        process.kill(); process.wait(); path.unlink(missing_ok=True)
        raise
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.stderr.close()


def prepare(request, assets, output_dir, cancel, settings=None, progress=lambda *_: None):
    """Prepare exact temporal alignment/masks, retaining only necessary CPU state."""
    import numpy as np
    from PIL import Image
    from custom_nodes.openframe import media
    from .runner import ProviderError
    graph = build_workflow(request, {role: Path(path).name for role, path in assets.items()})
    prepared = {}; original = alpha = None; tracking = None
    directory = output_dir / "cloud-input"
    directory.mkdir(exist_ok=True)
    if "source" in graph:
        source = graph["source"]["inputs"]
        width, height, count, fps = request["width"], request["height"], request["frames"], request["fps"]
        # The host holds source+mask arrays for the bounded clip, never model weights.
        estimate = width * height * count * 32
        if estimate > 2 * 1024**3:
            raise ProviderError("This Cloud clip needs over 2 GiB of local media buffers. Shorten the clip or reduce resolution; no GPU job was submitted.")
        original = media.decode_frames(assets["source"], width, height, fps, count, request.get("trim_start", 0))
        if request["task"] == "inpaint":
            mask_path = Path(assets["mask"])
            if mask_path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
                masks = media.decode_frames(mask_path, width, height, fps, count, request.get("trim_start", 0)).mean(axis=-1) / 255.0
            else:
                with Image.open(mask_path) as image:
                    first = media.fit_mask(image, width, height)
                if request["mask_tracking_method"] == "sam2":
                    from .cloud_tracking import track
                    masks, tracking = track(request, assets, output_dir, settings or {}, progress, cancel)
                else:
                    masks = media.propagate_mask(original, first, request["mask_tracking_method"], cancel)
        else:
            masks = np.ones((count, height, width), np.float32)
        generation, alpha = media.prepare_masks(masks, source["mask_dilation"], source["mask_feather"], source["feather_method"], edit_margin=source.get("edit_margin", 0))
        if tracking:
            tracked_path = directory / (request["job_id"] + "-tracked-mask.mp4")
            _lossless_input(tracked_path, (np.repeat((frame * 255).round().astype(np.uint8)[..., None], 3, axis=2) for frame in masks), width, height, fps, cancel)
            prepared["tracked_mask"] = tracked_path
        padded = "pad_refinement" in graph
        dh, dw = ((-height) % 64, (-width) % 64) if padded else (0, 0)
        for role, images in (("source", original), ("generation_mask", generation)):
            path = directory / f"{request['job_id']}-{role}.mp4"
            def encoded_frames():
                for frame in images:
                    if role == "generation_mask":
                        frame = np.repeat((frame * 255).round().astype(np.uint8)[..., None], 3, axis=2)
                    if dh or dw:
                        frame = np.pad(frame, ((0, dh), (0, dw), (0, 0)), mode="edge" if role == "source" else "constant")
                    yield frame
            _lossless_input(path, encoded_frames(), width + dw, height + dh, fps, cancel)
            prepared[role] = path
    else:
        for role, path in assets.items():
            prepared[role] = Path(path)
    if assets.get("reference"):
        prepared["reference"] = Path(assets["reference"])
    return graph, prepared, original, alpha, tracking


def native_graph(logical, request, filenames):
    """Replace utility boundaries only; all model/sampling nodes stay unchanged."""
    graph = copy.deepcopy(logical)
    def node(name, cls, **inputs):
        graph[name] = {"class_type": cls, "inputs": inputs, "_meta": {"title": cls}}
        return [name, 0]
    editing = "source" in graph
    if editing:
        graph.pop("source")
        source = node("cloud_source_file", "LoadVideo", file=filenames["source"])
        source = node("cloud_source", "GetVideoComponents", video=source)
        mask = node("cloud_mask_file", "LoadVideo", file=filenames["generation_mask"])
        mask = node("cloud_mask_frames", "GetVideoComponents", video=mask)
        mask = node("cloud_mask", "ImageToMask", image=mask, channel="red")
        padded = graph.pop("pad_refinement", None)
        replacements = {("source", 0): source, ("source", 1): mask}
        if padded:
            replacements.update({("pad_refinement", 0): source, ("pad_refinement", 1): mask})
        for entry in graph.values():
            for field, value in entry["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and tuple(value) in replacements:
                    entry["inputs"][field] = replacements[tuple(value)]
        for name, spec in list(graph.items()):
            if spec["class_type"] == "OpenFrameGreenFill":
                coarse = name == "green_guide" and bool(padded)
                width = ((request["width"] + 63) // 64) * 64 if padded else request["width"]
                height = ((request["height"] + 63) // 64) * 64 if padded else request["height"]
                green = node(name + "_colour", "EmptyImage", width=width // 2 if coarse else width,
                             height=height // 2 if coarse else height, batch_size=1, color=0x66FF00)
                graph[name] = {"class_type": "ImageCompositeMasked", "inputs": {"destination": spec["inputs"]["images"],
                    "source": green, "x": 0, "y": 0, "resize_source": False, "mask": spec["inputs"]["mask"]}}
    for name, role in (("image", "source"), ("reference", "reference")):
        if name in graph:
            graph[name]["inputs"]["image"] = filenames[role]
    save = graph.pop("save")["inputs"]
    node("save", "SaveImage", images=save["images"], filename_prefix="openframe/" + request["job_id"])
    if save.get("audio") and request.get("generate_audio", True):
        node("save_audio", "SaveAudio", audio=save["audio"], filename_prefix="openframe/" + request["job_id"])
    return graph


def _validate(graph, catalog):
    from .runner import ProviderError
    missing = sorted({entry["class_type"] for entry in graph.values()} - catalog.keys())
    if missing:
        raise ProviderError("Hosted Cloud lacks required nodes: " + ", ".join(missing))
    for entry in graph.values():
        name = entry["class_type"]
        for field, value in entry["inputs"].items():
            if (field.endswith("_name") and name in {"CheckpointLoaderSimple", "UNETLoader", "CLIPLoader", "VAELoader", "LoraLoaderModelOnly", "LTXICLoRALoaderModelOnly", "LTXAVTextEncoderLoader"}) or (name == "LTXAVTextEncoderLoader" and field == "text_encoder"):
                choices = _options(catalog, name, field)
                if choices and isinstance(value, str) and value not in choices:
                    raise ProviderError(f"Hosted Cloud does not provide exact required weight {value}. No model substitution or GPU submission was made.")


def input_slots(graph):
    from .cloud_ltx25 import INPUT_SLOTS
    slots = [*INPUT_SLOTS, ("image", "image", "source")]
    return [(node, field, role) for node, field, role in slots if node in graph]


def _run_cli(graph, prepared, output_dir, settings, progress, cancel):
    from .runner import ProviderError
    filenames = {}
    used_roles = {role for node, field, role in input_slots(graph)}
    for role, path in prepared.items():
        if role not in used_roles:
            continue
        cancel(); progress(.06, "Uploading " + role + " to Comfy Cloud")
        item = _cli(settings, ["upload", str(path), "--where", "cloud", "--no-overwrite"], timeout=300, cancel=cancel)["uploads"][0]
        filenames[role] = "/".join(x for x in (item.get("subfolder", ""), item["cloud_name"]) if x)
    for node, field, role in input_slots(graph):
        graph[node]["inputs"][field] = filenames[role]
    path = output_dir / "workflow.cloud.json"
    path.write_text(json.dumps(graph, indent=2))
    cancel()
    result = _cli(settings, ["run", "--workflow", str(path), "--where", "cloud", "--no-watch"], timeout=90)
    ident = result["prompt_id"]
    (output_dir / "provider-job.json").write_text(json.dumps({"provider": "comfy-cloud", "prompt_id": ident, "auth_mode": "cli-oauth", "url": HOSTED_URL}))
    start = time.monotonic(); terminal = False
    try:
        while True:
            cancel()
            status = _cli(settings, ["jobs", "status", ident, "--where", "cloud"], timeout=45)
            state = status["status"]
            terminal = state in {"completed", "failed", "error", "cancelled", "canceled"}
            if terminal:
                if state != "completed":
                    detail = str(status.get("error_message") or status.get("execution_error") or "No output generated")[:1200]
                    hint = " The hosted service stopped this job. Try fewer frames/lower resolution or Local ComfyUI; the requested duration was not changed and the job was not retried." if "exceeded maximum limit" in detail.lower() else ""
                    raise ProviderError(f"Hosted Cloud {state} (job {ident}): {detail}" + hint)
                break
            progress(.15, "Comfy Cloud: " + state)
            if time.monotonic() - start > 7200:
                raise ProviderError("Hosted Cloud exceeded two hours; cancellation requested.")
            time.sleep(3)
        progress(.86, "Downloading Cloud-generated media")
        downloads = _cli(settings, ["download", ident, "--where", "cloud", "--out-dir", str(output_dir / "cloud-output")], timeout=600, cancel=cancel)
        by_url = {item["url"]: Path(item["path"]) for item in downloads["files"]}
        outputs = {node: [by_url[url] for url in urls if url in by_url] for node, urls in status["outputs_by_node"].items()}
        return ident, graph, outputs
    except BaseException:
        if not terminal:
            _cli(settings, ["jobs", "cancel", ident, "--where", "cloud"], timeout=45)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = _cli(settings, ["jobs", "status", ident, "--where", "cloud"], timeout=20)["status"]
                if state in {"completed", "failed", "error", "cancelled", "canceled"}:
                    break
                time.sleep(2)
            else:
                raise ProviderError("Cloud cancellation is not yet confirmed. Inspect provider job " + ident)
        raise


def _run_sdk(graph, prepared, request, output_dir, settings, progress, cancel):
    from comfy_sdk import Comfy
    from .runner import ProviderError
    key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
    with _SDK_LOCK:
        old = os.environ.get("COMFY_BASE_URL")
        os.environ["COMFY_BASE_URL"] = HOSTED_URL
        try:
            client = Comfy(api_key=key)
        finally:
            if old is None:
                os.environ.pop("COMFY_BASE_URL", None)
            else:
                os.environ["COMFY_BASE_URL"] = old
    workflow = client.workflows.from_json(graph)
    for node, field, role in input_slots(graph):
        workflow.set_input(node, field, client.assets.from_file(str(prepared[role])))
    cancel(); progress(.08, "Submitting native graph to Comfy Cloud")
    job = client.submit(workflow, idempotency_key=request["job_id"])
    (output_dir / "provider-job.json").write_text(json.dumps({"provider": "comfy-cloud", "job_id": job.id, "auth_mode": "api-key", "url": HOSTED_URL}))
    start = time.monotonic()
    try:
        while True:
            cancel(); job.refresh()
            if job.status in {"succeeded", "failed", "cancelled", "canceled"}:
                break
            if time.monotonic() - start > 7200:
                raise ProviderError("Hosted Cloud exceeded two hours; cancellation requested.")
            progress(.15, "Comfy Cloud: " + job.status); time.sleep(3)
        job.result()
        outputs = {}
        raw = output_dir / "cloud-output"; raw.mkdir(exist_ok=True)
        from .cloud_ltx25 import OUTPUT_NODES
        for node in OUTPUT_NODES:
            if node not in graph:
                continue
            outputs[node] = []
            for index, item in enumerate(job.get_outputs(node)):
                cancel()
                destination = raw / (str(index).zfill(6) + "-" + Path(item.name).name)
                item.to_file(str(destination)); outputs[node].append(destination)
        return job.id, job.get_workflow().graph, outputs
    except BaseException:
        if job.status not in {"succeeded", "failed", "cancelled", "canceled"}:
            job.cancel()
            job.wait(timeout=60)
            if job.status not in {"succeeded", "failed", "cancelled", "canceled"}:
                raise ProviderError("Cloud cancellation is not yet confirmed. Inspect provider job " + job.id)
        raise


def run_hosted(request, assets, output_dir, settings, on_progress, is_cancelled):
    if request["model_id"] == "ltx-2.5":
        from .cloud_ltx25 import run
        return run(request, assets, output_dir, settings, on_progress, is_cancelled)
    from PIL import Image
    import numpy as np
    from custom_nodes.openframe import media
    from .runner import ProviderError, _raise_if_cancelled
    cancel = lambda: _raise_if_cancelled(is_cancelled)
    auth = auth_status(settings, refresh=True)
    if auth["mode"] == "missing":
        raise ProviderError("Sign in using `comfy cloud login` on the app server, or configure a Comfy API key.")
    catalog = node_catalog(settings)
    on_progress(.02, "Preparing aligned source and masks locally")
    logical, prepared, original, alpha, tracking = prepare(request, assets, output_dir, cancel, settings, on_progress)
    graph = native_graph(logical, request, {role: path.name for role, path in prepared.items()})
    _validate(graph, catalog)
    started = time.monotonic()
    if auth["mode"] == "cli-oauth":
        ident, executed, outputs = _run_cli(graph, prepared, output_dir, settings, on_progress, cancel)
    else:
        ident, executed, outputs = _run_sdk(graph, prepared, request, output_dir, settings, on_progress, cancel)
    frames = outputs.get("save", [])
    if len(frames) != request["frames"] or any(path.suffix.lower() != ".png" for path in frames):
        raise ProviderError(f"Cloud returned {len(frames)} lossless frames; expected {request['frames']}. No partial clip was published.")
    on_progress(.94, "Compositing original plate and encoding final video locally")
    save = logical["save"]["inputs"]
    def final_frames():
        for index, path in enumerate(frames):
            cancel()
            with Image.open(path) as image:
                if image.size != (request["width"], request["height"]):
                    raise ProviderError("Cloud returned unexpected output dimensions")
                pixels = np.asarray(image.convert("RGB"), np.float32) / 255.0
            blend = original is not None and save.get("preserve_outside_mask")
            yield media.composite_frame(pixels, original[index].astype(np.float32) / 255.0 if blend else None,
                alpha[index] if blend else None, save.get("match_lighting", False))
    source_audio = assets.get("source") if original is not None and request.get("preserve_audio", True) else None
    trim = request.get("trim_start", 0)
    # Native SaveAudio keeps generated audio losslessly; the shared encoder reads
    # it as an audio source without a second waveform serialization.
    if source_audio:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(source_audio)], capture_output=True, timeout=30, check=True)
        if not probe.stdout.strip():
            source_audio = None
    if not source_audio and outputs.get("save_audio"):
        source_audio = outputs["save_audio"][0]; trim = 0
    result = output_dir / (request["job_id"] + "-cloud.mp4")
    media.encode_video(result, final_frames(), request["width"], request["height"], request["fps"], request["frames"],
                       source_audio=source_audio, trim_start=trim, check_cancelled=cancel)
    final = [{"path": str(result), "kind": "video", "role": "result"}]
    if request["task"] == "inpaint" and request.get("export_mask", True):
        mask = output_dir / (request["job_id"] + "-mask.mp4")
        media.encode_mask_video(mask, alpha, request["width"], request["height"], request["fps"])
        final.append({"path": str(mask), "kind": "video", "role": "mask"})
    prepared_info = {}
    for role, path in prepared.items():
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        prepared_info[role] = {"filename": path.name, "sha256": digest, "size": path.stat().st_size,
            "relative_path": str(path.relative_to(output_dir)) if path.is_relative_to(output_dir) else None}
    metadata = {"provider": "comfy-cloud", "auth_mode": auth["mode"], "provider_job_id": ident, "provider_url": HOSTED_URL,
        "request": request, "seconds": time.monotonic() - started, "execution": "hosted-cloud-diffusion-local-media",
        "workflow_role": "local-replay-recipe", "cloud_workflow": executed, "prepared_inputs": prepared_info,
        "pipeline": "ltx-inpaint-two-stage" if "sample_refinement" in logical else "ltx-inpaint-single-stage" if request["model_id"] == "ltx-2.3" and request["task"] == "inpaint" else request["model_id"] + ":" + request["task"],
        "processing": {"input_encoding": "lossless-rgb-h264", "cloud_output": "lossless-8-bit-png-frames",
            "mask_feather_method": logical.get("source", {}).get("inputs", {}).get("feather_method"),
            "match_lighting": save.get("match_lighting", False), "composite": "shared-custom-node-media-helper",
            "note": "The local replay graph includes the complete pipeline. The separately recorded Cloud graph executes diffusion only; local CPU preprocessing/compositing/audio encoding are explicit. Cloud PNG output quantizes generated RGB to 8 bits before local compositing."}}
    if request["model_id"] == "ltx-2.3" and request["task"] in {"inpaint", "restyle"}:
        metadata["audio_policy"] = {
            "selected_mode": request.get("audio_mode"),
            "legacy_flags_preserved": request.get("audio_mode") is None,
            "mux_source": "generated" if source_audio in outputs.get("save_audio", []) else "source" if source_audio else "none",
            "trim_start": trim,
            "note": "Hosted diffusion/local mux routing. Output audio alignment and generated sound quality are not inferred from successful execution.",
        }
    if tracking:
        metadata["tracking"] = tracking
    (output_dir / "workflow.cloud.json").write_text(json.dumps(executed, indent=2))
    # Raw generated frames are transient. Keep the prepared inputs and executed
    # graph for a portable audit; the final video is the durable output.
    for paths in outputs.values():
        for path in paths:
            if path.is_relative_to(output_dir / "cloud-output"):
                path.unlink(missing_ok=True)
    return {"outputs": final, "workflow": logical, "ui_workflow": None, "metadata": metadata}
