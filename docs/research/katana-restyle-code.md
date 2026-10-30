# Katana: source-consistent restyling code audit

Research cutoff: 29 October 2026. This is a task-specific implementation decision, not a universal model ranking. No alternative wins merely by being newer.

## Observed failures

- Wan VACE the reviewed job executed the recorded supported 1.3B recipe, but turned the requested restrained gouache scene into neon colors. It used RGB source conditioning, not the structural-control pipeline below.
- LTX 2.5 the reviewed job improved palette/texture, but moved the mug handle from right to left and reinterpreted window geometry. Its source was only VAE-encoded and partially denoised. It did not load a structural IC-LoRA. Its recorded prompt expansion also duplicated a paragraph and introduced a static camera; this is evidence of changed instructions, not proof of the sole cause.

Both retain exact runtime/export receipts under local the retained review record. Successful execution is not a strict source-fidelity pass.

## Runnable candidates and boundaries

| Implementation | Released mechanism / source | Decision for this repair |
| --- | --- | --- |
| **Official LTX 2.5 Union Control** | [Complete native workflow](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_ICLoRA_Union_Control_Distilled.json); all-frame Canny/depth/pose guides, adapter metadata, 8-step sampling and connected 3-step latent refinement. | Selected first: concrete structural conditioning absent from the failing path, compatible with the cached complete model stack and native Comfy exports. This is a testable hypothesis, not a proven quality fix. |
| **VideoCoF**, CVPR 2026 Highlight | [Repository at f45b800](https://github.com/knightyxp/VideoCoF/tree/f45b8009616b3ef8e2024a7da585249b4c74fc2b), Apache-2.0; released 1.246 GB edit adapter; source → grounding → edited-video temporal segments. `scripts/local_style.sh`, `fast_infer.py`, `videox_fun/pipeline/pipeline_wan.py`. | Relevant trained alternative. Genjutsu owner audits the shared code/cache. Upstream random input stride/padding and hardcoded output FPS must not be copied into our exact-interval contract. Additional base/acceleration dependencies need their own audit. |
| **Qwen-Video-Edit**, August 2026 | [Repository at 4e44e49](https://github.com/yunpeng1998/Qwen-Video-Edit/tree/4e44e4992793379752387724666d24873ed9b8b2); `model.py`, `comfyui_nodes/nodes.py`, `infer.py`. Tiled video-VAE latents reuse image-editor priors. Released 360/480/720p checkpoints and Comfy node pack. [Report](https://arxiv.org/abs/2608.14790v3). | Promising, but not a small drop-in: ~55 GB editing stack plus ~40 GB checkpoint and Wan2.2 enhancement dependencies; checkpoint-specific 45/81-frame windows. HF card labels weights MIT, while the inspected code revision has no root license and only vendored license files. Do not infer unrestricted code reuse from the model-card label. |
| **UniVideo**, ICLR 2026 | [Repository at 893c9da](https://github.com/KlingAIResearch/UniVideo/tree/893c9da04b87fdf5099e8e0e9ef164bca6753327), MIT code; released instruction-based video editing/stylization through `pipeline_univideo.py` and `transformer_univideo_hunyuan_video.py`. | Runnable alternative, but a separate Hunyuan/Qwen stack. Component weight terms and source-motion performance on this clip remain unverified. No justified reason to replace the whole existing stack before testing explicit structural guidance. |
| **StyleMaster**, CVPR 2025 | [Repository at 1985b9d](https://github.com/KlingAIResearch/StyleMaster/tree/1985b9dc76a50a43255bb058e0a98beb99d63f8b); released Wan1.3B video translation with gray-tile ControlNet, motion adapter and style reference extraction. | Task-relevant code, but no project-level license found at the inspected revision. The paper's original internal model is not the released Wan reimplementation. Not silently treated as unrestricted reusable production code. |
| **FRESCO**, CVPR 2024 | [Repository at 736a714](https://github.com/williamyang1991/FRESCO/tree/736a7140f30d622ba8b62584445c8f6c2d9d9fe0); `src/diffusion_hacked.py` implements spatial/temporal correspondence constraints; optional keyframe propagation. | Relevant mechanism, but S-Lab license explicitly restricts commercial use. Its propagation components have additional terms. Not a permissive default for this product. |

Newer FFP-300K and SAMA papers describe source-motion preservation, but their abstracts alone do not establish a licensed, compatible released inference package. No integration or quality claim is based on those abstracts.

## Exact selected graph adaptation

The selected template is `example_workflows/2.5/LTX-2.5_ICLoRA_Union_Control_Distilled.json` at `220e1d45aa0469f518e982102fca4dca92a61862`. Its README table calls Union Control one stage, but the actual connected canvas contains stage 1, guide cropping, latent 2× upsampling and stage 2. The graph, not that summary row, determines this implementation.

| Upstream nodes | App mapping |
| --- | --- |
| Reference video → annotator, selectable Canny node 4991 | Existing exact-interval `OpenFrameVideoInput` → native shorter-side544 resize → `OpenFrameCannyGuide`, before any half-size RGB resize; retain thresholds 92/200 and detection resolution 512. |
| Loader 5607 | `LTXICLoRALoaderModelOnly`, strength 1; **wire output 1** as the actual reference-downscale factor. Do not guess it from the filename. |
| Preprocess guide 5012 | Every selected source frame becomes an IC-LoRA guide, frame index 0, strength 1, tiled encoding disabled as in the template. |
| First sampler 4832/4828/4831/4984/4829 | Native noise, CFG 1, Euler ancestral, exact eight-step distilled sigma schedule starting at 1. |
| Crop 5549 → refinement 5517 | Crop appended guide tokens, native latent upscaler 2×, three-step schedule `0.909375, 0.725, 0.421875, 0`; **Euler** comes from the enclosing subgraph's linked widget override. |
| Decode / save | Native video VAE decode, remove only bottom/right inference padding, then existing exact-duration saver and original source-audio mux. Source audio is frozen during sampling instead of generating replacement audio. |

The actual upstream links are source → shorter-side544 RGB resize → Canny512 → guide alignment. Our edge guide is then fitted to the explicit app output size and padded; it is not detected from an already half-sized RGB video. This deliberate canvas adaptation differs from the template, which derives generation dimensions from the aligned annotation.

The official default annotator is depth. Selecting its provided Canny branch is intentional: the mug handle and window boundaries require edges, and no new depth model is necessary. The narrowly adapted Canny implementation preserves the original Apache-2.0 `comfyui_controlnet_aux` resize, edge padding, byte conversion and `cv2.Canny` path from [a587a4c](https://github.com/Fannovel16/comfyui_controlnet_aux/tree/a587a4c1594524c1d2de5cd1a86cd868ff448e1c). Added code only bounds memory, checks cancellation and records hashes. Its full license accompanies exported node packs.

The [adapter](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control/tree/20a580c8606c06a0988d40375a61309e0fe5893d) is explicitly paired with LTX 2.5 by this upstream template despite its 2.3 filename. It is public, 654,465,352 bytes, expected SHA256 `a1b888a87f661d27f08b394ae559e8e1050be33900bcc36a5cdf659e48f88d18`, and retains the LTX Community License. That hash is upstream metadata until verified during remote provisioning. No model files are downloaded to the laptop.

## Compatibility and comparison contract

`restyle_method` defaults to `latent` at the API and for saved documents without this field. The new `canny` branch is accepted only for LTX 2.5 restyle, with the fixed official 8-step/CFG1/guide-strength1 recipe and native three-step refinement. New Katana documents expose both methods; Canny starts with prompt enhancement disabled, while existing saved enhancement choices remain unchanged.

Bounded implementation checks passed before rendering: three actual mug-video frames produced zero pixel differences against the pinned upstream Canny implementation after the native 544-pixel shorter-side resize. The public adapter's remotely read safetensors header confirms `reference_downscale_factor=2`; no weight body was downloaded for this inspection. The complete graph passed an actual CPU Comfy catalog/connection-slot check and canvas serialization (41 nodes, 58 links). The prior latent-restyle job's recorded API graph regenerated identically. These checks establish wiring and preprocessing equivalence, not output quality. Local receipts are under the retained review record and are intentionally outside public source archives.

For the comparison: same mug source, original gouache caption, seed `3842475011`, start 0, 41 frames at 24 FPS; output 1024×576. The inference canvas is 1024×640, first stage 512×320 and IC-LoRA reference latent input 256×160. Edge-replicated bottom padding preserves source aspect; final cropping removes it without reframing. Source audio remains original. Compared with the prior result, the method, fixed guidance/strength semantics, canvas and prompt enhancement change explicitly. This is **not** an isolated single-variable test.

Acceptance is whole-clip: handle remains on the source's right, mug/window geometry and source push-in are retained, style changes appearance without neon colors, no new abrupt geometry errors, requested output duration/audio and portable executed graphs.

The actual desktop-submitted comparison the reviewed case completed in88.59s of recorded H100 execution. Review of all41 source/result pairs confirms the right-side handle, close mug/window placement and progressive push-in; a stable warm illustration replaces the prior neon/geometry-flip failures. Its ink/cel outline treatment is stronger than restrained gouache, and it adds a small mug foot while simplifying steam, bokeh and fine texture. This is a scoped structural-restyle improvement, not universal style or exact-geometry fidelity. Actual guide hashes, unchanged original/model caption, audio correlation0.99862, API/canvas/full-media bundle checks and root's playback/reuse observations are recorded in the retained review record. No additional tuning render was made.
