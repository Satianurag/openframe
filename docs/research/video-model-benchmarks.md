# Video, motion and speech model selection — 29 October 2026

Research snapshot, not implementation or inference approval. No weights were downloaded, models provisioned, tests run or renders submitted for this audit. Existing caches and rejected outputs remain intact. Image selection is covered in [image-model-benchmarks.md](image-model-benchmarks.md); the separate VFX audit must retain an LTX-core path for the competition bonus.

## Decision from the available evidence

| Task | Evidence-based candidate | Why it is a candidate | What prevents a stronger claim |
| --- | --- | --- | --- |
| General text-to-video, hosted quality ceiling | **Wan 3.0** through an actual Comfy Partner node | Highest point estimate on the current AA T2V-with-audio board | Top confidence intervals overlap; paid hosted service, not a verified downloadable model; does not establish masked-edit or identity-transfer superiority |
| Image-to-video, hosted quality ceiling | **Seedance 2.5** through an actual Comfy Partner node | Highest point estimate on the current AA I2V-with-audio board | Same benchmark limits; proprietary service and credentials/credits required |
| General self-hostable video quality candidate | **MiniMax H3 Base** | Highest-ranked open-weight entry on both current AA audio/video boards; native Comfy checkpoints and templates exist | Restrictive territory/commercial terms, a substantial new stack, and missing proprietary Context-IR/2K components mean the local template is not identical to the ranked service |
| Permissive, practical LTX generation/VFX branch | **LTX 2.5** as a candidate alongside the proven 2.3 path | Newer native Comfy support, improved AA generation results over 2.3, and compatible official task workflows | AA generation scores do not establish VFX quality; generation and inpainting must use the exact task recipe. Existing 2.3 results remain the actual project evidence until a complete newer implementation is validated |
| Motion transfer | **Wan Animate 2 Base**, with the distilled model as a separate speed profile | Official end-to-end driving-video model, native nodes, Apache-2.0 weights, and an author-run blind comparison favoring it over the older Animate model | No independent broad motion leaderboard found; the paper's real-time Lite result uses four H100s and must not be promised on this application's single GPU |
| Portrait + uploaded speech | **LongCat Video Avatar 1.5** | Released MIT weights, purpose-trained Whisper conditioning, strong lip-sync metrics in another team's newer comparison, and real Comfy wrapper code | Custom-node integration is required; the existing upstream example still targets Avatar 1.0, and single-H100 performance is not yet measured here |
| Speech research watchlist | **Kandinsky S2V 1.0 Pro distilled** | Best aggregate scores in its October paper, with good identity/image metrics | The linked official GitHub returned 404 and the public HF model listing exposed only tiny test pipelines, not the reported production checkpoints. Treat release availability/license as unverified, not deployment-ready |

These are task-specific recommendations, not one universal “best model.” A T2V preference score cannot rank mask preservation, lip synchronization, source-motion copying, or faithful product identity.

## Current independent generation benchmark

Both tables below were read directly on 29 October 2026 with a fresh Context.dev scrape rather than relying on stale search snippets. They are **AA-Video v2.1 with audio** boards. Artificial Analysis describes blind pairwise preferences from validated private evaluators; these are not VBench scores and should not be mixed with its silent-video board.

| Model | T2V Elo and 95% CI | T2V samples | I2V Elo and 95% CI | I2V samples |
| --- | ---: | ---: | ---: | ---: |
| Wan 3.0 | 1174 ±14 | 6,640 | 1108 ±17 | 5,234 |
| Dreamina Seedance 2.5 | 1156 ±14 | 6,749 | 1148 ±17 | 5,118 |
| MiniMax H3 (768p), marked open weights | 1160 ±14 | 6,766 | 1126 ±17 | 5,146 |
| MiniMax H3 Max | 1150 ±17 | 3,108 | 1116 ±17 | 5,144 |
| LTX 2.5 Fast | 949 ±16 | 3,780 | 917 ±18 | 3,276 |
| LTX 2.5 Pro | 944 ±16 | 3,599 | 913 ±18 | 3,332 |
| LTX 2.3 Pro | 885 ±16 | 4,272 | 838 ±19 | 3,379 |
| LTX 2.3 Fast | 838 ±17 | 3,902 | 831 ±19 | 3,378 |

Sources: [AA text-to-video board](https://artificialanalysis.ai/video/leaderboard/text-to-video), [AA image-to-video board](https://artificialanalysis.ai/video/leaderboard/image-to-video). Release labels on these pages are July 2026 for H3/Seedance 2.5 and August 2026 for Wan 3.0/LTX 2.5. H3's actual community-license release date is 2 August 2026; the leaderboard's service label is not a weight-release date. H3 Max is a separate service entry and must not be represented as the downloadable H3 Base checkpoint.

Wan 3.0's T2V rank range is 1–3, while H3's is 2–7. Their confidence intervals overlap. Seedance 2.5's I2V range is 1–2 and H3's 2–4. The correct conclusion is a shortlist with a leading point estimate, not statistically certain superiority in every case. Hosted Fast/Pro endpoint names also do not identify an exact locally reproducible sampler, quantization, prompt enhancer or checkpoint.

Comfy confirms actual hosted node availability for [Wan 3.0](https://comfy.org/wan-3.0/) and [Seedance 2.5](https://comfy.org/seedance-2.5/). No downloadable Wan 3.0 or Seedance 2.5 weights were verified in this audit. These can be optional paid-provider choices for the main competition, not an Open Weights Only claim.

## MiniMax H3: strongest measured open-weight generation candidate, with material conditions

The [official model card](https://huggingface.co/MiniMaxAI/MiniMax-H3) documents two distinct downloadable Base families: FL2VA for text/first/last-frame generation and Ref2VA for multimodal references. Native output is 24 fps, 32 kHz stereo, 4–15 seconds, with a default 768-pixel short side. The model has a 33B dense transformer and a Qwen3-VL-32B encoder. Its AdaLN branches can be precomputed/pruned for inference.

The same card explicitly says **Context-IR is a hosted orchestration system not included in the release**, and **2K regeneration is not yet open-sourced**. Context-IR is described as critical to quality. Therefore an entirely local 768p pipeline is possible, but a local quantized/turbo graph must not inherit the hosted leaderboard rank or a complete 2K/omni-product claim without its own evidence.

The [actual community license](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), dated 2 August 2026, excludes the **United States, EU, UK and Republic of Korea** from its ordinary grant, including hosted services and output use/display. It also requires attribution/product labeling and separate prior authorization above US$20m annual commercial revenue. This is **open weights under conditions, not Apache/MIT or unrestricted open source**. The [official license FAQ](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/QA-about-License.md) explains separate applications for excluded regions. A user's location alone does not establish that GPU hosting, recipients and a public competition demo satisfy these terms. Do not provision or expose it globally under the ordinary grant without resolving the deployment/license scope. This is a practical selection constraint, not a claim that every commercial use requires a fee.

Native support is real: the already pinned Comfy commit `79cf64c21a1dba50749945ba9fe2e3a692f45438` contains `comfy_extras/nodes_minimax_h3.py` and its model/VAEs/encoder. The already pinned template commit `14220b8bd3e86baa852959f17039613191e66656` contains [T2V](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/video_minimax_h3_t2v.json), I2V, continuation, multiframe reference and Ref2VA graphs.

The official [Comfy checkpoint package](https://huggingface.co/Comfy-Org/MiniMax-H3), revision `77aac5182eb85bb20930536bac73e498bbe2bfd7`, exposes:

| Component | Published bytes |
| --- | ---: |
| Pruned FL2VA INT8 transformer | 20,970,379,616 |
| Qwen3-VL-32B NVFP4/AWQ encoder | 15,687,142,551 |
| INT8 video VAE | 2,811,065,184 |
| FP32 audio VAE | 605,254,808 |
| Example eight-step turbo LoRA | 1,956,193,000 |
| **Example T2V total** | **42,030,035,159 bytes / 39.14 GiB** |

Ref2VA requires its own transformer of the same listed size; the encoder/VAEs can be shared. Full/pruned BF16 alternatives exist. These are remote metadata sizes, not downloaded or measured VRAM. The template's quantization and acceleration are additional differences from AA's service. New Qwen-VL/VAEs cannot be substituted with the existing LTX/Wan encoders.

## Motion transfer: Wan Animate 2

The [official release](https://huggingface.co/Wan-AI/Wan2.2-Animate-2-14B) is dated **7 August 2026**, with [Comfy's native integration announcement](https://blog.comfy.org/p/wan-animate-2-is-now-available-in) on 8 August. It consumes driving frames directly, eliminating the older external pose/face extraction stage, and adds text-driven viewpoint control. Base and distilled checkpoints are available under Apache-2.0. The reported streaming Lite system must not be conflated with the downloadable distilled Base checkpoint.

The [paper](https://arxiv.org/html/2608.06009v1), §§5.3–5.5, reports an author-run blind study over visual quality, motion, expressions, identity and naturalness: more than 70% of overall comparisons favor Animate 2 over the previous Wan Animate, a majority favor it over the compared Dreamina version, and it is broadly comparable to the compared Kling MotionControl. The excerpt does not establish current commercial-version equivalence or an independent leaderboard. It is nonetheless much more relevant evidence for motion transfer than an unrelated T2V ranking.

Real-time throughput in that paper is **24 fps at 400×720 on four H100s**, with separate encoding/decoding GPUs and two DiT GPUs. The official reference scripts default to eight A800s for 720p and report two A800s at 480p. Native Comfy offloading/quantization provides a different deployment path; single-H100 capability/latency remains to be validated after implementation is complete.

The [Comfy model package](https://huggingface.co/Comfy-Org/Wan-Animate-2), revision `e7181fe1896b7f2ce34120d1a3663413548240d7`, includes Base and distilled BF16 files of **32,789,894,104 bytes each (30.54 GiB)**, or their INT8 variants of **16,653,175,528 bytes each (15.51 GiB)**. Existing UMT5, CLIP-Vision-H and Wan2.1 VAE files are reuse candidates, subject to exact file/hash compatibility. No new weights were fetched.

The [official Base graph](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/video_wan_animate2.json) and [distilled graph](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/video_wan_animate2_distilled.json) use `WanAnimate2ToVideo` and `WanAnimate2Cache`, already represented in the pinned source. The distilled graph has its own checkpoint, not a renamed old Animate model. These graphs establish motion-transfer integration; they do **not** automatically establish the old model's masked character-replacement/relighting semantics. Preserve that existing route until the new route's supported task is explicit.

**Validation-found recipe correction, 30 October 2026.** Actual Base the reviewed job used 20 steps/CFG 1 without an acceleration adapter and was visually rejected for severe motion ghosting. This was not a matched official Base recipe. The pinned Comfy Base template uses a separate LightX2V acceleration LoRA with LCM at six steps/CFG 1; the original author's [unadapted demo defaults](https://github.com/Wan-Video/Wan-Animate-2/blob/3ad2fef7d61d6200c9c653e0fe47be7616b323f3/infer/wan_animate_2_demo.py#L117) are **40 steps/CFG 3**, with [Euler and shift 5](https://github.com/Wan-Video/Wan-Animate-2/blob/3ad2fef7d61d6200c9c653e0fe47be7616b323f3/infer/wan_animate_2.yaml). The unadapted Base profile now follows those defaults; its weights are unchanged. The separate distilled profile remains ten steps/CFG 1. Missing driving-motion captions now remain empty, matching the optional native-template field, rather than copying the appearance prompt into a second conditioning role. Explicit captions and sampler settings are retained. Seventeen targeted graph/compositor checks passed. Controlled retry the reviewed case improved the face but still failed visual acceptance because detached hands and later body smearing remained. A subsequent exact-template audit found that template node 590 center-fits the reference before both VAE and CLIP-Vision conditioning, whereas our original graph fitted only the VAE branch. The two branches now share an explicit target-sized center crop; two affected graph checks pass. The aligned-reference retry the reviewed case still failed on this fast-hand clip: detached hands and late face/body smearing remain. Thus the framing mismatch was real but did not explain this result. Legacy direct-motion the reviewed job was visibly stronger on the same source/reference/seed, while retaining finger/prop limitations. Fresh application motion selections therefore use the validated legacy Wan Animate path; both Animate 2 alternatives remain explicit choices. This practical case does not overturn the author benchmark or establish a universal ranking. Failed outputs, upstream template and deployment receipts remain under the retained review record.

## Uploaded speech: LongCat 1.5 versus Kandinsky and Wan S2V

The [LongCat Avatar 1.5 release](https://github.com/MeiGen-AI/LongCat-Video-Avatar-1.5-Page) is dated **21 May 2026**. Its [official model card](https://huggingface.co/meituan-longcat/LongCat-Video-Avatar-1.5) explicitly licenses the **weights under MIT**, uses Whisper-Large-v3 rather than Wav2Vec2, and requires its eight-step distilled mode for version 1.5. It supports image/audio/text and continuation, including multiple speakers. Its own study uses 508 image/audio pairs, six scenarios, two languages, realistic/animated styles, 770 raters and 13,240 judgments; these are developer-reported evaluations, not independent universal guarantees.

More useful comparative evidence comes from another team's [Kandinsky S2V 1.0 paper](https://arxiv.org/html/2610.19290v1), posted **13 October 2026**, Table 6. Lower mean rank and Sync-D are better; higher Sync-C is better:

| Dataset | Model | Mean rank across five metrics | Sync-C | Sync-D |
| --- | --- | ---: | ---: | ---: |
| EMTD | Kandinsky Pro distilled | 2.30 | 8.03 | 7.85 |
| EMTD | LongCat 1.5 | 2.90 | **8.41** | **7.39** |
| EMTD | Wan S2V | 6.40 | 7.01 | 8.47 |
| CelebV-HQ | Kandinsky Pro distilled | 2.40 | 7.19 | 8.15 |
| CelebV-HQ | LongCat 1.5 | 2.60 | **7.55** | **7.73** |
| CelebV-HQ | Wan S2V | 7.30 | 6.55 | 8.60 |
| HDTF | Kandinsky Pro distilled | 2.70 | 8.12 | 7.82 |
| HDTF | LongCat 1.5 | 3.00 | **8.48** | **7.34** |
| HDTF | Wan S2V | 6.80 | 7.49 | 8.10 |

Kandinsky wins the aggregate largely through its balance of identity/image/audio metrics; LongCat has better reported lip-sync metrics in all three datasets. These are one paper's evaluation pool and metrics, not confidence-bounded global rankings. Wan S2V is a plausible native-integration baseline, but the evidence does not justify calling it the best current speech model merely because its node is easy to use.

Kandinsky's reported distilled Pro is 21B; Lite is 2B. Table 5 reports 125-frame SD chunks on one H100 at 173 seconds for distilled Pro and 43 seconds for distilled Lite, with much longer HD runtimes. These are authors' sampling measurements, not this product's end-to-end latency. Crucially, the paper's linked [GitHub repository](https://github.com/kandinskylab/kandinsky-s2v) returned HTTP 404 during this audit, and live HF API searches for `kandinskylab`/`kandinsky-s2v` returned only `tiny-kandinsky-s2v-modular-pipe` and `tiny-kandinsky-s2v-distilled-modular-pipe`. The collection scrape was blocked. This does not prove no release can exist elsewhere; it means **production weights, license and Comfy compatibility were not verified**, so a deployable recommendation would be premature.

LongCat has an actual implementation path: [Kijai WanVideoWrapper's model loader](https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/main/nodes_model_loading.py) detects the 1.5 Whisper projection dimensions, and [LongCat nodes](https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/main/LongCat/nodes.py) provide `LongCatAvatarWhisperEmbeds`. This is a custom-node path, not native Comfy. The existing cached wrapper commit is `088128b224242e110d3906c6750e9a3a348a659b`; its `LongCatAvatar_audio_image_to_video_example_01.json` still uses the old Wav2Vec2/Avatar 1.0 combination. A correct 1.5 graph must explicitly replace those components and pin the Whisper loader dependency, not copy the old example unchanged.

Official LongCat weight metadata at revision `92016c71d5d318d0f5d84e4db30015a571484ab6` shows:

| New component | Bytes |
| --- | ---: |
| BF16 base-model six shards | 31,706,008,384 |
| DMD LoRA | 2,523,077,984 |
| Whisper-Large-v3 BF16/FP16 safetensors | 3,087,130,976 |
| **Selected BF16 subset** | **37,316,217,344 / 34.75 GiB** |
| Alternative INT8 base-model four shards | 15,880,382,936 |

The repository also contains redundant FP32, PyTorch and Flax Whisper variants; downloading the whole repository would waste space. Foundation text encoder/VAE reuse must be confirmed against the exact wrapper requirements. Official examples use two processes/GPUs; the wrapper's offload options suggest a single-H100 route worth implementing, but do not constitute a measured guarantee.

## Honest current project status and implementation order

1. **Keep proven results and task routes.** Existing LTX2.3 masked removal/replacement, Wan Animate motion, and corrected compositing have real scoped evidence. New benchmark research does not invalidate those outputs or permit deleting their provenance.
2. **Add Wan Animate 2 as a distinct motion profile.** It is the strongest directly relevant, permissively licensed, natively integrated upgrade found. Do not silently route existing character-replacement recipes to a different conditioning contract.
3. **Add LongCat Avatar 1.5 for the speech candidate.** Finish exact graph/package/audio controls before any resumed validation. The provisioned Wan S2V profile remains unverified; the earlier LTX single-pass speech attempt remains explicitly rejected for nearly static lips.
4. **Retain an LTX-core VFX path and evaluate an exact LTX2.5 implementation after the feature audit.** General generation rankings are not sufficient to choose a VFX model; root's separate editing benchmark research governs that comparison.
5. **Offer proprietary ceiling models only as explicit optional providers if requested.** Wan3/Seedance2.5 cannot be silently substituted into an open-weights/local workflow. H3 needs the license/deployment decision resolved first and a truthful local-vs-hosted pipeline label.
6. **Only after the full implementation gate reopens:** fixed source/prompt comparisons, first-frame fidelity, body/hand motion, identity, measured lip synchronization plus human inspection, exact output audio/time alignment, realistic latency/memory and exported workflow replay. A successful API response is not a quality pass. No such tests were performed during this audit.

Metadata sizes were read through the installed Hugging Face Python client; template/source inspection reused existing pinned repository metadata and fetched only bounded source JSON/text. No new model bytes were downloaded.
