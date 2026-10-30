# Recast: reuse decision and implementation boundary

Reviewed 30 October 2026. The existing the reviewed case
Wan Animate replacement changes the source banknotes into a fan and changes fine
performance. Its earlier runtime success is **not** acceptance of realistic
performer replacement. The separate Influencer motion run
the reviewed case also changes banknotes into a cylindrical prop;
its source/export integrity does not establish prop fidelity.

## Selected existing implementation

Reuse the complete [official native SCAIL-2 workflow](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/video_wan21_scail2_character_replacement.json),
including its Base and Extend subgraphs. No core upgrade or new model architecture
is introduced. The deployment remains on ComfyUI
`79cf64c21a1dba50749945ba9fe2e3a692f45438`; its
[nodes_scail.py](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy_extras/nodes_scail.py)
and [nodes_sam3.py](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy_extras/nodes_sam3.py)
already implement the conditioning, segmentation and identity colors.

The [official SCAIL-2 repository](https://github.com/zai-org/SCAIL-2/tree/78fe19576bb06be96c2375e088574a262a300edb)
conditions directly on driving-video latents. This addresses an identifiable
information loss in our old graph: Wan Animate received pose, face crops and a
background with the performer region blacked out, so details of held banknotes
inside that region were missing from the video condition. Raw-video conditioning
is a reason to evaluate SCAIL-2, **not a guarantee that its generated hands or props
remain exact**.

The authors' [SCAIL-2 paper, version 3](https://arxiv.org/abs/2606.10804v3)
reports stronger X-Dance cross-identity human ratings than Wan Animate
(imaging 4.43 vs 3.80; temporal 4.18 vs 4.03; appearance 4.38 vs 4.23).
These are author-reported task results, not an independent banknote-preservation
benchmark or proof of a universal best model.

### Exact adaptation

- `engine/recast_workflows.py` constructs the native graph. FP16 base, DPO
  strength 1, full-quality defaults **40 Euler steps, CFG 5, simple schedule,
  shift 5**. No Lightx2v acceleration or relighting adapter is silently enabled.
- Native SAM3.1 tracks one `human` in source footage and the single-person
  reference. White driving-mask background and black reference-mask background
  use native `SCAIL2ColoredMask`, with its trained blue first-identity color.
  A painted first-frame source mask overrides text-based source selection;
  it is tracked natively. A mask video is explicitly rejected for this profile.
- `WanSCAILToVideo` receives the full RGB driving video and its colored masks,
  the reference RGB/mask and CLIP vision conditioning. The raw reference follows
  the official native template's framing; no unrelated pose-wrapper is mixed in.
- More than 81 frames uses the official five-frame anchored overlap. Native
  offsets account for that overlap. Subsequent decoded windows use the native
  Extend `ColorTransfer` (Reinhard Lab, per-frame, strength 1), drop five overlap
  frames and concatenate. The app bounds this implementation at 161 frames.
- The small `OpenFrameRecastMasks` adapter fails empty source/reference selection,
  records mask coverage, and reuses existing final plate-margin/feather helpers.
  It does **not** modify the colored conditioning masks. All-empty frames within
  an otherwise valid track remain possible during full occlusion and are recorded.
- The main result composites generated content over the original plate using
  that tracked support and preserves the selected original audio. A separate
  silent `uncomposited` output encodes raw decoded RGB **before** overlap color matching and
  plate compositing. It is an encoded diagnostic video, not a lossless tensor dump.
- Existing Wan Animate jobs, weights, graph construction and explicit saved
  model choices remain intact. Fresh Recast selects SCAIL-2. SAM2 is not installed
  or required merely because an old request field names that legacy tracker.

No separate hand/prop preservation algorithm has been added before observing
this complete existing implementation. Automatic segmentation can include or
exclude held objects, and the final support can clip a replacement silhouette.
Review both masks and raw/final outputs. Original hands or money are not promised
pixel-exact inside the editable performer support.

### Pinned remote artifacts

`engine/recast_models.py` stores exact byte counts and SHA-256 values.

| Repository / revision | Native artifact | Bytes | Terms |
|---|---|---:|---|
| [Comfy-Org/SCAIL-2](https://huggingface.co/Comfy-Org/SCAIL-2/tree/fe3c728bc793ba21ca674688f822afb709ad44fb) / `reviewed case` | `diffusion_models/wan2.1_14B_SCAIL_2_fp16.safetensors` | 32,794,040,328 | MIT model card |
| Same | `loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` | 1,226,936,552 | MIT model card |
| [Comfy-Org/sam3.1](https://huggingface.co/Comfy-Org/sam3.1/tree/7bb8374780a725b4353ed31f3a9395c9742b5621) / `reviewed case` | `checkpoints/sam3.1_multiplex_fp16.safetensors` | 1,745,546,848 | SAM License |

At most **35.77 GB decimal** of these three files if absent. Shared native Wan VAE,
UMT5 and CLIP vision reuse their existing pinned cache entries. The existing
official SAM3 PT checkpoint is a different representation; it is not relabelled
as this native checkpoint. Upstream SCAIL code is Apache-2.0; native Comfy code
and SAM model terms remain separate. All provisioning is remote, following actual
cache/free-space checks. No new weights are downloaded to the laptop.

## Alternatives inspected, not installed

| Reusable source | Evidence and decision |
|---|---|
| [MoCha](https://github.com/Orange-3DV-Team/MoCha/tree/aa503085c3b985e1c44ae4f7786c2a9402df53c1) + existing [WanVideoWrapper example](https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/088128b224242e110d3906c6750e9a3a348a659b/example_workflows/wanvideo_2_1_14B_MoCha_replace_subject_KJ_02.json) | Released replacement inference and checkpoint; [paper](https://arxiv.org/abs/2601.08587v2) specifically studies interactions. Model card is AGPL-3.0 and the checked official code tree had no top-level license. SCAIL has a simpler native integration and clearer distinct code/model terms. |
| [Floyd Stunt Double](https://github.com/gjnave/Floyd-Stunt-Double/tree/e73e8246a931b2bc04284d9b566de16106a78739) | Actual standalone MiniMax H3 + character-swap adapter, not a Comfy replacement graph. Optional still-image head protection is not proof of preserving source banknotes through video. Reusing its whole runtime would add another model stack without comparative evidence here. |
| [Genjustsu Open Source Workflow](https://github.com/sirioberati/Genjustsu-Open-Source-Workflow/tree/40fd6615c2b7d940d4d7060e82de522292eefe99) | Useful hash-bound mask review and original-audio restoration; actual generation uses hosted Seedance through Enhancor. It is not a self-hosted Comfy performer-replacement engine. |
| [Wan2GP](https://github.com/deepbeepmeep/Wan2GP/tree/9cb2bcdafa7b41d2a1c30d2571cea4bc104657fb) | Already integrates SCAIL/MoCha and bounded windows. Reusing native Comfy avoids wrapping another application. Its shift-3 recipe is not mixed with the official native shift-5 template. |

The July 2026 SCAIL relighting adapter is a real released follow-up if the observed
failure is lighting/shadows. It is not provisioned for the first DPO baseline.
SAM2Matting and MatAnyone2 have noncommercial restrictions and are not imported
into this default product path.

## Planned comparison and current status

The native path now has a real app result with a substantial banknote improvement
and an unresolved two-frame hand-compositing flicker.
See [Recast validation](../RECAST-VALIDATION.md) for all-frame evidence, the two-frame
hand-mask inconsistency, media/export checks and explicit limits. The original
planned comparison below describes the conditions used.
First comparison uses the original source interval and blue-blazer reference
from the failed Recast case, 65 frames at 16 FPS, source time 0, and the full-quality
native recipe. Changes are explicit: model/conditioning, automatic performer
segmentation instead of the broad old painted upper-body mask, and a literal
banknote/hand-performance caption instead of describing a fan of notes.
This is a practical repair comparison, not a one-variable model benchmark.

Before generation, inspect the source, reference and performer/prop regions.
Afterward compare every frame, timing, connected hands and individual banknotes
against the original and rejected Wan result; inspect raw and composited clips,
audio, model hashes and exported graph/bundle. Retain failure evidence. Do not
declare realism from completed inference or a few attractive frames.


## Influencer reference-edge cleanup: completed selected-interval proof

The matched SCAIL-2 Influencer comparison is a **qualified visual pass for 69 frames at 24 fps (2.875 seconds), source time 3.000–5.875 seconds**. This is not full-length validation of the 17.0417-second source. Root reviewed every raw and final frame. The broad white outline is absent in this comparison; the final `official-union` support retains the coat and rear shoe throughout. Hands, face/identity detail and action are not exact, and the original plate’s shadow can differ from the replacement silhouette. The reference is a stylized character, not a measured identity guarantee.

Only cleaned reference RGB enters native VAE character conditioning. The original CLIP reference, source tracking, prompt, seed and sampler settings remain unchanged. Reference preparation uses the native person mask, a fixed 12-pixel trimap, CPU ViTMatte and the pinned MIT PyMatting foreground solver, then premultiplies onto black. Confident-interior RGB stays unchanged. Final `official-union` compositing uses source plus generated performer support; its final correction did not rerun diffusion. The matched diffusion took 909.021 seconds. All 69 decoded final frames are unique and output hashes match the recorded files.

The portable cleanup node was checked against the exact prepared PNG used by that successful diffusion. With the pinned native `LoadImage`/`InputImpl.VideoFromFile` floating-RGB decode and FP32 bicubic center resize, both the preprocessed RGB and final prepared PNG match exactly. Both PNGs have SHA-256 **`f5490fa7b28bc2c7f4f57872ecdab596553102b7334c8d35b07768bfc447a6ee`**; maximum/mean RGB byte error is zero, alpha ≥0.5 covers 201,900 pixels, and the measured inner-edge white-pixel count is zero. This is a bounded equivalence result for this input and runtime, not a promise across every decoder/version.

The earlier `node-cpu-equivalence.json` and `native-prepared.png` remain intact as **diagnostic-only** evidence. That private proof substituted Pillow’s 8-bit WebP decode for ComfyUI’s native floating-RGB decode and reported maximum RGB error 10/mean 0.1213. The corrected native-loader proof resolves that discrepancy without a production cleanup change; FP16 or double quantization was not established as its cause.

Evidence:

- All-frame integrity and qualified visual review.
- Actual derived-media registration: asset the reviewed case, SHA-256 `9bbc4b07bb70bb5c5b467fa9ce8cdadb7bcd0beb1c7fea9f1c2be30008289198`, derived from original app the reviewed job. Registration does not fabricate a new app render job.
- Corrected native CPU equivalence, pinned-source/decoder diagnosis, and retained original diagnostic.

The **Clean reference edges** field is saved and reused in Recast MiniApp, Influencer and Katana. New drafts enable it; old saved character-replacement recipes lacking the field remain off. Requests send it only for SCAIL-2. Availability requires the selected provider’s explicit runtime capability; missing support blocks an enabled request and lets the user turn it off. These plumbing statements are source-reviewed; they are not a claim of additional browser acceptance or a new video render.
