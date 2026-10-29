"""Real execution adapters. All providers execute the selected ComfyUI graph."""
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import threading
import time
import uuid

import httpx
from .workflows import build_workflow, normalize_request


class JobCancelled(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


_CLOUD_CONFIG_LOCK = threading.Lock()


def _raise_if_cancelled(is_cancelled):
    if is_cancelled():
        raise JobCancelled("Generation cancelled.")


def _url(value):
    value = str(value).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ProviderError("Provider URL must be an HTTP(S) URL without embedded credentials.")
    return value


def check_provider(provider, settings):
    try:
        if provider == "modal":
            import modal
            function = modal.Function.from_name(settings.get("modal_app", "openframe-comfy"), settings.get("modal_function", "render"), environment_name=settings.get("modal_environment") or None)
            function.hydrate()
            return {"available": True, "detail": "Modal deployment found. GPU starts only when a job is submitted.", "models": ["ltx-0.9.8", "ltx-2.3", "wan-vace"]}
        if provider == "comfy-cloud":
            from .cloud import HOSTED_URL, check_hosted
            if settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/") == HOSTED_URL:
                return check_hosted(settings)
            key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
            if not key:
                return {"available": False, "detail": "Add a Comfy API key and a deployment containing the OpenFrame node pack."}
            url = _url(settings.get("comfy_cloud_url", "https://cloud.comfy.org"))
            response = httpx.get(url + "/api/v2/jobs", headers={"Authorization": f"Bearer {key}"}, params={"limit": 1}, timeout=15)
            if response.status_code not in {200, 501}:
                raise ProviderError(f"Comfy API returned HTTP {response.status_code}.")
            return {"available": True, "detail": "Comfy API responds. Your deployment must contain the model weights and OpenFrame custom nodes; node availability is validated on submission."}
        if provider != "local":
            raise ProviderError("Unknown compute provider.")
        url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
        headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
        with httpx.Client(timeout=15, headers=headers) as client:
            response = client.get(url + "/system_stats"); response.raise_for_status()
            info = client.get(url + "/object_info"); info.raise_for_status()
            classes = info.json()
            missing = [name for name in ("OpenFrameSaveVideo", "OpenFrameVideoInput", "OpenFrameGreenFill", "OpenFramePadForRefinement") if name not in classes]
            if missing:
                return {"available": False, "detail": "ComfyUI is running. Install the OpenFrame node pack and restart: " + ", ".join(missing)}
            available = []
            ckpts = classes.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            unets = classes.get("UNETLoader", {}).get("input", {}).get("required", {}).get("unet_name", [[]])[0]
            if "ltxv-2b-0.9.8-distilled.safetensors" in ckpts:
                available.append("ltx-0.9.8")
            if "ltx-2.3-22b-dev.safetensors" in ckpts:
                available.append("ltx-2.3")
            if "wan2.1_vace_1.3B_fp16.safetensors" in unets:
                available.append("wan-vace")
            return {"available": True, "detail": "ComfyUI and OpenFrame nodes are available. Selected graph validates all required weights at submission.", "models": available, "devices": response.json().get("devices", [])}
    except Exception as exc:
        return {"available": False, "detail": f"{type(exc).__name__}: {str(exc)[:500]}"}


def _cancel_local(client, prompt_id):
    client.post("/queue", json={"delete": [prompt_id]})
    queue = client.get("/queue").json()
    if any(item[1] == prompt_id for item in queue.get("queue_running", [])):
        client.post("/interrupt", json={})


def _run_local(request, assets, output_dir, settings, on_progress, is_cancelled):
    import websocket
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    client_id = uuid.uuid4().hex
    ws = None
    prompt_id = None
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    with httpx.Client(base_url=url, timeout=120, headers=headers) as client:
        filenames = {}
        for role, path in assets.items():
            _raise_if_cancelled(is_cancelled)
            name = f"openframe_{request['job_id']}_{role}{Path(path).suffix.lower()}"
            on_progress(.02, f"Uploading {role}")
            with Path(path).open("rb") as file:
                response = client.post("/upload/image", files={"image": (name, file)}, data={"type": "input", "overwrite": "false"})
            response.raise_for_status(); data = response.json()
            filenames[role] = "/".join(x for x in (data.get("subfolder", ""), data["name"]) if x)
        graph = build_workflow(request, filenames)
        try:
            wsurl = url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
            try:
                ws = websocket.create_connection(f"{wsurl}/ws?clientId={client_id}", timeout=2, suppress_origin=True, header=headers)
            except (OSError, websocket.WebSocketException):
                ws = None  # History polling remains authoritative.
            response = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
            if response.status_code >= 400:
                raise ProviderError("ComfyUI rejected the workflow: " + response.text[:5000])
            prompt_id = response.json()["prompt_id"]
            (output_dir / "provider-job.json").write_text(json.dumps({"provider": "local", "prompt_id": prompt_id, "url": url}))
            on_progress(.05, "Queued in ComfyUI")
            completed = set(); last_poll = 0.0; start = time.monotonic(); current = None
            while True:
                if is_cancelled():
                    _cancel_local(client, prompt_id)
                    raise JobCancelled("ComfyUI job cancelled.")
                if time.monotonic() - start > 7200:
                    _cancel_local(client, prompt_id)
                    raise ProviderError("ComfyUI execution exceeded two hours and was cancelled.")
                if ws:
                    try:
                        message = ws.recv()
                        if isinstance(message, str):
                            event = json.loads(message); data = event.get("data", {})
                            if data.get("prompt_id") in {None, prompt_id}:
                                if event.get("type") == "executing" and data.get("node"):
                                    if current:
                                        completed.add(current)
                                    current = str(data["node"])
                                    stage = graph.get(current, {}).get("class_type", "ComfyUI")
                                    on_progress(min(.88, .08 + .8 * len(completed) / len(graph)), stage)
                                elif event.get("type") == "progress" and data.get("max"):
                                    fraction = min(1, data.get("value", 0) / data["max"])
                                    tracking = current == "source"
                                    refining = current == "sample_refinement"
                                    progress_value = (.08 + .2 * fraction) if tracking else (.72 + .16 * fraction) if refining else (.3 + (.35 if "sample_refinement" in graph else .55) * fraction)
                                    label = "Tracking mask" if tracking else "Refining detail" if refining else "Sampling"
                                    on_progress(progress_value, f"{label} {data.get('value', 0)}/{data['max']}")
                                elif event.get("type") == "execution_error":
                                    raise ProviderError(f"{data.get('node_type', 'ComfyUI')}: {data.get('exception_message', 'Execution failed')}")
                    except websocket.WebSocketTimeoutException:
                        pass
                    except websocket.WebSocketConnectionClosedException:
                        ws = None
                else:
                    time.sleep(.5)
                if time.monotonic() - last_poll < 1.5:
                    continue
                last_poll = time.monotonic()
                response = client.get(f"/history/{prompt_id}"); response.raise_for_status()
                record = response.json().get(prompt_id)
                if not record:
                    continue
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    messages = status.get("messages", [])
                    details = next((m[1] for m in reversed(messages) if m[0] == "execution_error"), {})
                    raise ProviderError(f"ComfyUI failed: {details.get('exception_message', str(messages)[-2000:])}")
                if not status.get("completed"):
                    continue
                outputs = []
                # Only final save-node media; previews must never become output footage.
                for group in record.get("outputs", {}).get("save", {}).values():
                    if not isinstance(group, list):
                        continue
                    for item in group:
                        if not isinstance(item, dict) or not item.get("filename") or Path(item["filename"]).suffix.lower() not in {".mp4", ".webm", ".mov"}:
                            continue
                        on_progress(.94, "Downloading finished video")
                        filename = Path(item["filename"]).name
                        destination = output_dir / filename
                        with client.stream("GET", "/view", params={"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}) as stream:
                            stream.raise_for_status()
                            with destination.open("wb") as file:
                                for chunk in stream.iter_bytes():
                                    _raise_if_cancelled(is_cancelled); file.write(chunk)
                        outputs.append({"path": str(destination), "kind": "video", "role": item.get("role", "result")})
                if not outputs:
                    raise ProviderError("ComfyUI completed but the final save node returned no video. Inspect the execution history.")
                metadata = {"prompt_id": prompt_id, "provider": "local", "request": request, "seconds": time.monotonic() - start, "pipeline": "ltx-inpaint-two-stage" if "sample_refinement" in graph else "ltx-inpaint-single-stage" if request["model_id"] == "ltx-2.3" and request["task"] == "inpaint" else request["model_id"] + ":" + request["task"]}
                ui_workflow = None
                try:
                    from .export import to_ui_workflow
                    schema_response = client.get("/object_info"); schema_response.raise_for_status()
                    ui_workflow = to_ui_workflow(graph, schema_response.json())
                    (output_dir / "workflow.ui.json").write_text(json.dumps(ui_workflow, indent=2))
                except Exception as exc:
                    metadata["ui_export_error"] = str(exc)[:500]
                return {"outputs": outputs, "workflow": graph, "ui_workflow": ui_workflow, "metadata": metadata}
        except BaseException:
            if prompt_id:
                try:
                    _cancel_local(client, prompt_id)
                except Exception:
                    pass
            raise
        finally:
            if ws:
                ws.close()


def _run_modal(request, assets, output_dir, settings, on_progress, is_cancelled):
    import modal
    from modal.exception import FunctionTimeoutError
    environment = settings.get("modal_environment") or None
    volume = modal.Volume.from_name(settings.get("modal_volume", "openframe-assets"), environment_name=environment)
    # The host may poll before a cold worker first creates its progress dictionary.
    progress_store = modal.Dict.from_name(settings.get("modal_progress_dict", "openframe-progress"), environment_name=environment, create_if_missing=True)
    function = modal.Function.from_name(settings.get("modal_app", "openframe-comfy"), settings.get("modal_function", "render"), environment_name=environment)
    job_id = request["job_id"]
    remote_files = {}
    if assets:
        on_progress(.01, "Uploading source media to Modal")
        with volume.batch_upload() as batch:
            for role, path in assets.items():
                _raise_if_cancelled(is_cancelled)
                remote = f"/jobs/{job_id}/input/{role}{Path(path).suffix.lower()}"
                batch.put_file(str(path), remote)
                remote_files[role] = remote
    _raise_if_cancelled(is_cancelled)
    call = function.spawn(request, remote_files, job_id)
    (output_dir / "provider-job.json").write_text(json.dumps({"provider": "modal", "call_id": call.object_id, "job_id": job_id}))
    on_progress(.03, "Starting Modal ComfyUI GPU worker")
    last_progress = None
    host_progress = .03
    try:
        while True:
            if is_cancelled():
                call.cancel(terminate_containers=True)
                raise JobCancelled("Modal GPU job cancelled.")
            try:
                result = call.get(timeout=2)
                break
            except FunctionTimeoutError:
                raise
            except TimeoutError:
                progress = progress_store.get(job_id, None)
                if progress and progress != last_progress:
                    last_progress = progress
                    fraction = max(0.0, min(1.0, float(progress.get("progress", 0))))
                    host_progress = max(host_progress, .03 + .91 * fraction)
                    stage = str(progress.get("stage", "Rendering on Modal"))
                    if stage == "Complete":
                        stage = "Preparing finished files for transfer"
                    on_progress(host_progress, stage)
        outputs = []
        on_progress(.96, "Downloading finished video from Modal")
        for item in result["outputs"]:
            remote_path = item["path"]
            destination = output_dir / Path(remote_path).name
            with destination.open("wb") as file:
                for chunk in volume.read_file(remote_path):
                    _raise_if_cancelled(is_cancelled); file.write(chunk)
            outputs.append({**item, "path": str(destination)})
        return {**result, "outputs": outputs, "metadata": {**result.get("metadata", {}), "provider": "modal", "call_id": call.object_id}}
    except BaseException:
        try:
            call.cancel(terminate_containers=True)
        except Exception:
            pass
        raise


def _run_cloud(request, assets, output_dir, settings, on_progress, is_cancelled):
    from .cloud import HOSTED_URL, run_hosted
    if settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/") == HOSTED_URL:
        return run_hosted(request, assets, output_dir, settings, on_progress, is_cancelled)
    try:
        from comfy_sdk import Comfy
    except ImportError as exc:
        raise ProviderError("Install the cloud extra: pip install '.[cloud]'.") from exc
    key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
    if not key:
        raise ProviderError("A Comfy API key is required for this provider.")
    graph = build_workflow(request, {role: Path(path).name for role, path in assets.items()})
    # Current official SDK resolves the endpoint at construction from COMFY_BASE_URL.
    with _CLOUD_CONFIG_LOCK:
        old_url = os.environ.get("COMFY_BASE_URL")
        os.environ["COMFY_BASE_URL"] = _url(settings.get("comfy_cloud_url", "https://cloud.comfy.org"))
        try:
            client = Comfy(api_key=key)
        finally:
            if old_url is None:
                os.environ.pop("COMFY_BASE_URL", None)
            else:
                os.environ["COMFY_BASE_URL"] = old_url
    wf = client.workflows.from_json(graph)
    for role, path in assets.items():
        asset = client.assets.from_file(str(path))
        if role == "source":
            if "source" in graph:
                wf.set_input("source", "filename", asset)
                wf.set_input("save", "source_filename", asset)
            else:
                wf.set_input("image", "image", asset)
        elif role == "mask" and "source" in graph:
            wf.set_input("source", "mask_filename", asset)
        elif role == "reference" and "reference" in graph:
            wf.set_input("reference", "image", asset)
    _raise_if_cancelled(is_cancelled)
    on_progress(.04, "Uploading assets and submitting to Comfy API")
    # Do not retry an ambiguous submission: duplicate execution can incur a second charge.
    job = client.submit(wf, idempotency_key=request["job_id"])
    (output_dir / "provider-job.json").write_text(json.dumps({"provider": "comfy-cloud", "job_id": job.id}))
    try:
        start = time.monotonic()
        while True:
            if is_cancelled():
                job.cancel()
                # Confirm the terminal state rather than treating an HTTP cancellation request as completion.
                job.wait(timeout=60)
                if job.status not in {"cancelled", "canceled", "failed", "succeeded"}:
                    raise ProviderError("Comfy cancellation is still pending. Check job " + job.id)
                raise JobCancelled("Comfy API cancellation completed.")
            job.refresh()
            if job.status in {"succeeded", "failed", "cancelled", "canceled"}:
                break
            on_progress(.1, "Comfy API: " + job.status)
            if time.monotonic() - start > 7200:
                job.cancel()
                raise ProviderError("Cloud render exceeded two hours; cancellation requested for " + job.id)
            time.sleep(2)
        job.result()
        outputs = []
        for item in job.get_outputs("save"):
            filename = Path(item.name).name
            if Path(filename).suffix.lower() not in {".mp4", ".webm", ".mov"}:
                continue
            destination = output_dir / filename
            item.to_file(str(destination)); outputs.append({"path": str(destination), "kind": "video"})
        if not outputs:
            raise ProviderError("Comfy API returned no final video. Verify the OpenFrame node pack in your Build.")
        return {"outputs": outputs, "workflow": graph, "metadata": {"provider": "comfy-cloud", "job_id": job.id, "request": request}}
    except BaseException:
        if job.status not in {"succeeded", "failed", "cancelled", "canceled"}:
            try:
                job.cancel()
            except Exception:
                pass
        raise


def run_job(request, assets, output_dir, settings, on_progress, is_cancelled):
    output_dir = Path(output_dir).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    r = normalize_request(request)
    required_assets = {"source", "mask"} if r["task"] == "inpaint" else {"source"} if r["task"] in {"image-to-video", "restyle"} else set()
    if missing_assets := required_assets - assets.keys():
        raise ProviderError("Missing required input assets: " + ", ".join(sorted(missing_assets)))
    r["job_id"] = str(request.get("job_id") or uuid.uuid4().hex)
    if not r["job_id"].replace("-", "").isalnum():
        raise ProviderError("Invalid job identifier.")
    _raise_if_cancelled(is_cancelled)
    provider = r.get("provider", settings.get("default_provider", "local"))
    runner = {"local": _run_local, "modal": _run_modal, "comfy-cloud": _run_cloud}.get(provider)
    if not runner:
        raise ProviderError("Unknown compute provider.")
    result = runner(r, assets, output_dir, settings, on_progress, is_cancelled)
    _raise_if_cancelled(is_cancelled)
    on_progress(1.0, "Complete")
    return result
