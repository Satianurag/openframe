# Smoke: released workflow audit and scoped replacement

Reviewed 30 October 2026; release cutoff 29 October. The initial research selected the reusable workflow below; the later actual-run review is recorded at the end. Existing the reviewed job genuinely sampled the endpoint/midpoint-conditioned LTX 2.5 graph, but looked like a largely static fade. Its graph has no fallback interpolation or postprocessing crossfade. Retain that failed-quality evidence.

## Candidate comparison

| Released implementation | What its actual graph does | Fit and limits |
|---|---|---|
| [Comfy first/last style transition](https://github.com/Comfy-Org/workflow_templates/blob/abb9cf6477b59c52dbe234c67f82318dadd872b2/templates/template_ltx2_3_style_transition.json) + [valiantcat adapter](https://huggingface.co/valiantcat/LTX-2.3-Transition-LORA/tree/685118b10fdc2aea63b47bbc6c395fe8c602db53) | Matching LTX 2.3 distilled checkpoint, two native endpoint guides, a transition-trained LoRA and one distilled sampling pass. The author demonstrates scene/identity/style changes, including forest → clouds → mountain. | **Selected candidate:** already a real two-source generated bridge. The cloud example is relevant evidence of intended use, not proof that our mug→lamp Smoke works. No controlled head-to-head benchmark or smoke-specific guarantee is available. |
| [AInVFX Fluid v2](https://huggingface.co/AInVFX/ainvfx-fluid/tree/fd4855a18d879c551bf4c5f49b1a877874437cb6) | Painted first/last and optional intermediate keys, black intervening frames, IC-LoRA downscale 2, eight-step LTX 2.5 generation. The released plume example disables I2V. | Fluid-specific and runnable, but the released graph is not a two-photograph transition. Full-scene generation is supported; describing it as *only* a black-background element generator would also be inaccurate. Not integrated as an invented hybrid. |
| [Native Wan 2.2 FLF](https://github.com/Comfy-Org/workflow_templates/blob/abb9cf6477b59c52dbe234c67f82318dadd872b2/templates/video_wan2_2_14B_flf2v.json) | `WanFirstLastFrameToVideo` with high/low-noise I2V models; active unaccelerated branch uses 20 Euler/simple steps, CFG 4 and shift 8. | Released endpoint pipeline, but no inspected smoke-specific adapter or comparative evidence establishes an advantage. Would require another matched large model stack. No provisioning. |
| [Native Wan Fun Inpaint](https://github.com/Comfy-Org/workflow_templates/blob/abb9cf6477b59c52dbe234c67f82318dadd872b2/templates/video_wan2_2_14B_fun_inpaint.json) | High/low-noise Fun InP models and first/last conditioning; shipped active branch adds the published four-step acceleration adapters. | Another reusable endpoint route. Not an excuse to substitute generic Wan weights or invent a Smoke claim. No provisioning. |

The inspected Comfy template revision is `abb9cf6477b59c52dbe234c67f82318dadd872b2`; the selected file's last recorded change was 28 September 2026. Its code/workflow license is MIT. The adapter was created 20 March and last updated 30 March 2026. Its card declares Apache-2.0; the underlying LTX and Gemma licenses still apply. Newest release date alone does not determine task suitability.

## Why Fluid was not silently substituted

The pinned Fluid v2 card and its 191,680-byte Painter workflow were read, along with [PaintAPlate's complete fluid graph](https://github.com/AInVFX/ainvfx-paintaplate/blob/1f4a5706e4fbec2f6bb5ae763460d03551392d15/web/workflows/fluid.json) and [builder](https://github.com/AInVFX/ainvfx-paintaplate/blob/1f4a5706e4fbec2f6bb5ae763460d03551392d15/tools/build_workflows.py). In that application the blank plate supplies dimensions, length and FPS; `PaintAPlate_KeyframeVideo` supplies painted controls. Neither graph conditions on two distinct scene photos. The adapter is 654,446,312 bytes, expected SHA256 `6310fbda80c9516750bd9fa4db67d500b01c9af2fbd500a7b439d4dbdfb4f971`.

Version 2, released 29 October, replaces withdrawn v1 and documents a synthetic training set. The model card permits painted keys over photographs but warns that the generated scene is inspired by them, not pixel-identical. A native endpoint-plus-painted-control combination would be a **new, unverified adaptation**. Generating a smoke element on black and compositing it between two plates would instead be a **composited transition** and must be labelled accordingly. Neither can be presented as an already proven generated transformation. Fluid weights retain LTX-2.x Community terms; PaintAPlate application code is Apache-2.0. No Fluid weights were downloaded.

## Matched selected recipe

Profile `ltx-2.3-transition`, effect/task `transition-video`; Local ComfyUI only. Existing `ltx-2.5` transition requests and executed graphs remain intact.

- Exact template checkpoint: `Lightricks/LTX-2.3-fp8@91eda216f820e5ecb3d17dc9fe3b7cdaf56b587d`, `ltx-2.3-22b-distilled-fp8.safetensors`, 29,531,884,062 bytes, expected SHA256 `d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2`.
- Exact encoder: `Comfy-Org/ltx-2@ccde4ba417d7900669fd56dd292a883cee11ff37`, `split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors`, 9,447,702,218 bytes, expected SHA256 `aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d`.
- Exact adapter: `valiantcat/LTX-2.3-Transition-LORA@685118b10fdc2aea63b47bbc6c395fe8c602db53`, `ltx2.3-transition.safetensors`, 390,229,424 bytes, expected SHA256 `ba420d6fefafced8e317e2d6ff951b312b52f534377d016b491877a00b830d33`.
- `LTXAVTextEncoderLoader` and the audio/video VAEs read that **2.3 checkpoint**, not the cached 2.5 stack. Adapter strength 1.
- Decode actual last source-video frame / first destination-video frame, or the supplied stills. Native `ResizeImageMaskNode` does centered **nearest-exact** fitting first, then `LTXVPreprocess` compression 25. No earlier resized RGB substitutes for this ordering.
- Native `LTXVAddGuide`: first at 0, then last at −1, both strength 0.7; the last guide receives the first guide's conditioning **and latent**. No midpoint still.
- Audio and guided video latents are concatenated before sampling. CFG 1, eight exact distilled sigma intervals, `SamplerEulerAncestral(eta=0, s_noise=1)`; use the sampler's **denoised output slot 1**, then separate audio/video and crop guide tokens.
- Native tiled decoder: tile 768, overlap 64, temporal size 4096, temporal overlap 64. No second sampling/refinement pass.
- Record original text and the actual model text with `zhuanchang` appended once. No LLM prompt expansion. The adapter card's general CFG 4 recommendation differs from this released distilled template; the implementation follows the complete template's CFG 1 rather than mixing recipes.

Explicit application adaptations: native output canvas on the existing 32-pixel grid; 121 or 241 frames at 24 fps rather than the template's linked duration controls; bounded real image/video endpoint extraction; original/model prompt provenance; optional generated bridge audio; existing explicit concatenation of input clips around the bridge. The bridge itself has no compositor dissolve, interpolation, midpoint paste, or forced endpoint pixel replacement. Native guidance does not guarantee identical endpoint pixels. The selected template's center-crop framing is fixed; custom pad/anchors remain available on the legacy 2.5 option.

## Remote cache and release contract

A read-only cache audit inspected exact model files and their matching cache revisions. Existing 2.3 **dev BF16 + Gemma3 FP8** are different from the selected distilled FP8/FP4 files. None of the exact three files was present. Initial download requirement was **39,369,815,704 bytes (36.67 GiB)**, all remote only. The subsequent coordinated CPU preparation completed before the actual run described below. Expected hashes above are upstream metadata, not a claim that local bytes were verified.

Isolated source modules: `engine/smoke_models.py`, `engine/smoke_workflows.py`; additive catalog/manifest/dispatch, capability and prompt-provenance hooks. Existing endpoint loader gains optional `fit_on_load=false`; its default preserves old graphs. Portable bundles retain exact model pins, the recorded API graph, both endpoint media mappings and the MIT template attribution. The existing optional midpoint still remains replayable only with its compatible 2.5 profile; switching profiles never silently discards it.

Fresh explicit selection of the Smoke preset may select the new candidate when no model was chosen. Saved/explicit profiles remain. Reuse retains actual seed, model, prompt-enhancement flag, guidance, steps, strength, negative prompt, audio and refinement settings. Model-specific dimensions/framing are checked rather than silently changing an incompatible request.

## Comparison acceptance before any quality claim

Retain the mug source and seed 45317 from `reviewed case`, at 1024×576 and 121 frames/24 fps. The old 512×768 portrait lamp loses its shade and base under the official centered crop. Instead, use the already approved 1824×1024 wide lamp/desk Expand result, asset the reviewed case, SHA256 `678248e546c2105c4357b22c6df5c38b9659dbba2ca6862a3e9df1d0ae6d948c`. The actual native resize preserves its complete lamp and book. Record the changed destination, base/adapter, single-pass recipe, guide strength 0.7, crop instead of pad, endpoint preprocessing, removed midpoint, template negative prompt and appended trigger; this is **not** a single-variable comparison. Inspect all generated bridge frames for evolving volumetric smoke that genuinely obscures/reveals the scenes, coherent spatial motion and recognizable endpoints. A static blend, white dissolve, pasted plume or isolated hard cut fails the Smoke quality criterion even if inference succeeds.

Verify real frame count, audio duration, graph/model hashes, original-vs-model prompt, endpoint timestamps and portable API/UI/full-media exports. Root owns actual desktop Generate/playback/reuse. If the candidate fails visually, retain the evidence and report that limitation rather than relabeling execution as a pass or sweeping seeds.


### Bounded implementation checks

The unsubmitted candidate passed 11 invalid-request rejection cases, while the old 2.5 pad/midpoint request remains accepted. 25 native nodes and 36 internal connections/output slots match the pinned template; 12 nodes’ recipe widgets and the complete negative prompt match exactly. The 28-node/41-link editable canvas was generated using live CPU Comfy native schemas plus the actual updated endpoint class executed in the no-model CPU probe. Full-media export was checked in memory: both relocated endpoints, three exact model manifests and the MIT attribution are present. `tsc --noEmit` passed. These checks establish source/contract consistency, **not Smoke output quality**.


### Actual submitted result

The reviewed case was submitted through the desktop Transitions form after reviewing both fitted endpoints and the exact seed/profile/settings. H100 execution took 74.500 seconds. All 121 bridge frames were inspected: smoke actually billows and spreads, then reveals the recognizable lamp, shade, base and book; the mug handle remains recognizable. Independent review accepted this as a **scoped generative Smoke demonstration**. Soft mug/scene overlap remains around the middle, so it is not an opaque smoke-wipe guarantee. The prior static-looking 2.5 result remains failure evidence.

The bridge is 121 frames / 5.041667 seconds; optional cut assembly is the original 97-frame mug clip followed by that bridge, totaling 218 frames / 9.083333 seconds. Both are 1024×576 at 24 fps. Source audio is retained with zero measured sample offset and 0.99809 aligned correlation after re-encoding. Native bridge audio is present and unclipped, but ends at 5.010 seconds (31.667 ms before video); the source's native audio similarly ends at 4.010 versus 4.041667 seconds. This is consistent with causal audio-latent rounding, not an established mux defect. Assembly explicitly pads each segment; final audio is 9.083 seconds. Waveform statistics do not establish semantic sound quality.

Live API graph, editable UI graph and the streamed full-media bundle were checked against the recorded execution. Only portable input filenames change; source/end media hashes, exact expected model hashes/revisions, original/model prompt, one `zhuanchang` trigger, native sampler and denoised output slot, and the template MIT license all match. This does not claim a fresh byte hash of the remote model files. The bundle was inspected in memory without another archive/media copy.
