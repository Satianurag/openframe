# FLUX3 trained character plus photographic reference — read-only assessment

30 October 2026. The masked-loss trained-only output still fails jaw/chin likeness. This note proposes a separate reference-assisted mode; it does not change that verdict, train another adapter, switch models or claim universal identity preservation. No inference, model downloads or runtime changes were performed for this assessment.

## Smallest defensible candidate

Use the existing **undistilled `flux3-klein-base` plus the same registered character LoRA**, with one approved, clear photograph from the existing training set as a native image reference. Keep the matched caption, seed315042, 50 Euler/simple steps, CFG3.5, character strength1, output size and direct-caption mode. Do not enable a preservation mask or add another LoRA. No new model files or custom nodes are needed.

Soul Image already accepts a trained character and reference photographs together. Adding one photograph makes its normal UI submit `edit-image` with that first photograph as `source_asset_id`; subsequent images become ordered references. Alternatively, the existing API can keep `create-image` and add one `reference_asset_id`/ordered reference, since Base advertises references for text-to-image. Either must be recorded honestly as reference-assisted conditioning. Prefer the existing visible app path for acceptance; do not silently retrofit the old trained-only result.

The baseline is the retained review record. Its caption is already explicit, so adding a reference need not invoke prompt expansion or alter sampler parameters. Judge facial proportions/jaw/chin against the selected photograph, while checking that the requested navy sweater/courtyard scene is actually generated rather than simply reproducing the training photograph. Copying reference clothing, pose or background is a possible tradeoff, not an identity pass.

## Released evidence and exact pins

| Primary source | Concrete evidence | Limits |
|---|---|---|
| [Diffusers FLUX3 training README](https://github.com/huggingface/diffusers/blob/aae97e79e8e6a55e0b43114f9c8916c06d4bca8c/examples/dreambooth/README_flux3_klein.md#inference), commit `reviewed case`, blob `2649356e29881d511bda298f6119454b76645539` | Its inference example initializes `black-forest-labs/flux-3-image-klein-base`, loads a trained LoRA, then explicitly directs image-to-image callers to pass the reference through `image=`. The checked upstream file exactly matches our retained training README. | This establishes compatibility, not a measured identity improvement for our particular subject or trained-only adapter. |
| [Official native Base image-edit template](https://github.com/Comfy-Org/workflow_templates/blob/abb9cf6477b59c52dbe234c67f82318dadd872b2/templates/image_flux3_klein_image_edit.json), blob `97d2b7eee8bc6972756a8b11a9e773c4becc843e` | Undistilled Base loader, native `ReferenceMultiLatent`, references on positive and negative conditioning, empty output latent, Euler/simple sampler. The template describes ordered reference tags. | The published template uses quantized Base/encoder; our existing matched profile uses BF16. Do not silently switch precision. The template alone does not contain our private trained adapter. |
| [Native reference nodes](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy_extras/nodes_edit_model.py) | `ReferenceLatent` appends VAE samples to `reference_latents`; `ReferenceMultiLatent` encodes each reference and appends the same list to both CFG branches. | Full-image latent conditioning, not an identity-only facial embedding or a landmark constraint. |
| [Native model-only LoRA loader](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/nodes.py) | `LoraLoaderModelOnly.load_lora_model_only` modifies the model independently of reference conditioning. Our registered Local loader verifies the adapter hash before using this path. | Only the matched Base checkpoint/adapter pair is accepted; FLUX1 PuLID or unrelated identity-adapter weights are not compatible substitutes. |
| [BFL reference implementation](https://github.com/black-forest-labs/flux-3-image-klein/blob/bfc8889a4497f846416f253a3972a1941ac698b9/README.md) and [Comfy release description](https://blog.comfy.org/p/flux-3-image-klein-in-comfyui-56b) | Base is explicitly undistilled and supports image editing/multiple references; BFL documents up to ten images. | Recognition claims are not a guarantee of exact facial geometry in this application. |

**Recipe inconsistency observed, not silently “fixed”:** the current pinned BFL README lists Base50/CFG4; the official Comfy Base-edit template’s note says50/CFG3.5, while its serialized KSampler widget containsCFG1. Our established matched profile uses50/CFG3.5. This reference-assisted candidate keeps that existing recipe rather than changing guidance while testing the additional reference. No inference-based conclusion follows from those inconsistent published defaults.

## Existing application and graph contract

- `engine/training_models.py`: Base inherits `supports_reference`, image-edit/text-to-image reference tasks and the ten-image limit; it additionally declares character-adapter support. Exact Base SHA is `5c921759dc03663dbb67df11d8e3d317d2d5b893b31b969c95dc77ebf861b19c`.
- `engine/flux3_character_workflows.py`: builds the ordinary FLUX3 graph first, then connects the registered adapter to the sampler model and injects its trigger into the actual caption. It does **not** discard the reference conditioning. Base/hash/provider/adapter guards remain active.
- `engine/flux3_workflows.py`: references are aspect-preserved with native Lanczos scaling (default1MP,16-pixel size grid), VAE-encoded, and appended to both positive and negative conditioning. With preservation disabled, generation begins from the empty output latent at denoise1, not from a lightly denoised copy of the photograph. Our explicit `VAEEncode` + chained `ReferenceLatent` slots implement the released multi-reference conditioning operation.
- `frontend/src/apps/SoulImage.tsx`: reference slots coexist with the trained-character selector; selecting references routes to image-edit and retains `character_adapter_id`/strength. No additional frontend feature is required for this bounded candidate.
- Local ComfyUI execution must use the provider that owns the registered adapter; weights are not silently copied to another provider. The public Cloud image adapter remains unavailable.

## Licensing and acceptance boundaries

BFL reference code and Diffusers are Apache2; the Comfy template is MIT; native ComfyUI is GPL3. The Base/model-derived adapter remains subject to the **FLUX Kommunity License1.0**, not a blanket Apache license. No additional weights are proposed, and no new identity plugin is introduced.

A clear result would demonstrate **reference-assisted likeness on this subject**, with exact request/reference/adapter hashes and a visible comparison to both the training photograph and failed trained-only output. It would not establish trained-only success, general identity disentanglement, exact jaw geometry on arbitrary views, or independence from reference clothing/background. Preserve the failed trained-only receipts regardless of the candidate outcome.


## Authorized candidate outcome

The user subsequently authorized exactly one inference, now completed as the reviewed case in42.39s. The actual API request retained create-image and added only the single approved training crop to `reference_asset_ids`; no code/model/training changes were made. Executed graph and hashes confirm the same adapter/sampler plus references on both CFG branches. It improves visible jaw/chin and overall likeness but copies the reference framing/background and misses the requested waist-up composition. This is a qualified **reference-assisted** improvement only; the trained-only identity failures remain unchanged. See [the final Characters receipt](../CHARACTER-TRAINING.md#reference-assisted-likeness-comparison-separate-from-trained-only-acceptance) and the retained review record.
