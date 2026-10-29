"""Deploy: modal deploy deploy/modal_app.py

All diffusion happens inside pinned ComfyUI. Model weights live on a persistent
Modal Volume; media moves through a second Volume without oversized RPC payloads.
"""
from pathlib import Path
import os
import modal

ROOT = Path(__file__).resolve().parents[1]
COMFY_SHA = "79cf64c21a1dba50749945ba9fe2e3a692f45438"
LTX_SHA = "220e1d45aa0469f518e982102fca4dca92a61862"
APP_NAME = os.environ.get("OPENFRAME_MODAL_APP", "openframe-comfy")
app = modal.App(APP_NAME)
models = modal.Volume.from_name("openframe-models", create_if_missing=True)
media = modal.Volume.from_name("openframe-assets", create_if_missing=True)
progress = modal.Dict.from_name("openframe-progress", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install("torch==2.10.0", "torchvision==0.25.0", "httpx>=0.28,<1", "websocket-client>=1.8,<2", "huggingface-hub>=0.36,<2", "opencv-python-headless>=4.10,<5")
    .env({"SAM2_BUILD_CUDA": "0"})
    .pip_install("git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4")
    .run_commands(
        f"git init /opt/ComfyUI && cd /opt/ComfyUI && git remote add origin https://github.com/Comfy-Org/ComfyUI.git && git fetch --depth 1 origin {COMFY_SHA} && git checkout FETCH_HEAD",
        f"git init /opt/ComfyUI/custom_nodes/ComfyUI-LTXVideo && cd /opt/ComfyUI/custom_nodes/ComfyUI-LTXVideo && git remote add origin https://github.com/Lightricks/ComfyUI-LTXVideo.git && git fetch --depth 1 origin {LTX_SHA} && git checkout FETCH_HEAD",
        "pip install -r /opt/ComfyUI/requirements.txt -r /opt/ComfyUI/custom_nodes/ComfyUI-LTXVideo/requirements.txt",
    )
    .add_local_dir(ROOT / "engine", "/opt/openframe/engine", copy=True)
    .add_local_dir(ROOT / "custom_nodes/openframe", "/opt/ComfyUI/custom_nodes/openframe", copy=True)
    .env({"PYTHONPATH": "/opt/openframe", "HF_HOME": "/models/huggingface", "HF_HUB_ENABLE_HF_TRANSFER": "0", "HF_XET_HIGH_PERFORMANCE": "1"})
)


@app.function(image=image, volumes={"/models": models}, secrets=[modal.Secret.from_name(os.environ["OPENFRAME_HF_SECRET"])] if os.environ.get("OPENFRAME_HF_SECRET") else [], timeout=7200, cpu=4, memory=16384)
def prepare_models(model_ids: list[str] = ["ltx-0.9.8", "ltx-2.3", "wan-vace", "sam2"], include_inpaint: bool = True):
    """Download once on CPU, never on the user's laptop or a billed GPU."""
    from engine.models import download_model
    result = {}
    try:
        for model_id in model_ids:
            result[model_id] = download_model(model_id, Path("/models/comfy"), Path("/models/huggingface/hub"), progress=lambda _, stage: print(stage, flush=True), task=None if include_inpaint else "text-to-video")
            models.commit()
    finally:
        # Keep completed files reusable if a later gated file or network call fails.
        models.commit()
    return result


_COMFY = None


def _start_comfy():
    import subprocess
    import time
    import httpx
    global _COMFY
    if _COMFY is not None and _COMFY.poll() is None:
        return
    _COMFY = subprocess.Popen(["python", "main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch", "--preview-method", "none"], cwd="/opt/ComfyUI")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if _COMFY.poll() is not None:
            raise RuntimeError("ComfyUI exited during startup; inspect Modal logs for missing dependencies.")
        try:
            if httpx.get("http://127.0.0.1:8188/system_stats", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("ComfyUI startup timed out.")


def _stop_comfy():
    import subprocess
    global _COMFY
    if _COMFY is not None and _COMFY.poll() is None:
        _COMFY.terminate()
        try:
            _COMFY.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _COMFY.kill()
            _COMFY.wait(timeout=10)
    _COMFY = None


@app.function(image=image, gpu=os.environ.get("OPENFRAME_MODAL_GPU", "H100"), cpu=8, memory=131072, volumes={"/models": models, "/assets": media}, timeout=7200, scaledown_window=120, max_containers=1)
def render(request: dict, assets: dict, job_id: str):
    """The public worker interface used by engine.runner; serial per GPU."""
    import time
    from engine.models import MODEL_FILES
    from engine.runner import _run_local
    from engine.workflows import normalize_request
    if not job_id.replace("-", "").isalnum():
        raise ValueError("Invalid job identifier")
    media.reload()
    normalized = normalize_request(request)
    normalized["job_id"] = job_id
    normalized["provider"] = "local"
    last_update = [0.0, -1.0, ""]
    def report(value, stage):
        now = time.monotonic()
        value = max(last_update[1], float(value))
        if stage != last_update[2] or value - last_update[1] >= .025 or now - last_update[0] >= 15:
            progress[job_id] = {"progress": value, "stage": stage}
            print(f"[{job_id}] {value:.0%} {stage}", flush=True)
            last_update[:] = [now, value, stage]
    report(.03, "Loading cached model profile")
    comfy = Path("/opt/ComfyUI")
    # A new profile must be provisioned on CPU before generation; no hidden GPU downloads.
    entries = [entry for entry in MODEL_FILES[normalized["model_id"]] if not entry.get("tasks") or normalized["task"] in entry["tasks"]]
    mask_is_video = Path(str(assets.get("mask", ""))).suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}
    if normalized["task"] == "inpaint" and normalized["mask_tracking_method"] == "sam2" and not mask_is_video:
        entries += MODEL_FILES["sam2"]
    # Comfy retains mmap file handles while its model cache is warm. Reloading a
    # Volume then fails. Refresh only for a newly provisioned profile, after
    # closing that process; ordinary repeated jobs retain their warm models.
    if any(not (Path("/models/comfy/models") / entry["category"] / Path(entry["file"]).name).exists() for entry in entries):
        _stop_comfy()
        models.reload()
    for entry in entries:
        cached = Path("/models/comfy/models") / entry["category"] / Path(entry["file"]).name
        if not cached.exists():
            raise RuntimeError(f"Model cache missing {cached.name}. Run: modal run deploy/modal_app.py --prepare --model {normalized['model_id']}")
        destination = comfy / "models" / entry["category"] / cached.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.symlink_to(cached)
    report(.04, "Starting ComfyUI")
    _start_comfy()
    resolved_assets = {}
    for role, path in assets.items():
        candidate = (Path("/assets") / str(path).lstrip("/")).resolve()
        if not candidate.is_relative_to((Path("/assets/jobs") / job_id / "input").resolve()) or not candidate.is_file():
            raise ValueError("Invalid source asset path")
        resolved_assets[role] = str(candidate)
    output_dir = Path("/assets/jobs") / job_id / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        result = _run_local(normalized, resolved_assets, output_dir, {"comfy_url": "http://127.0.0.1:8188"}, report, lambda: False)
        for item in result["outputs"]:
            item["path"] = "/" + str(Path(item["path"]).relative_to("/assets"))
        result["metadata"].update(provider="modal", comfy_commit=COMFY_SHA, ltx_nodes_commit=LTX_SHA, gpu=__import__("torch").cuda.get_device_name(0), seconds=time.monotonic() - started)
        media.commit()
        report(1, "Complete")
        return result
    except Exception as exc:
        report(last_update[1], "Failed: " + str(exc)[:400])
        raise
    finally:
        # Remove only input/output copies created by this job in ephemeral Comfy storage.
        for folder in [comfy / "input", comfy / "output/openframe"]:
            if folder.exists():
                for path in folder.iterdir():
                    if path.is_file() and job_id in path.name:
                        path.unlink(missing_ok=True)


@app.local_entrypoint()
def main(prepare: bool = False, model: str = "ltx-0.9.8", base_only: bool = False):
    if prepare:
        print(prepare_models.remote([model, "sam2"] if model in {"ltx-2.3", "wan-vace"} and not base_only else [model], include_inpaint=not base_only))
    else:
        print("Deploy with: modal deploy deploy/modal_app.py")
        print("Provision weights on CPU: modal run deploy/modal_app.py --prepare --model ltx-0.9.8")
        print("Then start the OpenFrame app and select Modal GPU.")
