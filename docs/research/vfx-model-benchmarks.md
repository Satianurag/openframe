# VFX model evidence — 29 October 2026

This is a dated research snapshot, not a claim of completed implementation or new render validation. Sources below were inspected on 29 October 2026. Publication dates, leaderboard update dates and retrieval dates are different facts. All implementation must finish before the final sequential app validation; no new test suite is requested.

## Selection for OpenFrame

Use the **complete official LTX 2.5 task workflows** as the current LTX-core VFX implementation candidate. Keep proven LTX 2.3 outputs and their exact exported graphs. The competition's LTX bonus requires LTX as the core video model; replacing it with an unrelated editor would not establish eligibility. [Competition requirements](https://comfy.org/open-source-higgsfield/).

This choice is based on the required model family, released task adapters and official Comfy integration. **No retrieved independent benchmark establishes LTX 2.5 as the world's best video editor.** General T2V/I2V preference rankings do not measure masked preservation, clean plates, alpha edges or relighting. Separate image and generation/motion/speech evidence is recorded in [image-model-benchmarks.md](image-model-benchmarks.md) and [video-model-benchmarks.md](video-model-benchmarks.md).

## Editing benchmarks and their limits

| Evidence | Date and protocol | Relevant result | What it does not establish |
| --- | --- | --- | --- |
| [VEFX-Bench project](https://xiangbogaobarry.github.io/VEFX-Bench/), [paper](https://arxiv.org/abs/2604.16272v2) | Paper April 2026; the accessible project table explicitly says **2 May 2026**. 300 edits across nine categories/32 subcategories; instruction following, rendering quality and edit exclusivity. | Aggregate: Kling o3 Omni 3.057, Kling o1 2.985, Runway Gen4.5 2.912, Seedance2.0 2.766, UniVideo 2.516, Wan2.6 2.146, VACE1.775. UniVideo's IF/RQ/EE are 2.294/3.266/3.091; VACE's 2.027/3.172/1.180. | This is an **older table**, not an October ranking. LTX2.5 is absent. VACE's rendering quality does not compensate for its much weaker edit exclusivity. |
| [VEFX live leaderboard](https://vefx-leaderboard.com/leaderboard), [benchmark](https://vefx-leaderboard.com/benchmark#evaluation-metrics) | Live site describes benchmark v1.0 frozen 3 August 2026. Aggregate is computed per item before averaging, with instruction-following weighted twice. | The retrieved leaderboard returned **“Failed to load leaderboard.”** | No current numeric ranking was available from this retrieval. Do not silently relabel the May project table as today's result, or recompute its aggregate from averaged columns. |
| [OmniXRef](https://oliver-cong02.github.io/OmniXRef.github.io/), [October paper](https://arxiv.org/abs/2610.22744v1) | Submitted 15 October 2026. Authors' multimodal-reference benchmark uses Gemini-3.8-Flash judgments of reference adherence, visual quality and source preservation. | Published overall 3.77; camera3.81, motion3.27, content4.48, style3.74, VFX3.55. Supports combinations of image/video/text reference attributes in the reported research system. | Author evaluation, not a human-preference leaderboard or a directly comparable VEFX score. The retrieved official page links the paper but no downloadable production checkpoint or inference repository. Deployment availability remains unverified. |
| [OpenVE-3M official repository](https://github.com/OpenVE-Team/OpenVE-3M), [paper](https://arxiv.org/abs/2512.07826v3) | Eight edit categories and a 431-pair benchmark; dataset/benchmark released. Repository inspected at current HEAD, last visible update April2026. | Useful coverage for global style, backgrounds, local changes/addition/removal, subtitles, camera edits and creative edits. | The official release checklist still leaves **OpenVE-Edit Model unchecked**. Dataset release is not model release. |
| [GRNEdit paper](https://arxiv.org/abs/2608.16328v1) | August2026 author evaluation on OpenVE-Bench. | Reports 4.03 for2B and4.18 for8B, with less than3% conditioning parameters and0.6M training pairs. | No verified downloadable production checkpoint/Comfy recipe was established here. The result cannot be compared directly with VEFX or Arena Elo. |

## A real alternative editor, without overstating its rank

[UniVideo](https://github.com/KlingAIResearch/UniVideo) has released inference/training code and [public weights](https://huggingface.co/KlingTeam/UniVideo). The model card is tagged Apache-2.0; the official code repository is MIT. It combines a HunyuanVideo backbone with Qwen2.5-VL. Its older VEFX result makes it a useful challenger, not a proven October winner.

[RunningHub's Comfy integration](https://github.com/HM-RunningHub/ComfyUI_RH_Univideo) actually implements text-directed video editing and image-reference video editing. It does **not** implement every task in the original paper. It requires Hunyuan components, the UniVideo Variant1 checkpoint and Qwen2.5-VL-7B; its recommended24GB configuration uses INT8. That memory recommendation is the wrapper author's statement, not this project's measurement. Dependency licenses and the exact quantized configuration must be retained rather than treating one repository's license badge as the entire stack's license.

Do not add a menu item until the model, dependency manifest, graph and output path are implemented. No UniVideo weights were downloaded for this audit.

## LTX2.5: exact task support rather than prompt labels

The [official Comfy workflows](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/master/example_workflows/2.5) include generation, two-stage inpainting/outpainting, ingredients, union control, motion tracking, single-stage IC-LoRA video-to-video, native-resolution tiled rendering/upscaling and HDR workflows. The in/outpainting template explicitly reuses the compatible2.3 IC-LoRA; a nonexistent2.5 adapter ID must not be invented.

The installed Hugging Face CLI listed the following official model repositories on29October. These are actual released adapter names, not a list of independently benchmarked winners:

- [Alpha Gen](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen): output a matte and composite it with **original source RGB**.
- [Clean Plate](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Clean-Plate): dedicated clean-plate candidate.
- [Pixel Spatial Upscaler](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler), [Refine Details](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details), [Restore](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore), [Deblur](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Deblur), [Decompression](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Decompression): distinct restoration recipes, not interchangeable strengths on one generic edit.
- [SDR to HDR](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR): requires correct HDR encoding/metadata; an8-bit SDR MP4 renamed HDR is not this operation.
- [Layout to Render](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render), [Ingredients](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients), [Day to Night](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night), [Colorization](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Colorization), [Water Simulation](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation), [Slow Motion Control](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Slow-Motion-Control), [Cinemagraph](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph).

Alpha Gen's official constraints are consequential: an **empty prompt**, native-resolution stage1 only, dimensions padded to multiples of32, frame count8n+1, no more than145frames or1920×1088. The model selects its foreground; it cannot be directed to an arbitrary object with a text prompt or mask. Longer shots require explicit chunking with seam validation. The authors recommend H100/B200-class hardware for full-HD145-frame inference. These are published constraints, not a measured runtime guarantee.

The current LTX2.5 base repository revision observed through the Hub is `49b093a39c19169a8a81721dcc541e07e945232f`; AlphaGen is `4cc554f7f8dd858b50e80f1d37d70ce0103f5c94`. Runtime manifests must pin the exact component files, not just these marketing names. LTX2.5 uses matching transformer, Gemma4 encoder, video/audio VAEs and upscaler components. The [LTX community license](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x) and repository access requirements remain separate from the application code's license.

## Auxiliary tools and hardware constraints

[NVIDIA's Comfy VFX integration](https://comfy.org/nvidia-vfx/) supplies super-resolution, frame generation and SDR-to-HDR. Its nodes are Apache-2.0, while the underlying NVIDIA library is proprietary. The page requires RTX hardware and40-series-or-newer for frame generation. An H100 allocation does not establish compatibility. Do not claim this path works merely because CUDA exists.

October's [FlashVSR+ paper](https://arxiv.org/abs/2610.17552v1) is a newer restoration candidate than older SeedVR2/FlashVSR comparisons. Its [official inference repository](https://github.com/OpenImagingLab/FlashVSR_Plus) and [Turbo/Base weights](https://huggingface.co/ruchangyao/FlashVSR_plus) are released. The authors report spatially untiled 4K on a 24 GB RTX4090, up to 2× DiT acceleration and 45% lower peak memory; those are author measurements, not this project's measurements or an independent quality ranking. The released CUDA-only pipeline requires dimensions divisible by128 and offers explicit segmented decoding for long videos. The current app implements LTX's native upscaling recipes; FlashVSR+ is not mislabeled as an implemented provider.

## Task-specific auxiliary choices

- **Frame interpolation:** [LDF-VFI](https://github.com/xypeng9903/LDF-VFI), [CVPR2026 paper](https://arxiv.org/abs/2601.14959v2), has released sequence-level interpolation code and weights. The implementation uses the pinned ComfyUI-Tween integration with actual source intervals and target timestamps. Its output-frame count is computed from the last source-frame timestamp, without inventing another final-frame interval. This is not evidence that it wins every current interpolation benchmark.
- **Depth:** the implemented default is Apache-licensed Video Depth Anything Small. ViGeo1.1 is an explicit research option: its published KITTI300 AbsRel is0.052, but its weights are CC-BY-NC4. The preview palette and side-by-side option change presentation; raw depth remains a separate output. The current bounded wrapper has a300-frame/1280-long-side limit, rather than claiming Higgsfield's1800-frame limit.
- **Layers:** [Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered) provides a released native RGBA decomposition model and [official Comfy graph](https://docs.comfy.org/tutorials/image/qwen/qwen-image-layered). It regenerates content, including hidden areas; it is not exact pixel segmentation. Entry zero is the regenerated full image. Subsequent layers are composited back to front, with reconstruction error recorded.

## Prompted foreground selection

Automatic LTX AlphaGen and text-selected foreground extraction are different operations. The signed-in reference UI exposes a subject prompt; sending that prompt into AlphaGen's required empty conditioning would not implement the feature.

The selected semantic path is **SAM3.1 concept tracking → explicit trimap → ViTMatte Base refinement**, following the published selection/refinement pattern of Matte Anything. It uses a current released tracker with an older specialized matte refiner, not a claimed October matting champion. Alpha temporal flicker and incorrect/absent subject selection must be evaluated with real videos. Model-specific licenses remain attached to the components; SAM3.1 uses Meta's custom SAM License, not Apache.

[SAM3.1's official release notes](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md) are dated27March2026. Relative to SAM3 they report improved VOS performance on six of seven listed benchmarks (MOSEv2 J&F60.3→62.3; SA-V test84.4→85.1), with mixed promptable-concept results. The approximately7× H100 speedup is specifically for128 tracked objects; it is not a general single-subject latency guarantee.

[SAM2Matting](https://github.com/FudanCVL/SAM2Matting), an ECCV2026 release, has actual SAM2/SAM3 checkpoints and interactive text support. Its code and weights are CC-BY-NC-SA4 for noncommercial research. [MatAnyone2](https://github.com/pq-yang/MatAnyone2) focuses on human matting and declares the NTU S-Lab license; describing it as MIT would be incorrect. These are useful research comparisons, but they are not silently used as unrestricted commercial defaults.

## HDR output semantics

The implemented saver accepts native float data from the pinned Comfy [ImageColorSpace implementation](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy_extras/nodes_images.py). `HDR` means Rec.2020 HLG with a1000-nit reference display. Video export uses real HEVC Main10 or ProRes422HQ through RGB48-to-10-bit conversion, with explicit primaries, transfer and matrix metadata. Out-of-range HLG code clipping is counted in the result metadata.

EXR export instead converts ACEScct into scene-linear ACEScg/AP1/D60, preserves extended finite values and records chromaticities. It writes one half-float frame at a time into an opt-in ZIP, using lossless EXR ZIP16 compression; it never passes through an8-bit image. The archive includes a frame-rate/geometry manifest, while audio remains in the separate SDR preview. Encoder metadata and high-dynamic-range values still require final runtime verification.

## Final validation contract

After **all requested coding** is complete, validate each app sequentially with actual media. For VFX inspect requested change, unedited-region preservation, temporal stability, alpha boundaries, moving shadows, occlusions, first/last frames and audio alignment. Record actual model revision, precision, prompt pipeline, sampler, source interval, outputs and exported workflow. Compare the relevant task outcomes; a successful request, generic beauty score or screenshot of a control is insufficient. Comfy Cloud is wiring-only per the user's instruction.
