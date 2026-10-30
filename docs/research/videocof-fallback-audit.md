# VideoCoF fallback audit — 30 October 2026

Read-only source/metadata audit for Genjutsu; no model downloads, inference, installs, or production edits. Current upstream commit: `f45b8009616b3ef8e2024a7da585249b4c74fc2b` (6 October 2026). Cached source/metadata receipts are under the retained review record.

## Decision

VideoCoF is released and runnable, but it is **not a reviewed-first-frame/reference-image replacement pipeline**. Keep it a separate text-instruction fallback. Finish the already-implemented official VACE first-frame case before paying for another stack. VideoCoF has relevant author-reported object-swap results, but no inspected evidence establishes our blue-cuboid replacement through a daylight-to-tunnel transition.

## What the released interface actually does

The [CLI](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/fast_infer.py) accepts a source video, edit instruction and frame/sampling options. It has no user mask, edited-first-frame, or object-reference input. The [Gradio application](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/examples/app.py) retains generic `start_image`, `end_image`, `validation_video_mask`, and `ref_image` parameters, but does not forward them into inference. They are not evidence of supported conditioning.

In [pipeline_wan.py](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/videox_fun/pipeline/pipeline_wan.py), `prepare_cot_video_latents` (lines 380–427) concatenates encoded source video with noisy grounding and edit segments. `__call__` (line 518 onward) uses aligned temporal RoPE and zeroes predicted noise on the source-conditioning prefix (around lines 705–740). The final edited segment is separately generated and decoded. This freezes the **conditioning video**, not all unedited output pixels. There is no final source RGB restoration or outside-mask composite. Scene preservation is learned. An external compositor would be an additional application step, and a source-object mask could clip a differently shaped replacement.

## Exact runnable reuse and integration cost

Reuse the complete modified pipeline, rather than loading its LoRA into generic native Wan sampling:

- `examples/wan2.1/predict_v2v_cot_json.py`: full-model inference entrypoint.
- `scripts/wan2.1/test_cot_lora.sh` with `USE_DMD=0`: released full-model invocation.
- `videox_fun/pipeline/pipeline_wan.py`, `videox_fun/models/wan_transformer3d.py`: source/ground/edit layout and temporal alignment.
- `videox_fun/data/dataset_image_video.py::derive_ground_object_from_instruction`: instruction-to-grounding text.
- `config/wan2.1/wan_civitai.yaml`: exact model loader layout.

The [published evaluation instructions](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/metric/README.md) select 50 Flow-UniPC steps, CFG 5, shift 3, BF16, VideoCoF LoRA scale 1 and repeated RoPE. This is a real released path without FusionX. The fast demo instead uses four steps/CFG 1 plus FusionX. Do not silently retain four steps when the accelerator is absent.

A bounded search of the official repository, native ComfyUI, Kijai WanVideoWrapper, and public VideoCoF repositories found no ready Comfy node/workflow for this full path. The pipeline's inherited `comfyui_progressbar` argument is not integration. The discovered RunPod repository is a deployment guide, not a reusable Comfy wrapper. A minimal faithful integration would isolate upstream dependencies behind a queued Comfy node/CLI, retain its modified transformer/pipeline, and add existing app transport/cancellation/provenance. It would expose video+instruction only, rejecting unsupported reference/mask claims.

Both released scripts need app I/O adaptation: random source start/stride is not an exact requested interval; generator seed does not seed that CPU input selection. The saver is hardcoded to 10 fps and omits source audio. Our selected frames/FPS and audio must therefore be supplied/restored explicitly. These are known source differences, not runtime-validated fixes.

## Pinned weights and licenses

Live Hugging Face metadata, not downloaded files:

| Dependency | Exact revision | Weight bytes |
|---|---|---:|
| Wan-AI/Wan2.1-T2V-14B: six transformer shards | `a064a6c71f5be440641209c07bf2a5ce7a2ff5e4` | 57,154,077,392 |
| Same repository: BF16 UMT5 `.pth` | same | 11,361,920,418 |
| Same repository: Wan2.1 VAE `.pth` | same | 507,609,880 |
| XiangpengYang/VideoCoF: `videocof.safetensors` | `766ff88960ec689d86695d96edb8a570ad16cfc0` | 1,246,458,124 |
| Optional fast-path FusionX T2V LoRA | see below | 316,822,496 |

The full documented **non-accelerated weight footprint is 70,270,065,814 bytes (70.27 GB)**; fast-path total is 70,586,888,310 bytes (65.74 GiB). Config/tokenizer files add approximately 21.55 MB. These are gross upstream footprints, not measured missing-cache bytes. Existing VACE/SCAIL/Animate checkpoints are not this exact base. Existing FP8 UMT5/safetensors VAE are not the documented loader artifacts; claiming reuse would require an explicit compatible-format/key/dtype check. No such conversion was performed.

[VideoCoF code](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/LICENSE), its [released adapter](https://huggingface.co/XiangpengYang/VideoCoF/tree/766ff88960ec689d86695d96edb8a570ad16cfc0), and the [Wan base card](https://huggingface.co/Wan-AI/Wan2.1-T2V-14B/tree/a064a6c71f5be440641209c07bf2a5ce7a2ff5e4) declare Apache 2.0. The optional accelerator requires separate treatment: the README-linked mirror's file SHA `c653087fa7c9163abdd1a4c627bfc483966c6d78a4426667d1185f860951c30e` matches original `FusionX_LoRa/Wan2.1_T2V_14B_FusionX_LoRA.safetensors` at [origin revision b9793a1f84727f2f69bdffecc2f50f0abfa746a6](https://huggingface.co/vrgamedevgirl84/Wan14BT2VFusioniX/blob/b9793a1f84727f2f69bdffecc2f50f0abfa746a6/README.md). Its card metadata says Apache, but its README explicitly restricts merged models to research/noncommercial use and identifies noncommercial components. Do not treat that contradictory accelerator declaration as cleared for the commercial default. The released 50-step path avoids it.

`verified-dependencies.json` and `fusionx-origin.json` retain file sizes, revisions and SHA256 values, including the byte-identical accelerator match. Metadata availability is not an inference or local-byte integrity proof.

## Relevant evidence and its limits

The [April 2026 paper, Table 9](https://arxiv.org/html/2512.07469v2#S13.T9), reports object-swap instruction/preservation scores of 9.10/8.39 and success 80.77%, versus VACE's 8.11/6.53 and 34.62%. These are the authors' benchmark and GPT-4o judgments, not independent current rankings or exact background-pixel guarantees. Its future-work section describes reference-driven identity editing as a future extension. Published swaps include people, clothing and signs; no inspected controlled example matches our cuboid/tunnel case. Training also uses filtered VACE-generated swap targets.

The October [evaluation release](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/metric/README.md) explicitly says its 240 public samples cannot be mapped exactly to the paper's original 200-sample table/subset, and the historical checkpoint/run mapping is incomplete. Its full-model and fast configurations are executable options, not proof of exact historical-score reproduction. Thus the benchmark justifies keeping VideoCoF on the fallback shortlist; it does not justify promising superior object geometry and scene preservation before a bounded app comparison.
