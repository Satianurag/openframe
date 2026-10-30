# Character training on your ComfyUI GPU host

This runs the existing `OpenFrameTrainCharacter` graph on a configured **Linux
CUDA ComfyUI host**. The studio may run on a separate lightweight computer.
Connect through Local ComfyUI; no provider-specific SDK is required.
Direct Comfy Cloud and native macOS/Windows training are not supported by this
runtime. Linux under WSL still needs its own compatible CUDA environment.

Training is private and explicit. It uploads 20–50 photographs to your selected
ComfyUI input directory and trains the undistilled FLUX3 Klein Base checkpoint.
It does not train from unrelated faces or silently substitute reference-image
conditioning. Use a coherent identity dataset with permission to process it.

## Reuse the released, pinned trainer

The upstream implementation is Hugging Face Diffusers at
[`aae97e79e8e6a55e0b43114f9c8916c06d4bca8c`](https://github.com/huggingface/diffusers/tree/aae97e79e8e6a55e0b43114f9c8916c06d4bca8c):

- `examples/dreambooth/train_dreambooth_lora_flux3_klein.py`
- `examples/dreambooth/requirements_flux3_klein.txt`
- `examples/dreambooth/README_flux3_klein.md`

The trainer source must have SHA256
`89cc2ff1af1909c1652deefdee7a60e589c3d4e7169d22ab7e05e3ca0c49be72`.
OpenFrame verifies this before its small recorded adaptation: load the existing
native base in memory, disable external logging, and emit bounded progress and
checkpoint notices. Training/sampling algorithms are not replaced. Diffusers is
Apache-2.0; base weights are under FLUX Kommunity License 1.0. Its commercial-output
exception is not a blanket commercial fine-tuning license. Retain upstream terms.

## Explicit GPU-host setup

Reuse a compatible existing checkout, Python3.12 CUDA environment and model cache.
Otherwise create an isolated training environment on that host. The application's
historical training proof used an H100; this guide does not claim a smaller GPU
will fit every supported resolution/rank. Do not install this stack on the
lightweight Mac/browser host merely to enable a UI control.

Check out the exact Diffusers commit above, then use the following paths as
placeholders for your existing installations:

```sh
python3.12 -m venv --system-site-packages /path/to/training-env
/path/to/training-env/bin/python -m pip install --no-deps /path/to/pinned-diffusers
/path/to/training-env/bin/python -m pip install -r /path/to/pinned-diffusers/examples/dreambooth/requirements_flux3_klein.txt
/path/to/training-env/bin/python -m pip install --no-deps -e /path/to/openframe-source
/path/to/ComfyUI/python -m pip install --no-deps -e /path/to/openframe-source
```

`--system-site-packages` assumes the base interpreter already supplies a compatible
CUDA PyTorch. If it does not, install the matched CUDA PyTorch/torchvision pair in
the isolated environment following PyTorch's instructions for that GPU host.
The pinned trainer requirements supply the required Diffusers training packages;
never install them into ComfyUI's shared environment as an accidental upgrade.
The editable OpenFrame package provides engine helpers, with no dependency
reinstallation. Use the actual ComfyUI interpreter path instead of the placeholder.

A portable training bundle contains `engine/` but is not an installable source
checkout. For that bundle, omit the two editable OpenFrame installs and put its
extracted root on the Python path before starting ComfyUI:

```sh
export PYTHONPATH=/path/to/extracted-training-bundle
```

The trainer child inherits this path, so both processes can import the bundled
engine. Do not add another environment's `site-packages` to `PYTHONPATH`; that
would bypass the isolated runtime. Keep the extracted source and relocated
training inputs available until the job completes. The pinned Diffusers/runtime
setup and model requirements remain the same.

Provision only the selected profile **on the GPU host**:

```sh
python -m engine.setup --comfy-dir /path/to/ComfyUI --model flux3-character-training
```

The model manifest pins the base native file (SHA256
`5c921759dc03663dbb67df11d8e3d317d2d5b893b31b969c95dc77ebf861b19c`),
text encoder, tokenizer, VAE and model configurations. Existing matching files
are reused. Authenticate normally with Hugging Face and obtain gated-model access
before this explicit provisioning step. Training itself runs offline and never
downloads missing weights. Use `--no-download` to install node files only.

Before starting ComfyUI, set:

```sh
export OPENFRAME_TRAINING_PYTHON=/path/to/training-env/bin/python
export OPENFRAME_TRAINER_SOURCE=/path/to/pinned-diffusers
```

The node obtains its model root from ComfyUI's `folder_paths.models_dir`.
Restart ComfyUI with the configured environment above, choose its endpoint in studio Settings and check
the Local connection. Training availability reflects the runtime/source paths,
CUDA host and required files; package compatibility is additionally checked when
the process actually runs. This source addition is not a new Local inference proof.

## Bounds, cancellation and adapter ownership

- 20–50 distinct still PNG/JPEG/WebP images, minimum side256px, ≤40MP/image,
  ≤32MiB/image, ≤500MP and ≤512MiB total.
- 500–3000 steps, resolution512/768/1024, rank16/32, BF16 base, rank=alpha,
  gradient checkpointing, cached latents, CPU offload and8-bit Adam.
- Six-hour execution budget, checkpoints every500steps, at most two retained
  optimizer checkpoints; progress updates every25steps. No automatic retry or
  automatic checkpoint resume.
- Cancellation deletes this queued prompt or interrupts it only when running.
  The training node terminates its child process and retains completed host
  checkpoints. Uploaded inputs and useful training artifacts are not bulk-deleted.
- The durable registry saves provider, prompt ID and a hash of the Comfy endpoint.
  It never downloads the LoRA onto the UI/API host. Changing endpoints cannot
  silently redirect an existing registered adapter.

Adapters remain at `models/loras/openframe/<job-id>/character.safetensors`.
Use the ready character in Image Studio with the matching **undistilled FLUX3
Base** profile, provisioning that inference profile separately on the same host.
Local inference verifies the registered LoRA SHA256 before native loading.
Distilled models, arbitrary adapter paths and cross-provider reuse are rejected.
The full inference workflow/bundle records the required adapter path and hash;
private adapter bytes are not included automatically.

The generated result still needs visual identity/action review. A successful
training process and a valid LoRA file do not prove identity generalization.

### Opt-in reviewed spatial loss masks

The unchanged default trains the full image. An advanced training request may supply `loss_mask_asset_ids`, ordered one-to-one with `dataset_asset_ids`. The portable `OpenFrameTrainCharacter` node carries these filenames in optional `loss_masks_json`; omitting it preserves the original graph and loss. Use upright photographs and matching, single-frame grayscale PNG masks at the photograph's exact dimensions. White identifies the reviewed region; black retains an outside loss weight of0.1. Include the entire jaw, ears and hair for head-focused experiments. Masks must retain at least1% support after the actual training crop.

This adaptation reuses Fizgig's Apache-2.0 spatial weighting at revision `6fb10a3bc2f70c8d664262fb48358edbf505788b` (`src/fizgig/families/driver.py`, `flux3/driver.py`, `dataset/masks.py`). See `docs/licenses/Fizgig-LICENSE.txt` in the source distribution and the accompanying bundle license. The existing Diffusers velocity target, captions, crop RNG and timestep weighting remain unchanged. Masks replay the image's exact crop/flip, resize to its packed latent token grid using area averaging, clamp weights to0.1–1, and normalize spatial weights to mean1 per image. This is loss weighting, not a face-recognition objective or a guarantee of likeness. The resulting manifest records mask/photo hashes, transformed-mask geometry/hashes, outside weight and source pin.
