# Local Qwen3.8 visual planning

This optional runtime runs on your configured **Linux or WSL2 NVIDIA CUDA ComfyUI host**, not on the lightweight app computer. It uses the same Qwen3.8-27B implementation as the existing visual planner. It does not use Comfy Cloud, require a rented-worker account, or substitute a smaller model. Native Windows and CPU visual inference are not supported by this runtime.

## Install on the CUDA host

Use the matching OpenFrame source checkout and compatible ComfyUI CUDA environment. Keep the complete `engine/` package importable by ComfyUI and the isolated interpreter; for example, add the OpenFrame checkout root to `PYTHONPATH`. The node starts its child with that same package root. Do not copy only `planner.py`, since the existing model manifests and reference-analysis helpers are also required.

Install the node pack and reuse/provision the exact planner files on this host:

```sh
python -m engine.setup --comfy-dir /path/to/ComfyUI --model qwen3.8-planner
```

Use `--no-download` if the declared files are already present. `engine/analysis_models.py` declares all 28 files, expected sizes and revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` of `Qwen/Qwen3.8-27B` (Apache-2.0). Total model files are 55,586,036,499 bytes. Reuse an existing cache; do not download them onto the lightweight app computer. BF16 model weights plus activations require a suitably large CUDA GPU; the existing private proof used an H100 80 GB, which is evidence of that configuration, not a minimum-memory claim.

Create an isolated environment using the compatible ComfyUI CUDA Python as the base. The following changes only the isolated environment, not ComfyUI's Transformers installation:

```sh
/path/to/ComfyUI/.venv/bin/python -m venv --system-site-packages /path/to/openframe-planner
/path/to/openframe-planner/bin/python -m pip install 'transformers==5.22.0'
export OPENFRAME_VISUAL_PLANNER_PYTHON=/path/to/openframe-planner/bin/python
export OPENFRAME_VISUAL_PLANNER_MODEL_DIR=/path/to/ComfyUI/models/planning/qwen3.8-27b
export PYTHONPATH=/path/to/openframe${PYTHONPATH:+:$PYTHONPATH}
```

The child also needs the existing compatible CUDA Torch, Pillow, and FFmpeg/FFprobe. Inheriting a known-compatible CUDA environment avoids reinstalling its large Torch packages. Configure these variables in the process that starts ComfyUI, then restart that host. No model downloads occur during planning.

## Capability and execution

`OpenFrameVisualPlanner` reports the exact model's file-size presence, Linux CUDA availability and configured executable in its `request_json` input metadata. This is a prerequisite check, not proof that dependencies or output quality work. The app queries this from the configured ComfyUI URL and auth settings. Choose **Local ComfyUI / Qwen3.8 27B** explicitly. The optional legacy Qwen2.5 CPU text planner is a separately labelled choice and never an automatic fallback.

The app uploads only selected reference media to ComfyUI input, submits one planner graph through the normal Comfy queue, and retrieves its structured proposal from history. Images are analyzed at up to 448 pixels per side; each video is limited to five minutes and at most 16 sampled frames. Audio is not analyzed. The original reference hashes, sampling timestamps, observations, exact model revision, host identity hash and submitted graph are recorded with the proposal. Planning does not submit image/video generation: review and approve the proposed shots separately.

The node unloads Comfy models before the isolated planner starts, and the planner process exits after the proposal. The existing bounded execution budget and strict JSON validation apply. Cancellation deletes the queued prompt or interrupts this running prompt using the existing Comfy cancellation path; the node terminates its child. A failed or interrupted proposal is not replaced with a preset. Reconnect to the same Comfy host to inspect its history if cancellation could not be confirmed.
