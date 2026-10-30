# Official SAM3.1 runtime for Recast and semantic video matte

This is an optional runtime **on the CUDA ComfyUI host**, not on the lightweight
browser/API laptop. Connect through Local ComfyUI using the explicit setup below.
Native SCAIL-2 generation remains a normal pinned ComfyUI workflow. Official
Recast tracking changes only its final compositing support; its generation
conditioning remains native SAM3.1. A deliberate painted performer override uses
native support instead.

## Supported execution boundary

The isolated transport uses Linux anonymous memory files (`memfd_create`), with
no decoded-frame disk cache. Use a Linux CUDA ComfyUI host. A Linux environment
under WSL must itself have working CUDA and the listed packages; native Windows
and macOS execution of this helper is not claimed. No heavy runtime is installed
automatically on the application host.

The pinned [official SAM3 README](https://github.com/facebookresearch/sam3/blob/f1647e8d0c1d280991f4d1b7d974c2704537fe66/README.md#installation)
specifies Python3.12+, PyTorch2.7+, and CUDA12.6+; its installation example uses
PyTorch2.10/CUDA12.8. The app's isolated dependency set below matches its recorded CUDA
validation environment. Other driver/platform combinations require their own
verification; a present interpreter path is not an inference-quality claim.

## Explicit setup

Reuse a suitable existing isolated environment and model cache when available.
Otherwise create an isolated **Python3.12** environment on the GPU host. If its
base interpreter already has a compatible CUDA PyTorch, `--system-site-packages`
can reuse it. Do not alter ComfyUI's own NumPy/Transformers installation.

```sh
python3.12 -m venv --system-site-packages /path/to/openframe-sam3-runtime
/path/to/openframe-sam3-runtime/bin/python -m pip install \
  setuptools==80.9.0 numpy==1.26.4 transformers==4.57.1 \
  huggingface-hub==0.36.0 opencv-python-headless==4.11.0.86 \
  timm==1.0.17 ftfy==6.1.1 iopath==0.1.10 pycocotools==2.0.10 \
  scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3 \
  pillow einops tqdm regex typing_extensions safetensors
/path/to/openframe-sam3-runtime/bin/python -m pip install --no-deps \
  git+https://github.com/facebookresearch/sam3.git@f1647e8d0c1d280991f4d1b7d974c2704537fe66
```

If that interpreter does not already contain compatible CUDA PyTorch/torchvision,
install the matched upstream pair into this isolated environment using the
official PyTorch instructions for the host's driver. Do not install CPU-only
PyTorch and expect this graph to run. No package install commands run during
workflow execution.

Supply the approved official checkpoint at
`ComfyUI/models/matting/sam3.1/sam3.1_multiplex.pt`:

- Repository `facebook/sam3.1`, revision `daa63191845a41281374e725f4c9e51c7a824460`.
- File `sam3.1_multiplex.pt`,3,502,755,717bytes.
- SHA256 `0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`.
- Obtain upstream access and comply with the SAM License. Weights are not bundled.

From the full OpenFrame source, the explicit model installer can reuse/download
only the chosen profile's missing files on that GPU host:

```sh
python -m engine.setup --comfy-dir /path/to/ComfyUI --model scail-2 --recast-composite-tracking official
```

The default `--model scail-2` installs native requirements only. Official Recast
does **not** use or require ViTMatte. The separate semantic video-background
remover also needs its three pinned `matting/vitmatte/` files; use the full
`sam3.1-vitmatte` profile and its exported model manifest for that app. Its alpha
refinement remains independent per frame.

Before starting ComfyUI, configure the interpreter on the ComfyUI host:

```sh
export OPENFRAME_SAM3_PYTHON=/path/to/openframe-sam3-runtime/bin/python
# Start ComfyUI normally in this environment's shell.
```

Restart ComfyUI after installing the current OpenFrame node pack, then check the
Local connection in the studio's Settings. The capability check reports runtime
path/checkpoint/CUDA-host prerequisites; actual package imports and GPU execution
remain runtime checks. Missing prerequisites fail before the app uploads or
queues this graph. Saved official-support settings are never silently downgraded.

## Behavior and limitations

The official predictor uses the source frames, concept `person`, threshold0.5,
and matches the native first-frame performer at IoU≥0.5. That selected instance ID
is retained; a bystander is never silently substituted. Unmatched first frames
fail clearly. Native conditioning masks, model, DPO adapter and sampler remain
unchanged. The exported mask is the actual margin/feathered final support, not
the native conditioning segmentation. Fine hand anatomy, held-object detail and
generated garment boundaries still require review.

New configured jobs can select `official-union` (the setup flag accepts the same
name and provisions the identical checkpoint). This adds a second official pass
over the decoded generated performer, matched independently against the same
native first-frame source identity. Final support is the union of native source,
official source and matched generated-person masks, followed by the existing
margin and feather once. It protects wider generated clothes/shoes and retains
native coverage when official source tracking loses part of a person. It does
not alter SCAIL conditioning, repair raw generated anatomy/halos, or replace the
whole scene. Both passes must meet the first-frame IoU guard; no unrelated actor
is selected as a fallback. Per-frame areas, matched IDs, model pins and source /
generated RGB hashes are recorded. ViTMatte is not used for this support mode.

Saved `native` and `official` graphs retain their original behavior. A deliberate
manual mask still requires native support. The Local capability check exposes
`official-union` only when the updated node has its optional `generated_images`
input and the isolated runtime prerequisites are present. Update nodes and check
the connection again before selecting this mode on an older installation.

The wrapper unloads Comfy models before the isolated pass, operates offline,
checks cancellation while reading progress, and terminates the child process on
cancellation/error/one-hour timeout. The Linux memory files close on completion.
Frames are not written to disk by this transport. The original source/registered
results and the rejected historical comparisons remain unchanged.

The prior hand-support repair was established using existing decoded output and
65 tracked frames; that is not a new public-Local end-to-end validation. Fresh
application validation must use the current selected source/reference and inspect
all final/raw/mask frames before claiming a quality pass.
