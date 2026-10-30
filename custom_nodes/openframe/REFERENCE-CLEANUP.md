# Reference edge cleanup

`OpenFrameReferenceForeground` prepares a single character reference for SCAIL-2.
It uses the native identity mask, a fixed 12px trimap, CPU ViTMatte and the released
MIT PyMatting foreground-color solver, then premultiplies the recovered foreground
onto black. The original reference still feeds CLIP and native SAM selection.
This operation changes only the reference RGB supplied to the video VAE.

Install the node requirements in **ComfyUI's Python environment**, including
`numba==0.61.2`. This requires NumPy below 2.3; review compatibility with other
installed node packs before changing an existing environment. Transformers and
PyTorch come from the pinned ComfyUI environment. There is no runtime installer
or automatic model download.

Put these files from `hustvl/vitmatte-base-composition-1k`, revision
`bf486d01a7d9e3dbcc8400f7942835caf0eaf76e`, in `models/matting/vitmatte/`:

- `pytorch_model.bin` (386,836,309 bytes; SHA256
  `b2521bcc4b719fb24611c39605b6642162fd7502e69b3cc846506ca921757b41`)
- `config.json`
- `preprocessor_config.json`

The application setup CLI includes these files when called with
`--model scail-2 --recast-reference-cleanup`. Exported `MODEL-REQUIREMENTS.json`
lists their exact sources and destinations. Existing files/caches are reused.
Restart ComfyUI and check the Local connection after installation.

This CPU preparation has no Linux-only video-runtime dependency. Choosing
official final composite tracking separately requires the runtime described in
`RECAST-RUNTIME.md`. Hosted Comfy Cloud does not provide this custom SCAIL recipe.

The foreground solver is vendored unchanged from
`pymatting/pymatting@6d5c4a6bed0e5672abac0bad078e594423ffe4fd`,
`pymatting/foreground/estimate_foreground_ml.py`; its full MIT notice accompanies
the source in `_pymatting_foreground_ml.py`. ViTMatte is Apache-2.0.

This reduces reference-background contamination, not every possible generated
halo. Fine anatomy, held objects, lighting and identity still require review.
The successful matched comparison covers one 69-frame selected interval, not
arbitrary references or an independently installed PC. Original jobs and recipes
without the explicit cleanup flag retain their previous reference conditioning.
