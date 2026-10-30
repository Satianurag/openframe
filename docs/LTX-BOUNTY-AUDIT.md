# LTX VFX submission scope

OpenFrame is an inspectable ComfyUI application with Local ComfyUI and supported direct Comfy Cloud execution. LTX is the generative core of the VFX workflows; the application does not replace inference with edited preview videos or simulate completion.

## Implemented core

- Matched LTX2.3 and LTX2.5 masked removal/replacement graphs, source trim/resampling, explicit mask/tracker choices, generation margin and final preservation support.
- Official edited-start-image conditioning, optional bounded plate-fit finishing and removal lighting correction. Original no-reference/legacy recipes remain distinct.
- Source, generated and silent audio for supported editing profiles. Generated audio uses native audio latents/decoder; unsupported task modes reject explicitly.
- Real job persistence, progress, cancellation, deliberate retry, protected assets, immutable request reuse and source/model/node provenance.
- API graph, native UI canvas and full-input bundle exports. Input slots are relocated without altering recorded sampling settings; user media and model weights are separate.
- Task-specific video outpaint, extension, upscale, alpha, HDR, Water and exterior Relight. Their fixed recipes, bounds and provider restrictions are exposed rather than treated as universal generation controls.

SAM tracking/matting, depth and frame interpolation are auxiliary models. They are not described as LTX-generated capabilities. A binary paint mask is not a semantic drawing guide; the app does not implement proprietary named elements, unlimited reference bindings, motion-brush trajectories or every vendor preset.

## Evidence and quality

Reviewed owned-media removal/replacement cases retain their exact graphs and selected inputs in the examples release. Generated edit audio was non-silent and matched between raw/final outputs. Edited-start-image plus plate-fit passed a97-frame scene review with a remaining faint boundary limitation. Exterior Relight passed49-frame layout/lighting review while regenerating fine water/texture detail. Water retained broad vehicle/arm motion with visible rain/wet surfaces but drifting fine detail and parking lines.

Native GUI import/export of representative removal, replacement, audio, plate-fit and Relight canvases preserved their explicit inputs and links; declared optional defaults were distinguished from changes. This is portability evidence, not model execution on the machine displaying the canvas. Runtime success alone does not establish subject identity, exact product geometry, photorealism or arbitrary-source quality.

## Direct Cloud boundary

LTX2.3 hosted generation and masked editing have actual bounded execution evidence. Its adapter returns intermediate lossless frames for app compositing/audio/encoding. A reviewed shape mismatch and hosted timeout remain disclosed limitations, not erased successes.

LTX2.5 Cloud support is **inpaint-only**. The native hosted graph can return a composite video. The app prepares aligned source/masks and optional tracking; selected exact lighting correction, plate-fit and output encoding remain explicit CPU finishing. Finishing consumes the raw generated frames and original source/mask rather than blending an already-composited video twice. Catalogue/schema/CPU/export checks passed; a new live LTX2.5 hosted acceptance run has not been performed. Other tasks, exact unavailable weights and unsupported providers fail explicitly.

## Delivery and replay

Public startup uses a configured Local ComfyUI host or supported Comfy Cloud connection. No private worker or account is required. The source includes application/node code, pinned requirements, licenses and runtime guides. Model access terms remain separate from the application's MIT license.

The examples release separates unexecuted portable Local replay recipes from actual evaluation outputs and explicitly historical Cloud evidence. Native Local import does not relabel earlier computation as an independent PC run. The sanitized plate-fit template requires the user's own source, mask and edited starting frame. Third-party evaluation footage, user training photos, adapters, credentials and weights are not distributed.

See [validation scope](VALIDATION.md), [desktop acceptance](DESKTOP-VALIDATION.md), [API](API.md), [architecture](ARCHITECTURE.md) and [third-party attribution](THIRD_PARTY.md). The release manifest determines the exact shipped files and hashes.
