"""Optional exact SAM2 tracking through the configured local ComfyUI runtime.

Only masks are computed here. The video diffusion graph still executes on
hosted Comfy Cloud. No point/bounding-box approximation of the painted mask.
"""
from pathlib import Path
import io
import json
import time
import uuid

import httpx
import numpy as np
from PIL import Image


def tracker_status(settings):
    from .runner import _url
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    try:
        response = httpx.get(url + "/object_info/OpenFrameVideoInput", headers=headers, timeout=5)
        response.raise_for_status()
        spec = response.json().get("OpenFrameVideoInput", {}).get("input", {})
        fields = {**spec.get("required", {}), **spec.get("optional", {})}
        options = fields.get("tracking_method", [None, {}])
        metadata = options[1] if len(options) > 1 else {}
        available = bool(metadata.get("openframe_sam2_available") and metadata.get("openframe_sam2_checkpoint") == "sam2.1_hiera_small.pt")
        return {"available": available, "checkpoint": "sam2.1_hiera_small.pt", "detail":
            "Configured local ComfyUI reports the SAM2 package and exact SAM2.1 small checkpoint. Tracking uses add_new_mask; runtime execution is checked per job."
            if available else "Configure local ComfyUI with the current OpenFrame nodes, SAM2 package and sam2.1_hiera_small.pt; no tracker substitution will be made."}
    except (httpx.HTTPError, ValueError):
        return {"available": False, "detail": "The configured local ComfyUI tracker is unavailable. Connect it in Settings or select static/optical-flow tracking."}


def track(request, assets, output_dir, settings, progress, cancel):
    from .runner import ProviderError, _cancel_local, _url
    status = tracker_status(settings)
    if not status["available"]:
        raise ProviderError("Cloud SAM2 requires exact local tracking: " + status["detail"])
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    ident = None; terminal = False
    with httpx.Client(base_url=_url(settings.get("comfy_url", "http://127.0.0.1:8188")), headers=headers, timeout=120) as client:
        filenames = {}
        for role in ("source", "mask"):
            cancel(); progress(.02, "Uploading " + role + " to local SAM2 tracker")
            path = Path(assets[role])
            with path.open("rb") as file:
                response = client.post("/upload/image", files={"image": ("openframe_tracker_" + request["job_id"] + "_" + role + path.suffix.lower(), file)}, data={"type": "input", "overwrite": "false"})
            response.raise_for_status(); item = response.json()
            filenames[role] = "/".join(x for x in (item.get("subfolder", ""), item["name"]) if x)
        graph = {
            "source": {"class_type": "OpenFrameVideoInput", "inputs": {
                "filename": filenames["source"], "mask_filename": filenames["mask"],
                "width": request["width"], "height": request["height"], "frames": request["frames"], "fps": request["fps"],
                "trim_start": request.get("trim_start", 0), "track_mask": True, "tracking_method": "sam2",
                "mask_dilation": 0, "mask_feather": 0, "edit_margin": 0, "feather_method": "smooth-inward"}},
            "mask_image": {"class_type": "MaskToImage", "inputs": {"mask": ["source", 1]}},
            "save": {"class_type": "SaveImage", "inputs": {"images": ["mask_image", 0], "filename_prefix": "openframe-tracker/" + request["job_id"]}},
        }
        cancel()
        response = client.post("/prompt", json={"prompt": graph, "client_id": uuid.uuid4().hex})
        if response.status_code >= 400:
            raise ProviderError("Local SAM2 tracker rejected its mask-only graph: " + response.text[:1200])
        ident = response.json()["prompt_id"]
        (output_dir / "tracker-job.json").write_text(json.dumps({"prompt_id": ident, "provider": "configured-local-comfy", "workflow": graph}))
        try:
            start = time.monotonic()
            while True:
                cancel(); progress(.03, "Tracking painted mask with local SAM2.1; Cloud diffusion has not started")
                response = client.get("/history/" + ident); response.raise_for_status()
                record = response.json().get(ident)
                if record:
                    if record.get("status", {}).get("status_str") == "error":
                        terminal = True
                        errors = record["status"].get("messages", [])
                        detail = next((m[1].get("exception_message") for m in reversed(errors) if m[0] == "execution_error"), "Unknown tracker failure")
                        raise ProviderError("Local SAM2 tracking failed: " + str(detail)[:1200])
                    if record.get("status", {}).get("completed"):
                        terminal = True
                        break
                if time.monotonic() - start > 1800:
                    raise ProviderError("Local SAM2 tracking exceeded30minutes; no Cloud diffusion was submitted.")
                time.sleep(1)
            items = record.get("outputs", {}).get("save", {}).get("images", [])
            if len(items) != request["frames"]:
                raise ProviderError("Local SAM2 returned an incomplete mask sequence; no Cloud diffusion was submitted.")
            masks = []
            for item in items:
                cancel()
                response = client.get("/view", params={"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as image:
                    if image.size != (request["width"], request["height"]):
                        raise ProviderError("Local SAM2 returned unexpected mask dimensions")
                    masks.append((np.asarray(image.convert("L")) >= 128).astype(np.float32))
            return np.stack(masks), {"provider": "configured-local-comfy", "prompt_id": ident, "checkpoint": status["checkpoint"],
                "initialization": "add_new_mask", "workflow": graph, "seconds": time.monotonic() - start,
                "note": "Exact SAM2 propagation only. Edit margin, generation dilation and final feather are applied once by the shared host helper after tracking."}
        except BaseException:
            if ident and not terminal:
                _cancel_local(client, ident)
            raise
