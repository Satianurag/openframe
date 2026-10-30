# Genjutsu replacement: released-code adaptation

30 October 2026. New profiles are source-complete candidates, not visually verified video results.

## Preserved failure

Actual the reviewed job deleted the toy car without inserting the blue block and showed a dark edited-region patch. Its executed graph used LTX2.5 In/Outpainting (not Clean Plate), the correct tracked mask/caption, enhancement off, nonzero noise, and97frames24fps. Native guide/AV source does not freeze the target video latent. Evidence is retained in the retained review record. No preblend output existed, so the diffusion versus Laplacian contribution could not be separated.

## Primary candidate: PaintAPlate / Ripple

[PaintAPlate](https://github.com/AInVFX/ainvfx-paintaplate/tree/1f4a5706e4fbec2f6bb5ae763460d03551392d15), Apache2, is an actual Comfy application with complete [`shot.json`](https://github.com/AInVFX/ainvfx-paintaplate/blob/1f4a5706e4fbec2f6bb5ae763460d03551392d15/web/workflows/shot.json) and [`tools/build_workflows.py:shot`](https://github.com/AInVFX/ainvfx-paintaplate/blob/1f4a5706e4fbec2f6bb5ae763460d03551392d15/tools/build_workflows.py#L387). Its addition path propagates an edited first frame; In/Outpainting is used separately for erasing.

[WepeNerd/LTX-Ripple](https://huggingface.co/WepeNerd/LTX-Ripple/tree/76abac5ede8a3415b9d1cd803843a38ecb351600) file `LTX25_Ripple_v11.safetensors` is654,443,392bytes, SHA256 `bde543610144e5bba78782fb0ac18daa663fc087c2212244b8116deb1925ee2a`. Its LTX Community license is retained separately from PaintAPlate's Apache code license in `docs/licenses/`. The author's complete `Workflow_example/LTX_Ripple_FFAF_Edit_v14.json` corroborates the same native inference contract.

The released graph replaces only frame0 of the RGB source batch with the reviewed edited frame, applies Ripple1.35, feeds the batch into native `LTXAddVideoICLoRAGuide`, then uses eight Euler/simple steps, CFG1, separate empty audio latent, AV sampling, guide cropping and decode. There is no green-hole source, In/Outpainting adapter, enhancer or Laplacian refinement.

Our isolated `engine/ripple_models.py` / `ripple_workflows.py` retain that core. Native fixed two-input ImageBatch replaces upstream's dynamic batch node. Existing media loaders fit source and full edited frame to the same center-cropped canvas; the reference must first match the video's original dimensions. Cached BF16 transformer/encoder and standard BF16 video VAE are retained instead of upstream INT8 ConvRot transformer/encoder and conv BF16 VAE. This is disclosed as an adaptation, not bit-identical upstream execution. Exact dependency hashes remain in the manifest.

The final composite uses our existing source SAM2 mask, explicit margin and feather. PaintAPlate's separate matte graph instead tracks generated frames with SAM3.1 and grows changed regions through `FollowMatte` (thresholded shot/base difference near the tracked region, with a previous-mask fallback). That algorithm is not copied here. If a new silhouette escapes the source mask, raw-versus-composite outputs allow the problem to be identified rather than attributed blindly to diffusion. Both outputs are available; no lighting rematch is applied. Source audio is retained over the selected interval.

The profile is bounded to121frames,1920longest side and2,088,960pixels. Upstream explicitly notes heavy-occlusion/large-change limitations. No quality guarantee is inferred from its demos.

## Reviewed first-frame proof

Root submitted Image Studio the reviewed job and accepted one coherent blue cuboid. Exact600×1066 output the reviewed case, SHA256 `d2e31f7f5b46532118e778c1718f8ab61872e12a5fa948e4b1ab28b486a57e47`. All591,860 pixels outside the submitted mask preserve original RGBA exactly. Source is frame0 of the same clip.  This is image integrity, not video acceptance.

## Selectable fallback: native VACE14B

[Official Comfy template](https://github.com/Comfy-Org/workflow_templates/blob/abb9cf6477b59c52dbe234c67f82318dadd872b2/templates/video_wan_vace_inpainting.json), MIT, uses masked source + appearance reference through WanVaceToVideo, shift5,20steps,CFG6,UniPC/simple. Our separate profile does not inherit1.3B or Lightning settings. Checkpoint `Comfy-Org/Wan_2.1_ComfyUI_repackaged` rev`123acf1cc74bccbb9bfff8ac1ee72edc08c2341d`, `split_files/diffusion_models/wan2.1_vace_14B_fp16.safetensors`,34,675,323,640bytes, SHA256 `f202a5c59b8a91ada1862c46a038214f1f7f216c61ec8350d25f69b919da4307`, Apache2 model card. Shared UMT5/VAE reused. The checkpoint is installed on the evaluation host; public use requires explicit Local provisioning. Actual97-frame appearance-reference the reviewed job preserved the tunnel lighting/scene but produced a blue car silhouette rather than the requested cuboid, already visible in raw output. It fails object-shape acceptance; no sampler sweep follows.

## Other runnable-source checks

| Candidate | Evidence and decision |
|---|---|
| [VideoCoF](https://github.com/knightyxp/VideoCoF/tree/f45b8009616b3ef8e2024a7da585249b4c74fc2b) | Apache2 code; actual pipeline accepts source video and instruction, not an edited frame/object reference/mask. The documented50-step path totals70,270,065,814 published weight bytes before cache reuse. Fast FusionX adds316,822,496bytes and has conflicting Apache-card versus research/noncommercial README terms. No Comfy wrapper found in the bounded search. It is not a small reference-guided drop-in; see [the exact source/weight audit](videocof-fallback-audit.md). |
| [Kiwi-Edit](https://github.com/showlab/Kiwi-Edit/tree/178f3f4f8221d7598fcc21875c847d6cf6323c4e) | MIT official code; released5B instruction/reference weights; Yogurt wrapper has complete JSON. Weight license metadata is absent; Qwen2.5-VL3B base has research/noncommercial terms. Both inspected Comfy wrappers lack root licenses. Not selected as commercial default. |
| [WanVaceAdvanced](https://github.com/drozbay/ComfyUI-WanVaceAdvanced/tree/049213cf21144317a56ab270099b78f879d95a80) | GPL3 nodes, complete workflows, reference/control separation and Phantom options. Real code, but extra merged weights are not evidence of better insertion on this case. |
| [Wan-VACE-Prep](https://github.com/stuttlepress/ComfyUI-Wan-VACE-Prep/tree/f04e44cd24204ba03bfd27bd97711686333c1138) | MIT preprocessing and examples; gray masked source preparation is not a new insertion model. |
| [User-ranked Genjutsu entry](https://github.com/sirioberati/Genjustsu-Open-Source-Workflow/tree/40fd6615c2b7d940d4d7060e82de522292eefe99) | MIT app uses paid Enhancor Seedance/Replicate services, not an open-weight Comfy insertion workflow. |
| VideoAnydoor / PISCO / Point2Insert | Inspected trees expose demo/project material rather than a usable released inference stack; papers alone were not treated as integrations. |

Small upstream sources are cached once under the retained review record. No full duplicate checkout or laptop weight download.


## Explicit known-first-frame VACE control (source complete; quality pending)

The optional `vace_reference_mode=first-frame` reuses [official VACE FrameRefExpand](https://github.com/ali-vilab/VACE/blob/48eb44f1c4be87cc65a98bff985a26976841e9f3/vace/annotators/frameref.py) and [Composition(extension,repaint)](https://github.com/ali-vilab/VACE/blob/48eb44f1c4be87cc65a98bff985a26976841e9f3/vace/annotators/composition.py), Apache2. Native Comfy batch/mask nodes put the complete edited image at control frame0 with a zero generation mask. Frames1–96 retain the original source and tracked generation masks. The appearance-reference latent is omitted. Original source and final compositor support remain independent, including frame0. The existing appearance graph is unchanged. No new weights, sampler or proprietary effect recipe is introduced.

The full reference must match the source's native canvas; accepted image the reviewed case is600×1066. The isolated576×1024 appearance image is rejected in this mode. The new candidate changes only reference and reference mode from the20-step/CFG6/seed2837573547,97@24 appearance case.

This is learned conditioning, not exact first-frame restoration. Both [official VACE mask encoding](https://github.com/ali-vilab/VACE/blob/48eb44f1c4be87cc65a98bff985a26976841e9f3/vace/models/wan/wan_vace.py#L157) and pinned native WanVaceToVideo use nearest-exact97→25 temporal mask sampling, whose first sample is input frame1. The zero-mask edited frame0 still enters the separately encoded inactive-video stream. We preserve this released behavior; we do not claim a hard-frozen first latent frame or silently widen its mask interval.

Fourteen graph invariants and the actual frontend request helper pass. The deployed native CPU proof also passes ten control-node checks on Comfy:97-frame assembly, edited frame0, source/mask tails, unchanged final support and blanked edit regions. It performs no VAE encoding or diffusion; actual output quality remains pending. Evidence/draft/portable API graph: the retained review record. All supplied Higgsfield media and derivatives remain private validation inputs, excluded from public galleries/releases.
