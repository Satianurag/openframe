# Characters: identity follow-up, 30 October 2026

The framing-only comparison improved likeness but did **not** pass identity acceptance. Source, old/full-frame adapter, new/framed adapter and both matched outputs remain unchanged. The initial research was read-only. The user subsequently authorized exactly one opt-in masked-loss comparison; its implementation and execution receipt are recorded below. No prior artifacts were replaced.

## Exact current trainer audit

The implementation uses the official Diffusers trainer at `aae97e79e8e6a55e0b43114f9c8916c06d4bca8c`, not an invented training loop. Its [README](https://github.com/huggingface/diffusers/blob/aae97e79e8e6a55e0b43114f9c8916c06d4bca8c/examples/dreambooth/README_flux3_klein.md) and [training source](https://github.com/huggingface/diffusers/blob/aae97e79e8e6a55e0b43114f9c8916c06d4bca8c/examples/dreambooth/train_dreambooth_lora_flux3_klein.py) establish:

| Item | Our actual runs | Published implementation/recommendation | Interpretation |
|---|---|---|---|
| Model | Undistilled FLUX3 Klein Base, BF16; frozen Qwen3-VL | Base training; separate text encoder | Correct family, not a distilled-training mismatch |
| Caption | `A photograph of of_higgsfield_performer person.` for every image | Subject folder plus a trigger-bearing instance caption is explicitly supported; per-image dataset captions are optional | Valid baseline. Same caption cannot separately label pose/clothing/background; that entanglement is a plausible limitation, not a demonstrated bug |
| Objective | Uniform full-image flow-matching MSE; fixed shift6.93, target noise−image | Source lines1981–2046 implement this exact objective | No facial embedding, landmark, perceptual or spatially masked identity objective is present |
| Dropout | .1 | Argument help calls .1 common; supports CFG | Not a missing-trigger defect; approximately450 of500 steps are conditionally captioned in expectation |
| LoRA | rank16/alpha16, all default attention/feed-forward targets | Same target set; README’s style example uses rank32/alpha32 | Native coverage was verified separately:258 patches, zero unmapped keys/shapes. Capacity is lower than that example, not known incompatible |
| Budget |500 steps,512 pixel budget, batch1 | Published style example:2000 steps,1024,rank32 | Our run is a bounded functional/diagnostic budget. The README does **not** certify500 steps for faces or provide a FLUX3-specific identity success threshold |
| Data |20 correlated source moments;8 head crops,8 upper-body crops,4 originals in second run | Aspect buckets and subject-folder training supported; no official8/8/4 ratio | Cropping improved visible likeness but does not add independent views, lighting, clothes or scene diversity |
| Inference | Base50 Euler/simple,CFG3.5,actual trigger prefix,registered strength1 | Official Base inference defaults50/3.5 | Correct baseline; actual PNG/graph carries trigger. Pre-trigger general image metadata is separately noted in the receipt |

BFL’s [release notes](https://docs.bfl.ai/release-notes) explicitly identify Base as the training model and support both Diffusers and AI Toolkit. Older [FLUX2 training guidance](https://docs.bfl.ai/flux_2/flux2_klein_training) gives character step ranges, but it is a different model generation: it is not evidence that an exact step count fixes this FLUX3 jaw error. Changing rank, resolution, steps and captions simultaneously would also lose the current controlled comparison.

## Released compatible implementation worth reusing

[Fizgig](https://github.com/shootthesound/Fizgig/tree/6fb10a3bc2f70c8d664262fb48358edbf505788b), pin `6fb10a3bc2f70c8d664262fb48358edbf505788b` (30 October), is Apache-2.0 and has an actual FLUX3 masked-training implementation, not just a paper claim:

- [families/flux3.py](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/src/fizgig/families/flux3.py#L37): explicitly enables `masked_training` for FLUX3.
- [flux3/driver.py,186–212](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/src/fizgig/flux3/driver.py#L186): same flow velocity target, then packs the spatial mask onto generated-image tokens and applies weighted squared error. It rejects distilled training.
- [families/driver.py,37–51](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/src/fizgig/families/driver.py#L37): normalizes spatial weights to mean1 per image before averaging loss. Small masks do not simply make that image’s gradients vanish.
- [dataset/masks.py](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/src/fizgig/dataset/masks.py): mask/image shape checks, same image crop/resize, area averaging onto latent grid, and `clamp(mask,min=floor,max=1)`. Empty/tiny masks are rejected or visibly reported; they are not silently useful training examples.
- [families/train.py](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/src/fizgig/families/train.py#L1201): loads the mask and sends it to that exact driver path.
- [Masked training guide](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/docs/MASKED_TRAINING.md): supports face/hair or person masks, recommends outside weight.1, leaves the whole input image intact, and supports SAM3.1 or manually supplied masks. Optional masked prior preservation needs another base forward; it is not needed for the minimal experiment.

Important evidence limit: its author reports better character likeness with masks, but supplies no independently validated FLUX3 identity benchmark in these sources. [FLUX3 documentation](https://github.com/shootthesound/Fizgig/blob/6fb10a3bc2f70c8d664262fb48358edbf505788b/docs/FLUX3.md) explicitly labels its presets experimental and borrowed initially from Krea2. Its FLUX3 block-to-identity map is not measured, so its block-strength tools do not justify guessing which blocks to amplify.

## Adapter compatibility audit

A bounded current review checked live web/GitHub searches and all22 Hub adapters explicitly tagged to FLUX3 Klein Base. This is not a claim that every unindexed release was searched.

| Candidate | Released evidence | Applicability |
|---|---|---|
| [PuLID-FLUX](https://github.com/ToTheBeginning/PuLID/blob/1aa2fc7df4bf51080df39f355f9abdc1cbfefbaa/docs/pulid_for_flux.md) | Official code explicitly names FLUX.1-dev and FLUX.1-Krea-dev; v0.9.1 identity adapter exists | Not verified compatible with FLUX3 architecture. Do not load it or claim a drop-in identity fix |
| [ausboss FLUX3 Restore](https://huggingface.co/ausboss/FLUX-3-Image-Klein-Restore-LoRA/tree/be1d0a1c5edf6655d0c370d531a8157815bb5469) | Released161MB rank32 adapter, trained on Base; tested on distilled restoration/reference tiles; FLUX Kommunity terms | Author reports small improvement on8 restored faces. It redraws an existing photo, not a learned person in new scenes; cannot substitute for this Characters acceptance |
| [ausboss FLUX3 Consistency](https://huggingface.co/ausboss/FLUX-3-Image-Klein-Consistency-LoRA/tree/0367b0cdeb14b16423ff64e1c256a1a5f76cd414) | Released161MB rank32 adapter; Base-trained, distilled-tested; FLUX Kommunity terms | Intended to reduce scene shifts during editing. Author’s15 edits:4 better,5 worse,6 tied; poses/hair sometimes worse. Not a face-identity adapter |
| [Raume subject LoRA](https://huggingface.co/Raume/alphajace-klein-lora/tree/4a9e3f312bf9dedc53da54484d557e305c643781) | Actual FLUX3 DreamBooth subject weights | Different subject, no useful published dataset/hyperparameter/identity evidence; cannot repair our subject |
| [SimpleTuner subject example](https://huggingface.co/SimpleTuner/flux-3-klein-image-domokun-1024/tree/b7a5180e3d9d0364766374472360c337d379db22) | Actual Base subject LoRA,10000 steps/370 epochs,50-step CFG3.5 validation | Demonstrates compatible training; toy-subject result and larger budget do not establish human identity performance |

No general identity-encoder adapter with released, verified FLUX3 compatibility was established. Native multi-reference editing is a separate useful capability, but an unrelated reference-assisted render would not turn the failed trained-character check into a pass.

## Initial proposal (before authorization)

Prepare a small **opt-in masked-loss experiment** by reusing the pinned Apache Fizgig spatial-loss formulation in the existing pinned Diffusers trainer. Keep the exact framed20-image dataset, caption, seed,rank16,512 and500-step budget so the changed variable is the objective’s spatial emphasis. Review genuine head/hair/ear/jaw support masks before any run; retain person/body support for small action views where a head-only mask is below the source implementation’s meaningful-coverage threshold. Store the exact masks and selection policy. Use outside weight.1, per-image normalization and no extra masked-prior forward. Preserve every old graph/adapter and the unmasked default.

This needs minimal attributed glue: mask-to-identical-crop alignment in the dataset, mask/token weights at the existing squared-error reduction, and explicit provenance/optional dataset-mask transport. It does not need a different base model, face-swap system, pretrained identity adapter or extra model weights; already cached SAM3.1 may prepare masks if authorized. Do not transplant Fizgig’s experimental scheduler/presets or assume its positional token packing equals Diffusers without checking the actual grid.

The tradeoff is explicit: this targets where the gradient is spent and could improve facial proportions without another full-image budget increase, but is still flow matching, not a guaranteed identity metric. Imperfect masks can exclude ears/jaw/hair; emphasizing one correlated video can overfit its appearance. Expected per-step compute is close to the existing objective, but no measured runtime exists for this adaptation. If approved, bounded contract checks and one same-seed matched output must precede any production/default claim. No implementation or training was started during that initial research.

## Authorized masked-loss comparison (completed; identity not accepted)

The unchanged framed20 photographs now have20 reviewed conservative head rectangles. Every rectangle includes visible hair, ears and jaw; action frames retain at least1% mask support without replacing the head objective with a full-body mask. This is geometric loss support, not a semantic segmentation claim. The original source images and framing are unchanged.

`engine/training_masks.py` adapts the pinned Fizgig weighting; the full-image path still produces the identical prior adapted trainer SHA256 `d48fd9cf50d28db09c3febc50ae96bce0d1504278a33b74ffb207681c6a1e8ae`. The actual pinned Diffusers dataset code was executed on CPU: all20 image tensors and global Torch/Python RNG states remain identical with masks enabled; each mask follows the exact crop/flip, and token weights use area averaging. Uniform-error loss remains1, full support equals the old MSE, and foreground/outside gradient ratio is10. No model was loaded on the laptop.

 The normal app request creates character/the reviewed job; the sole request changes relative to the framing run are the new name and ordered mask assets. The private GPU continues to exercise public Local training transport internally, with that distinction recorded. The first invocation stopped before optimization because a new EXIF read preceded Pillow verification. Its immutable failure is retained; the guard ordering was corrected and all20 actual inputs pass. Explicit Retrythe reviewed case completed500steps in240.12seconds; matched inferencethe reviewed case completed in26.16seconds. The actual graph differs only in adapter filename/hash and output prefix from framing-only inference. Full output and face-crop review still finds the source jaw/chin proportions insufficiently preserved. Identity acceptance remains failed; all old results remain unchanged and no further training was automatically scheduled. See the complete implementation/integrity receipts and Apache license under the evidence directory and runtime guide.
