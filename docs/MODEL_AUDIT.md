# LTX 2.3 and 2.5 model audit

Audit date: 29 October 2026. This was a read-only source/metadata/runtime audit: no 2.5 weights were downloaded and no model profile was changed.

## Decision

Keep the tested LTX 2.3 profile as the current flagship. LTX 2.5 is a documented, available alternative, not an unavailable or incompatible model. There is no controlled comparison in this project proving either version best overall. The reason to retain 2.3 now is the completed, cached and directly exercised workflow, including an actual masked-edit result; it is not evidence that 2.5 has worse quality.

The earlier feasibility report selected the official 2.5 workflow as a candidate. Moving to 2.3 was a concrete implementation choice approved during the build. That difference should be stated accurately rather than explained by an invented availability constraint. Both versions are LTX-based; the competition's LTX-core requirement does not by itself mandate 2.5.

## Exact adapter compatibility

The [official 2.5 two-stage inpainting workflow](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json) explicitly selects:

- LTX 2.5 distilled transformer.
- LTX 2.5 Gemma 4 12B encoder with projections.
- LTX 2.5 video/audio VAEs.
- **`ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors`**, the same adapter used by the 2.3 profile.

Thus the supported pairing is established by the official graph, not by requiring identical version strings in filenames. The [2.5 model card](https://huggingface.co/Lightricks/LTX-2.5) says many 2.3 adapters carry over, while acknowledging exceptions that need validation. That general statement should not be extended to arbitrary adapters. The specific inpainting pairing above has stronger evidence because it is present in the official workflow.

The cached workflow was compared with GitHub's metadata at the pinned commit: 267,573 bytes, Git blob SHA `59f408a8c838be102d831bfc633a7018216a0aed`; the cached file's Git blob hash matches.

## Available weight files and access

Fresh Hugging Face API metadata returned the following revisions:

| Repository | Revision | Access metadata |
|---|---|---|
| `Lightricks/LTX-2.5` | `49b093a39c19169a8a81721dcc541e07e945232f` | `gated: auto` |
| `Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting` | `8becd61405133263d9e580be41a92e8f827b01ed` | `gated: auto` |
| `Comfy-Org/gemma-4` | `63d0f7c476756b88910170c1df75e2384ea1af31` | Not gated |

The 2.5 base repository requires its own upstream access approval/authentication unless the account already has it. Approval for the separate inpainting adapter repository alone is not proof of access to the 2.5 base repository. Metadata availability is not evidence that a particular account can download gated files.

Exact BF16 file sizes from the public metadata:

| Component | Repository-relative file | Bytes |
|---|---|---:|
| Distilled transformer | `diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors` | 42,018,190,584 |
| Text encoder | `text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` | 26,263,858,182 |
| Diffusion video decoder | `vae/ltx-2.5-video-vae-bf16.safetensors` | 1,472,223,346 |
| Audio VAE | `vae/ltx-2.5-audio-vae-bf16.safetensors` | 364,866,540 |
| Inpainting adapter, separate repository | `ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors` | 1,308,778,338 |
| Declared spatial upscaler | `latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 995,778,752 |
| Optional local prompt enhancer, `Comfy-Org/gemma-4` | `text_encoders/gemma4_e2b_it_bf16.safetensors` | 10,278,774,160 |

The first five files total **71.428 GB** in decimal units, approximately **66.52 GiB**. Including the declared upscaler gives **72.424 GB**; including that upscaler and the local prompt enhancer gives **82.702 GB**. These are file-byte sums, not GPU-memory requirements or guaranteed disk-usage estimates. The existing adapter can be reused; SAM2 tracking remains a separate already-selected dependency.

There is an important graph detail: the upscaler is listed in the model group, but that group's `LATENT_UPSCALE_MODEL` output is unconnected in this inpainting template. Its actual second stage enlarges decoded/blended pixels with Lanczos, then re-encodes and refines them. Do not download the unused upscaler solely because its selector remains in the imported template. The default template enables local prompt enhancement; disabling that branch must genuinely prune its enhancer dependency before excluding its weights.

The repository also lists a convolutional video VAE and Comfy-specific INT8 transformer/encoder variants. Those are additional resource/quality choices, not automatically interchangeable benchmark equivalents. The official BF16 graph is the clearest reference baseline.

## Pinned runtime compatibility

The deployment pins ComfyUI `79cf64c21a1dba50749945ba9fe2e3a692f45438` and the Lightricks node pack `220e1d45aa0469f518e982102fca4dca92a61862`.

A tiny read-only command in the already-running H100 worker queried its live `/object_info` and expanded the official 2.5 workflow's nested subgraphs. All **48 concrete node types** were present among **1,080 registered types**. UI-only notes/reroutes and subgraph UUID wrappers were excluded from that class-name comparison. This establishes node availability; it is not a successful workflow submission, loaded-weight check or inference result.

Installed versions observed in that worker:

| Package | Version |
|---|---|
| PyTorch | 2.10.0 |
| Transformers | 5.21.0 |
| Tokenizers | 0.23.3 |
| SentencePiece | 0.2.2 |
| comfy-kitchen | 0.2.40 |
| comfy-aimdo | 0.6.0 |

The [pinned native loader](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy/sd.py#L1883) explicitly recognizes the Gemma 4 12B LTX projection weights and constructs the corresponding native encoder/tokenizer. The [native Gemma 4 implementation](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy/text_encoders/gemma4.py) is already included. No separate Gemma 4 custom-node package is indicated by this graph or these sources.

The [diffusion decoder](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy/ldm/lightricks/vae/na_diffusion_decoder.py) uses `comfy_kitchen.na3d`; it does not require installing upstream NATTEN for this native Comfy path. The pinned runtime already includes comfy-kitchen. Actual kernel execution and memory behavior still require a real 2.5 render before claiming verified support.

## Workflow and quality implications

The 2.5 profile would require a real graph branch, not just renaming the 2.3 checkpoint: split `UNETLoader`/VAE loaders, its own projected Gemma 4 encoder, the documented adapter pair, and the correct two-stage media path. The official inpaint template snaps source dimensions to multiples of 64, uses half-resolution stage 1, then a two-step refinement at full size, with mask processing and Laplacian blending. Its stage-1 sigma schedule has eight sampling steps. Optional API text-encoding branches must remain disabled or excluded for an entirely local/open-weight execution path.

The upstream 2.5 card describes improvements in prompt interpretation, motion/detail fidelity, a new decoder and distilled-model quality. Those are upstream claims, not project A/B results. This audit supports offering 2.5 as a separately provisioned and subsequently tested alternative if useful; it does not support claiming it is universally better, claiming the current 2.3 workflow is obsolete, or spending another large download solely to change a version label.

Current decision: finish the already successful 2.3 VFX path and its two-stage verification, retain its provenance, and describe 2.5 accurately as an available future profile. No 2.5 profile is advertised as working in the application on the strength of this audit alone.

## Sources and limits

Primary sources: the pinned Lightricks workflow; the official 2.5 and inpainting-adapter model cards retrieved through Context.dev; fresh Hugging Face model metadata; pinned ComfyUI source retrieved with the installed GitHub CLI; and the live deployed worker's node registry/package metadata. Context.dev's model cards were cached by that service for roughly 15–17 hours; the file/revision/access metadata was separately read from Hugging Face during this audit. No comparative quality benchmark or 2.5 inference was performed.
