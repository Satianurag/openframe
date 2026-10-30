"""Direct ComfyUI transport for the existing Qwen3.8 visual planner."""
import hashlib
import json
from pathlib import Path
import time
import uuid

from .analysis_models import ANALYSIS_MODEL_ID


def visual_planner_status(settings):
    import httpx
    from .runner import _url
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    try:
        with httpx.Client(base_url=_url(settings.get("comfy_url", "http://127.0.0.1:8188")), headers=headers, timeout=3) as client:
            response = client.get("/object_info/OpenFrameVisualPlanner")
            response.raise_for_status()
            options = response.json().get("OpenFrameVisualPlanner", {}).get("input", {}).get("required", {}).get("request_json", [])
            status = options[1].get("openframe_visual_planner", {}) if len(options) > 1 else {}
            if status.get("model_id") != ANALYSIS_MODEL_ID:
                return {"available": False, "detail": "Install the pinned OpenFrameVisualPlanner node/runtime on the configured ComfyUI CUDA host."}
            return {"available": status.get("available") is True, "detail": status.get("detail", "Configured visual planner")}
    except Exception:
        return {"available": False, "detail": "The configured ComfyUI visual planner is unavailable. See PLANNER-RUNTIME.md; no smaller model or other provider is substituted."}


def plan_comfy(request, settings, on_progress, is_cancelled, on_submitted, references):
    import httpx
    from .runner import _url, _cancel_local
    from .planner import PlanningError
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    status = visual_planner_status(settings)
    if not status["available"]:
        raise PlanningError(status["detail"])
    if {item["asset_id"] for item in references} != set(request["reference_asset_ids"]):
        raise PlanningError("Every selected planning reference must be supplied.")
    prompt_id = None
    with httpx.Client(base_url=url, headers=headers, timeout=120) as client:
        uploaded = []
        for reference in references:
            if is_cancelled():
                raise PlanningError("Planning cancelled before reference upload.")
            path = Path(reference["path"])
            with path.open("rb") as handle:
                response = client.post("/upload/image", files={"image": (f"plan-{uuid.uuid4().hex}{path.suffix.lower()}", handle, "application/octet-stream")}, data={"type": "input"})
            response.raise_for_status()
            value = response.json()
            uploaded.append({"asset_id": reference["asset_id"], "kind": reference["kind"],
                             "filename": str(Path(value.get("subfolder", "")) / value["name"])})
        if is_cancelled():
            raise PlanningError("Planning cancelled before submission.")
        graph = {"plan": {"class_type": "OpenFrameVisualPlanner", "inputs": {
            "request_json": json.dumps(request, ensure_ascii=False), "references_json": json.dumps(uploaded)}}}
        response = client.post("/prompt", json={"prompt": graph, "client_id": uuid.uuid4().hex})
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        try:
            on_submitted({"provider": "local", "prompt_id": prompt_id,
                          "host_id": hashlib.sha256(url.rstrip("/").encode()).hexdigest()})
            deadline = time.monotonic() + request["budget_seconds"] + 60
            on_progress(.02, "Awaiting the visual proposal from the configured ComfyUI CUDA host")
            while time.monotonic() < deadline:
                if is_cancelled():
                    raise PlanningError("Planning cancelled.")
                response = client.get(f"/history/{prompt_id}")
                response.raise_for_status()
                history = response.json().get(prompt_id)
                if history:
                    status = history.get("status", {})
                    if status.get("status_str") == "error":
                        messages = status.get("messages", [])
                        error = next((item[1] for item in reversed(messages) if item[0] == "execution_error"), {})
                        raise PlanningError("Comfy visual planning failed: " + str(error.get("exception_message", "Inspect ComfyUI history"))[-2000:])
                    proposals = history.get("outputs", {}).get("plan", {}).get("openframe_plan", [])
                    if proposals:
                        result = proposals[0]
                        if not isinstance(result, dict) or not isinstance(result.get("episodes"), list) or len(result["episodes"]) != request["episodes"]:
                            raise PlanningError("The planner returned no complete proposal.")
                        result.setdefault("metadata", {}).update(provider="local", prompt_id=prompt_id,
                            host_id=hashlib.sha256(url.rstrip("/").encode()).hexdigest(), workflow=graph)
                        return result
                    if status.get("completed"):
                        raise PlanningError("ComfyUI completed without a visual proposal; no fallback was used.")
                time.sleep(.5)
            raise PlanningError("Visual planning exceeded its recorded execution budget.")
        except BaseException:
            try:
                _cancel_local(client, prompt_id)
            except Exception as error:
                raise PlanningError(f"Planning failed and cancellation of Comfy prompt {prompt_id} could not be confirmed.") from error
            raise
