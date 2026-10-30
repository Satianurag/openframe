# LTX atmosphere and source preservation

Primary-source audit, 30 October 2026. No new GPU inference or weights downloaded for this audit.

## What failed, and what the official graph actually contains

Weather jobthe reviewed case replaced the source McLaren-like silhouette/headlights with a different rounded sports car and lost the foreground raised-arm pose. Its49-frame graph used full-noise Union-Control Canny, without an initial RGB image. This is an actual visual failure, not merely an unfavorable metric.

The [official Union-Control template at220e1d45](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_ICLoRA_Union_Control_Distilled.json) contains optional initial-image conditioning in **both stages**, nodes3159/4970, strength1. That branch is now implemented for Weather. It can supply appearance information missing from edge maps; it does not guarantee future-frame identity. No additional full-video RGB identity branch was found in this template. The source video is converted to Canny, depth or pose annotations.

Do not diagnose a sampler bug from the nested node defaults: refinement node4976 internally displays `euler_ancestral`, but the actual outer subgraph instance5517 supplies **Euler**, matching our executed graph. The normal source/control resizing, adapter-provided reference scale, eight full-noise steps, guide cropping and three-step refinement match the intended template structure. We should not invent combined control adapters or rename generic Canny regeneration as a dedicated weather model.

## Better task-specific released recipe: Water Simulation

The official [Water-Simulation model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation/blob/7a458d0c206d6f80ee7bae2f46e21e959f6fc42e/README.md) explicitly includes rain, wet surfaces and spray. Its input is the **complete dry RGB video**, rather than edge annotations. The publisher supplies paired examples and describes subject/layout retention; these are author claims/examples, not our measured validation.

The card explicitly directs users to the released [native single-stage V2V IC-LoRA workflow](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_V2V_ICLoRA_Single_Stage_Distilled.json), replacing that generic template's example deblur adapter with this Water adapter. This substitution is the author's stated recipe, not an inferred adapter combination.

- Adapter: `ltx-2.5-22b-ic-lora-water-simulation-0.9.safetensors`.
- Repository revision: `7a458d0c206d6f80ee7bae2f46e21e959f6fc42e`.
- Bytes:906,080,568; SHA256`58c244d24a4381858749e66fae9fd1b91aec6b546f83f3f81a7a10b4934a7857`.
- Terms: LTX2.x Community License and the repository access agreement; the existing LTX/Gemma component terms remain.
- Recipe: eight fixed distilled sigmas, Euler ancestral, CFG1, LoRA strength1, full-resolution RGB guide at factor1, one stage,24fps,8n+1frames, up to185frames and1920×1088 in either orientation. The base transformer/encoder/VAEs are already the existing2.5 profile.
- Prompt: visible `Reference shows … Edited shows … ADD WATER …` structure, no enhancement or negative prompt. No silent caption rewrite.
- The source audio is encoded/frozen in the linked native template. Our matched method offers original audio or silence; generated audio remains a separate route rather than an unsupported addition to this recipe.

**The single-stage restriction is important evidence.** The card warns that its two-stage variant loses reference control during refinement and can drift identity; reinserting dry reference there may remove the added water. This is not proof that every other LTX adapter must be single-stage. It is the documented contract for this particular adapter.

Here “native output resolution” means stage1 runs at the chosen final canvas without a second-stage upscaler. Source resizing remains supported by the released graph: our prepared600×338 source is fitted to a1024×576 guide and sampled at1024×576 throughout. This is not a claim of untouched native source pixels.

Source implementation uses existing `ltx-2.5` / `weather` with explicit `restyle_method='water'`. It changes neither legacy latent/Canny graphs nor masked replacement. It has no new custom node or sampler dependency. Exact-request provisioning adds only this adapter to the four existing base components; no upscaler, enhancer, Union-Control or inpainting weights are required. The first authenticated probe returned403. After the user accepted this separate repository, root confirmed200; model preparation and actual inference are still pending. No Cloud availability is implied: the current directCloud2.5 adapter is explicitly inpaint-only.

## Released plate-preserving relighting, with a narrower promise

[PaintAPlate@31adafa85819b616c4f157dc88e6a96f5b9cfd9a](https://github.com/AInVFX/ainvfx-paintaplate/tree/31adafa85819b616c4f157dc88e6a96f5b9cfd9a), Apache2, provides actual `PaintAPlate_RelightTransfer` and [mathops.py](https://github.com/AInVFX/ainvfx-paintaplate/blob/31adafa85819b616c4f157dc88e6a96f5b9cfd9a/mathops.py) functions `light_ratio`, `relight`, `relight_frame`. Its [comp/export graphs](https://github.com/AInVFX/ainvfx-paintaplate/blob/31adafa85819b616c4f157dc88e6a96f5b9cfd9a/tools/build_workflows.py) convert to linear light, align the generated shot, estimate a smooth color/luminance ratio, and multiply the **original plate** by that ratio. The original car/arm texture and motion remain the source's pixels, rather than the model's regenerated geometry.

That is a meaningful implementation to reuse for **lighting-only** preservation. It deliberately suppresses fine generated detail, so it cannot be represented as full rain/splash/wet-reflection synthesis. Source/source-ratio behavior can be assessed on the already-rendered failed68b4 output in a bounded CPU preview before any integration; no rerender is needed. This audit did not modify or ship that compositor.

Two other official releases were checked and are not substitutes for this rain case:

- [LTX2.3 Relight@aa64fa30](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Relight/tree/aa64fa30f382cc507bfe40ece59d37c1fc9d2d92):327,309,305-byte adapter and a released Comfy graph using Eric Venti's light-direction sphere composited into every source frame. Intended for exterior sun direction/hardness; not rain or interior relighting.
- [LTX2.5 Day-to-Night@16a69fe6](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night/tree/16a69fe6c88de9e349246789d0c18803560881f5):327,318,440-byte RGB-reference adapter. It targets a daytime shot becoming night; the current plate already has artificial night lighting. Its own training/settings differ, so it is not silently loaded into the Water or Canny graph.

## Bounded next step

After access and coordinated deployment, review one source-matched Water run with the actual original car/arm interval, the literal trained prompt structure and native single-stage recipe. Check every frame for car/body identity, arm continuity, rain motion, wet-surface artifacts and source audio. Keep raw failure evidence. If only lighting preservation is required, assess the existing-source CPU RelightTransfer separately and label the narrower output honestly. No claim of perfect source retention or a universal best weather model follows from the released examples.

## Actual Water app output (30 October 2026)

Job the reviewed case, submitted through the Weather UI, produced49 frames at1024×576/24fps with the exact single-stage Water recipe. All49 source/result frame pairs were inspected. Falling streaks, wet body/roof highlights and reflective puddles are visibly present. The black McLaren's overall silhouette and headlight layout, and the foreground woman's raised-arm/lowered-arm exit, remain coherent without the earlier Canny discontinuity. This is a scoped rain-transformation pass, not exact source preservation: wheel/rim detail softens, minor nose/vent details drift, and a new yellow parking stripe appears at the lower-right corner. No repeated parameter sweep was needed. Source and output hashes, stream counts, actual graph and all-frame contact sheets are under the retained review record.
