# Ming narration and Qwen word timing on your ComfyUI host

This is an optional **Linux or WSL2 NVIDIA CUDA** runtime on the machine running ComfyUI. The OpenFrame browser/backend need no model weights. A configured remote ComfyUI server is also supported through the Local ComfyUI connection. Hosted Comfy Cloud does not expose these custom nodes/models.

Keep speech dependencies isolated from ComfyUI. These are the same pinned source revisions used by the recorded CUDA speech/ASR runs; portability of this configurable installation still needs its own runtime check. Do not interpret file detection as successful synthesis or lip-sync/audio quality.

## Companion code

Keep the OpenFrame node pack under `ComfyUI/custom_nodes/openframe`. Copy the bundled `engine` directory (only `__init__.py`, `narration_models.py`, `narration_workflows.py`, `narration_runtime.py`) beside `ComfyUI/main.py`, or put the matching OpenFrame source root on the ComfyUI process's `PYTHONPATH`. Do not overwrite an unrelated existing Python package named `engine`.

## Isolated environments

On that CUDA host, choose a persistent installation directory. The following commands install code/dependencies, not model weights. Use Python3.12 and a CUDA-compatible PyTorch environment. The Ming upstream requirements install their own stack. The ASR environment may reuse CUDA PyTorch from a compatible base interpreter. Creating a child venv does not automatically inherit packages installed only inside another venv.

```sh
mkdir -p "$HOME/openframe-audio"
cd "$HOME/openframe-audio"
git init ming-source
cd ming-source
git remote add origin https://github.com/inclusionAI/Ming-3.0-tts.git
git fetch --depth 1 origin 9332fb9443325d4726ce02cefd4ec1c211df4079
git checkout FETCH_HEAD
cd ..
python3.12 -m venv ming-env
ming-env/bin/pip install -r ming-source/requirements.txt pynini==2.1.6

git init asr-source
cd asr-source
git remote add origin https://github.com/QwenLM/Qwen3-ASR.git
git fetch --depth 1 origin 7c6daf77a2421100f5fb066495372c00129d39ff
git checkout FETCH_HEAD
cd ..
# If base Python has CUDA PyTorch, --system-site-packages reuses it.
python3.12 -m venv --system-site-packages asr-env
asr-env/bin/pip install --no-deps ./asr-source
asr-env/bin/pip install transformers==4.57.6 accelerate==1.12.0 nagisa==0.2.11 soynlp==0.0.493 qwen-omni-utils librosa soundfile sox pytz
```

If ASR does not already have CUDA PyTorch, install the matched PyTorch/torchaudio pair into `asr-env` using the official PyTorch instructions for this host’s driver. The recorded ASR environment used PyTorch2.10.0; a different platform/driver needs its own verification. Do not expect CPU-only wheels to run this profile.

Install FFmpeg on this host. Obtain only the files listed in the exported `MODEL-REQUIREMENTS.json`, retaining its exact repository revision, category, filename, size and published SHA256. Synthesis uses `models/tts/ming3`; recognition and alignment use `models/asr/qwen3` and `models/asr/qwen3-aligner`. Recognition is optional for a speech-only graph. Ming code/weights are MIT; Qwen ASR/aligner are Apache2.0. Upstream licenses apply independently of OpenFrame.

Set these variables in the environment that launches ComfyUI:

```sh
export OPENFRAME_MING_PYTHON="$HOME/openframe-audio/ming-env/bin/python"
export OPENFRAME_MING_SOURCE="$HOME/openframe-audio/ming-source"
export OPENFRAME_ASR_PYTHON="$HOME/openframe-audio/asr-env/bin/python"
# Optional: defaults to the configured ComfyUI models directory.
# export OPENFRAME_MODEL_CACHE=/absolute/path/to/ComfyUI/models
```

Restart ComfyUI and check its connection from OpenFrame. `OpenFrameSequenceNarration.request_json` reports separate synthesis and caption readiness based on CUDA, configured interpreter/source paths and exact manifest file sizes. The node validates selected dependencies before running, unloads Comfy models, invokes the isolated child with offline model settings, observes cancellation and a30-minute bound, and records actual model/code revisions, audio SHA and recognized timing. It never downloads weights at execution.

## App behavior

Ads can reuse a completed video and a real recording, then assemble captions/music without generating the video again. A shorter foreground recording needs explicit silence-padding consent; it is never silently looped. A generated narration must fit its shot; shorten the script or change its explicit speed if it does not. The selected episode speech/caption connection is persisted; saved unavailable provider choices fail explicitly and must be changed before a new run. New sequences choose the displayed current connection. No provider/model is silently substituted.
