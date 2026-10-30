# LTX exterior relighting and weather: released-code audit

30 October 2026. Source research and approved implementation follow-up; the first49-frame private Relight result now has scoped visual acceptance, recorded below. The author downloaded no model weights. Existing generic latent/Canny restyle remains available. Dedicated sun relighting, weather generation and preservation of source detail are separate requirements.

## Decision

The official LTX2.3 Relight adapter is the most directly relevant released model found for exterior sun direction. After the user accepted repository access, the same authorized account returned200 and the exact pinned workflow was retrieved. Its adapter is still absent from the live Comfy Cloud catalogue. The approved implementation is a distinct `ltx-2.3-relight` exterior profile, not a relabel of generic restyle. Its actual graph and explicit FP8-text-encoder adaptation are recorded below; the first scoped runtime result is recorded below; it does not establish exact material or calibrated-angle fidelity.

An immediately inspectable, licensed alternative for **finishing an existing generated relight** is PaintAPlate's `RelightTransfer`. It transfers a bounded lighting field to original pixels instead of using the regenerated picture as the final plate. This is a concrete reusable CPU component, not a rain model or proof that the current weather output can be repaired. A bounded comparison using an existing rendered clip could evaluate it after approval, without new diffusion.

## Official sun-direction adapter

Primary sources: [pinned model card](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Relight/blob/aa64fa30f382cc507bfe40ece59d37c1fc9d2d92/README.md), [gated workflow](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Relight/blob/aa64fa30f382cc507bfe40ece59d37c1fc9d2d92/LTX-2.3_Relight_ICLoRA_SingleStage_Distilled.json).

- Repository revision: `aa64fa30f382cc507bfe40ece59d37c1fc9d2d92`.
- File: `ltx-2.3-22b-ic-lora-relight-1.0.safetensors`, 327,309,305 bytes; SHA256 `c0d519f83681395d160e115829a9044d7d2ec013be6a2655834d235a2e866ebd`.
- Weights use LTX2 Community terms, not Apache/MIT. No weight bytes were fetched.
- Card contract: LTX2.3 distilled, one stage, adapter strength1, reference scale1. Exterior source video gets a fixed direction-sphere patch on every frame. Trained geometry is1280×704,121frames,24fps; patch143×143 at22px top/right. Composite after resizing. Source/reference/output must align.
- No mask control; interior relighting and content editing are outside the stated use. Caption describes lighting/direction, not scene replacement. The card specifically warns against its two-stage path.
- Access history: local unauthenticated401, then authorized403 before the user accepted this new repository, then authorized200. The exact pinned graph is now read. Its remote manifest size is136,813bytes; the local parsed/indent2 representation is136,961bytes, SHA256 `176a3c019bb401bef05edf984d18d6dac9353bc842dff3d5b497a082413e61e4`. That is a normalized-JSON hash, **not the hash of original remote bytes**.

The complete public [ComfyUI-LTXVideo tree](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/220e1d45aa0469f518e982102fca4dca92a61862) has no relight/weather/rain path. Its other IC-LoRA templates are not evidence of an identical Relight graph. A scoped Comfy-Org workflow search found image-relight templates, not this video workflow. This is a bounded search result, not proof that no other public mirror exists.

Backend's read-only hosted node catalogue lacks this exact LoRA; matching LTX2.3 base weights alone do not establish hosted availability.  Normal release must explicitly reject unavailable model/provider combinations.

## Sphere node: real headless boundary

The card links [Sphere-Light-Render-ComfyUI](https://github.com/eric-venti-seeds/Sphere-Light-Render-ComfyUI/tree/cc89da68f898ddabb6fddbfb0781d3999550ac18), revision `cc89da68f898ddabb6fddbfb0781d3999550ac18`, MIT. Its NOTICE separately attributes vendored Three.js and GeoNames data.

`js/preview.js:buildScene` and `renderLight`, with `js/light.js`, implement the actual Three.js sphere/shadow renderer. `renderLight` returns a PNG data URI. The browser serializes that image into `render_b64` before queueing. Python `SphereLightManualNode.execute` only decodes that value; it does **not** render from rotation/elevation/intensity. Missing/invalid image data silently becomes a flat gray image in upstream code.

Therefore an API adaptation must persist the actual rendered PNG and its parameters/hash, and reject a missing render. Sending just angle numbers would lose the control signal. The existing ComfyUI node can render it interactively; an app could reuse the licensed renderer functions with their dependencies. Portable graphs need the prepared image/base64, not a claim that arbitrary headless servers run browser code. Cloud also needs the prepared control frames and an actually available LoRA. The approved app adaptation now vendors only the exact manual renderer functions plus pinned Three.js r128 (1,140,878bytes; SHA256 `af527c374b56b8688737a42d7fcea7cb8aaeb57a4e3c6da98b4dffd55bcc3514`), with MIT licenses. `frontend/src/RelightSphere.tsx` lazily renders a512px PNG; explicit Apply uploads it, and parameter edits invalidate the prior image. `OpenFrameRelightSphere` reads that PNG, converts RGB and resizes to1024² with PIL LANCZOS, matching the released decoder. Native ImageScale then applies area resize to143². Missing/invalid PNG fails rather than inventing a gray sphere. Angles/image persist together; no hidden prompt rewrite. GeoNames data and city controls are not copied.

## Exact active Relight workflow and cache reuse

The downloaded workflow has46nodes/63links;34nodes reach primary SaveVideo4852. The active contract is more specific than the card's shorthand “distilled”:

- `ltx-2.3-22b-dev.safetensors` + distilledLoRA1.1 at0.5 + Relight1.0 at1.0. No substitution with a distilled checkpoint.
- CFG1, `euler_ancestral_cfg_pp`, eight explicit intervals: `[1, .99375, .9875, .98125, .975, .909375, .725, .421875, 0]`.
- Source slice0–5s → native center-fit Lanczos1280×704. Sphere decoder1024² → area143² → patch at(1115,22) on every fitted frame. Guide strength1/frame0/reference factor1.
- Primitive121 drives both audio/video latent lengths at24fps. The audio widget's97 is overridden. Our9–121/8n+1 bound is an intentionally bounded app envelope, not a published model maximum.
- Native AV sampling, crop guides, separate and tiledVAE decode `[2,2,6,False,auto,auto]`. Final video receives original selected source audio; generated audio decoder is not connected to primary output.
- LTXVPreprocess5095/CRF18 is **disconnected**. It is not part of inference. Bypassed GemmaAPI nodes and side-by-side preview concatenation likewise are not the active prompt/output contract.
- The workflow's saved sphere149.684°/15.3915°/2 and example caption “from the right” are not assumed consistent. App defaults90°/22°/2 explicitly show low right lighting; users see/edit the exact caption rather than an invisible rewrite.

Existing private-cache listing records DEV, distilled1.1 and FP8Gemma symlinks (`private-cache-listing.json`); listing is not a fresh byte-integrity proof. The current exact model manifest already records their hashes:

| Dependency | Bytes | SHA256 / source |
|---|---:|---|
| DEV checkpoint |46,149,344,974|`7ab7225325bc403448ea84b6db2269811a880e5118cd2ee2b6282a93d585016f`, LTX2.3`reviewed case`|
| distilled1.1 LoRA |7,605,507,256|`f5d4953f3386197a4b4f5abdb17616ff256171e8075c111d6e7d2dfa6e823b3a`, same revision|
| cached official FP8Gemma |13,205,434,827|`60216ce97c01c3a8753c2dfd0a89fc76e16fbe446d1a32ef8f1b528ac8bae466`, Comfy-Org/ltx-2`reviewed case`|
| new Relight LoRA |327,309,305|`c0d519f83681395d160e115829a9044d7d2ec013be6a2655834d235a2e866ebd`, pinned above|

Root explicitly approved existing official FP8Gemma instead of the graph's `comfy_gemma_3_12B_it.safetensors`; this is an **adaptation, not byte-identical upstream execution**. No duplicate26GB text encoder is requested. Only the327MB adapter is expected to be missing, subject to exact preparation checks. Public release remains local ComfyUI; hosted Relight stays unavailable until that exact capability exists. Private evaluation compute is solely the explicitly enabled test harness.

## Released detail-preserving finishing code

Primary source: [PaintAPlate](https://github.com/AInVFX/ainvfx-paintaplate/tree/31adafa85819b616c4f157dc88e6a96f5b9cfd9a), Apache2; [mathops.py](https://github.com/AInVFX/ainvfx-paintaplate/blob/31adafa85819b616c4f157dc88e6a96f5b9cfd9a/mathops.py), [workflow builder](https://github.com/AInVFX/ainvfx-paintaplate/blob/31adafa85819b616c4f157dc88e6a96f5b9cfd9a/tools/build_workflows.py). Existing source caches were reused.

`light_ratio`, `relight`, and `relight_frame` compute an edge-guided luminance ratio and smooth chroma ratio in linear light. The bounded field multiplies the original plate, retaining its texture and alpha; optional phase alignment compensates a small translation. The released node is `PaintAPlate_RelightTransfer`. The full `composite` workflow supplies original linear plate, half-resolution source/generated frames, radius8, strength1 and alignment enabled; its preview `comp` uses radius4. These are upstream recipes, not proposed tuning values.

This code does not generate new light, rain or geometry. It multiplies original pixels and would retain an object meant to be removed, so it is not a replacement for removal-specific lighting correction. The separate PaintAPlate FitToPlate replacement finishing audit is owned by the engine agent; it must not be conflated with this relight-transfer function. Strong generated misalignment can still contaminate the lighting field; framewise processing does not itself prove temporal consistency. Applying it to the current Canny output is an **unverified adaptation**. It must be optional and must not alter preserve-scene object swaps or saved historical recipes.

Minimal proposed experiment, not implemented:

1. Reuse one retained source/raw relight pair with identical frame range and known color encoding; no new model or render.
2. Invoke the pinned released transfer recipe, preserving original resolution/alpha and recording source/generated hashes and parameters.
3. Keep raw generated output separate from the transferred final result. Do not label changed RGB values as exact pixel preservation.
4. Review all frames for original car/body silhouettes, contact shadows, moving edges, lighting strength and temporal flicker. Rain absence remains a failure of weather generation even if detail improves.
5. Only after acceptance consider a narrow optional finishing control and a declared CPU helper in the portable bundle. This is a proposal, not current product behavior.

## Other concrete candidates and exclusions

| Candidate | Inspected release evidence | Decision |
|---|---|---|
| [gregtee2/ComfyUI_LTXRelight@0183a408](https://github.com/gregtee2/ComfyUI_LTXRelight/tree/0183a408c0d4016a84e1ab1e25fe3551f2bbd5d7) | Real HDRI sphere-card/preroll starter workflow; actual affine/flow alignment, delta and confidence-guard Python code. README expects a privately supplied `sphereball_version/lora_weights_step_05000.safetensors` and explicitly says no license file is included. | Not a licensed runnable drop-in for this release. Do not copy into production or substitute the official sun-ball LoRA for its different control convention. |
| [NeuralLightStage/LTX-2.5-relight-lora@e856841](https://huggingface.co/NeuralLightStage/LTX-2.5-relight-lora/tree/e856841fd8a293cd255f5cdfc387d572c9d8b618) | Public327,287,352-byte checkpoints plus training configs, but no README/license/inference workflow in inspected tree. Config uses2.5dev, reference-video training,768×416×49,30steps/CFG3 validation. | Not an established quality upgrade or distributable adapter contract. No checkpoint download. |
| Existing LTX2.5 Union-Control Canny + optional edited frame | Actual released native control recipe already implemented; preserves structural conditioning but does not guarantee generated body/material identity. | Keep truthful existing route and failed evidence. Edited-frame path requires its own visual acceptance. |
| Existing Ripple propagation | Released edited-first-frame graph; our actual cuboid run inserted the object but failed scene/tunnel-lighting preservation. | No blind prompt retry and no claim that propagation solves relighting. |

Follow-up supersedes the initial weather-search absence: the engine owner found the official LTX2.5 Water-Simulation adapter and its actual single-stage full-RGB video guide. Authorized access is now200. The existing Weather screen exposes it distinctly as `restyle_method=water`, with visible ADD WATER / Reference shows… / Edited shows… text,8steps/CFG1/source strength1,24fps,≤185frames, source/silent audio and no mask/reference/enhancer. Generic latent/Canny methods remain. Source is implemented; model availability and actual weather fidelity must be reported from its separate provisioning/render receipts, not inferred from this audit.

## Cached evidence

the retained review record contains the official model manifest/card; pinned Sphere Python/renderer sources, README/LICENSE/NOTICE; the inspected community pack README/config/alignment source; and NeuralLightStage training configs. These are research files, not weights. The specifically attributed manual sphere renderer/Three.js and PNG decoder adaptation are now included in production source as described above. PaintAPlate source remains in the existing the retained review record cache. Its inspected `mathops.py` SHA256 is `3df2e0b589487a506914562c969443df315acb16c3dd97bca70be69887d6d8bb`.

## First actual Relight result — scoped acceptance

Job the reviewed case, submitted through the actual app with the applied sphere, produced49frames at1280×704 from the owned512×320 forest stream. The engine owner reviewed all49frames: rock/stream layout stayed coherent, shading changed with lower-left cast shadows broadly consistent with the supplied back-right sphere, water kept moving, and no sphere imprint or obvious temporal flash appeared. Fine moss/rock texture and water detail were regenerated. This is a qualified generative-relighting pass, not exact calibrated angle, albedo, pixel identity or recovered source detail.

Recorded sphere149.684°/15.3915°/2; PNG SHA256 `b01fcab2d7102328447f8dd3a03e1e5de305286fdef847c9c984005088ebd6dc`. Actual source/sphere bundle hashes, API equality and path-only portability passed. Source-audio correlation was0.999030 at zero lag;32160 decoded16k source samples remained, with an extra AAC tail.  and adjoining workflow/bundle/audio receipts. This run used the isolated evaluation test harness; native GUI roundtrip and any direct hosted availability remain separate claims.
