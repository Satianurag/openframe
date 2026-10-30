"""Persistent transports for the same real ComfyUI character-training graph."""
import json
from pathlib import Path
import re
import time
from .training_runtime import normalize_training_request, MAX_SECONDS


def training_asset_roles(assets):
    photos = [key for key in assets if re.fullmatch(r"dataset_\d+", key)]
    masks = [key for key in assets if re.fullmatch(r"loss_mask_\d+", key)]
    ordered = [f"dataset_{index}" for index in range(len(photos))]
    paired = [f"loss_mask_{index}" for index in range(len(photos))] if masks else []
    if not 20 <= len(photos) <= 50 or set(assets) != set(ordered + paired):
        raise ValueError("Training requires20–50 ordered photographs and, optionally, exactly one loss mask per photograph.")
    return ordered, paired


def training_graph(request, filenames, photo_roles, mask_roles):
    inputs = {"request_json": json.dumps(request), "dataset_json": json.dumps([filenames[role] for role in photo_roles])}
    if mask_roles:
        inputs["loss_masks_json"] = json.dumps([filenames[role] for role in mask_roles])
    return {"train": {"class_type": "OpenFrameTrainCharacter", "inputs": inputs}}


def train_character(request, assets, settings, on_progress, is_cancelled, on_submitted=None):
    from .provider_policy import require_provider_enabled
    r = normalize_training_request(request)
    require_provider_enabled(r["provider"])
    training_asset_roles(assets)
    return _train_local(r, assets, settings, on_progress, is_cancelled, on_submitted)


def training_host_id(settings):
    """Bind an adapter to its configured Comfy host without persisting credentials."""
    import hashlib
    from .runner import _url
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    return hashlib.sha256(url.encode()).hexdigest()


def _train_local(r, assets, settings, on_progress, is_cancelled, on_submitted):
    import httpx
    import websocket
    from .runner import _url, _cancel_local, JobCancelled, ProviderError
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    prompt_id, ws = None, None
    with httpx.Client(base_url=url, timeout=120, headers=headers) as client:
        response = client.get("/object_info/OpenFrameTrainCharacter")
        response.raise_for_status()
        options = response.json().get("OpenFrameTrainCharacter", {}).get("input", {}).get("required", {}).get("request_json", [])
        if len(options) < 2 or options[1].get("openframe_training_available") is not True:
            detail = options[1].get("openframe_training_detail") if len(options) > 1 else None
            raise ProviderError(detail or "Configure the pinned Linux CUDA training runtime; see CHARACTER-TRAINING-RUNTIME.md.")
        photo_roles, mask_roles = training_asset_roles(assets)
        if mask_roles and "loss_masks_json" not in response.json()["OpenFrameTrainCharacter"]["input"].get("optional", {}):
            raise ProviderError("Update the configured training node for opt-in spatial loss masks.")
        filenames = {}
        for index, role in enumerate(photo_roles + mask_roles):
            if is_cancelled():
                raise JobCancelled("Character training cancelled before submission.")
            path = Path(assets[role])
            on_progress(.01 + .02 * index / len(assets), f"Uploading training photograph {index + 1}/{len(assets)}")
            with path.open("rb") as handle:
                response = client.post("/upload/image", files={"image": (f"openframe_{r['job_id']}_{role}{path.suffix.lower()}", handle)},
                                       data={"type": "input", "overwrite": "false"})
            response.raise_for_status()
            item = response.json()
            filenames[role] = "/".join(value for value in (item.get("subfolder", ""), item["name"]) if value)
        graph = training_graph(r, filenames, photo_roles, mask_roles)
        started, last_poll = time.monotonic(), 0
        try:
            try:
                wsurl = url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
                ws = websocket.create_connection(f"{wsurl}/ws?clientId={r['job_id']}", timeout=2, suppress_origin=True, header=headers)
            except (OSError, websocket.WebSocketException):
                pass  # History remains authoritative when websocket progress is unavailable.
            if is_cancelled():
                raise JobCancelled("Character training cancelled before submission.")
            response = client.post("/prompt", json={"prompt": graph, "client_id": r["job_id"]})
            if response.status_code >= 400:
                raise ProviderError("ComfyUI rejected character training: " + response.text[:2000])
            prompt_id = response.json()["prompt_id"]
            if on_submitted:
                on_submitted({"provider": "local", "prompt_id": prompt_id, "job_id": r["job_id"], "host_id": training_host_id(settings)})
            on_progress(.03, "Character training queued in ComfyUI")
            while True:
                if is_cancelled():
                    raise JobCancelled("Character training cancelled; checkpoints remain on the ComfyUI host.")
                if time.monotonic() - started > MAX_SECONDS + 300:
                    raise TimeoutError("Character training exceeded its bounded execution budget.")
                if ws:
                    try:
                        message = ws.recv()
                        if isinstance(message, str):
                            event = json.loads(message)
                            data = event.get("data", {})
                            if event.get("type") == "progress" and data.get("prompt_id") in {None, prompt_id} and data.get("max"):
                                fraction = min(1, max(0, data.get("value", 0) / data["max"]))
                                on_progress(.03 + .94 * fraction, f"Training character · {round(fraction * 100)}%")
                    except websocket.WebSocketTimeoutException:
                        pass
                    except websocket.WebSocketConnectionClosedException:
                        ws.close(); ws = None
                else:
                    time.sleep(.5)
                if time.monotonic() - last_poll < 2:
                    continue
                last_poll = time.monotonic()
                response = client.get(f"/history/{prompt_id}")
                response.raise_for_status()
                record = response.json().get(prompt_id)
                if not record:
                    continue
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    details = next((item[1] for item in reversed(status.get("messages", [])) if item[0] == "execution_error"), {})
                    raise ProviderError("Character training failed: " + str(details.get("exception_message", "Inspect ComfyUI history."))[-2000:])
                if not status.get("completed"):
                    continue
                results = record.get("outputs", {}).get("train", {}).get("openframe_training", [])
                if len(results) != 1:
                    raise ProviderError("ComfyUI completed without a unique character adapter receipt.")
                result = results[0]
                result["workflow"] = graph
                result["metadata"].update(provider="local", host_id=training_host_id(settings), prompt_id=prompt_id,
                                           compute_device="cuda", transport_seconds=time.monotonic() - started, weights_downloaded_to_host=False)
                on_progress(1, "Character adapter ready on the configured ComfyUI host")
                return result
        except BaseException:
            if prompt_id:
                _cancel_local(client, prompt_id)
            raise
        finally:
            if ws:
                ws.close()
