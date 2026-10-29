# Validation record

Validated on 29 October 2026. The complete initial implementation preceded testing. Later changes addressed observed failures; real GPU outputs were reviewed separately from API/test success.

## Verified product paths

| Area | Evidence and scope |
|---|---|
| UI reference | Public Higgsfield HTML, opened component DOM, computed styles and screenshots captured. Matched desktop/mobile review completed; intentional branding, supported-model, no-auth and working-mobile differences are documented in DIRECTION.md. |
| Frontend | Production build and final interaction checks; 19 control checks, 8 actual-result checks, 4 pagination checks and 6 new Cloud/settings checks passed without browser errors. Edit-margin defaults, explicit recipe reuse and exported values were also checked. Comparison playback, seeking, speed, fullscreen, mobile controls, recipe reuse and real downloads exercised. |
| Actual UI generation | Generate was clicked in the browser for real Modal jobs, followed by result/comparison and workflow/full-project downloads. Full recording and timestamped events are retained. |
| Service | 12 isolated backend integration/regression tests passed, including validation, lifecycle, media, persistence and stored-graph export behavior. Inference in those unit scenarios is explicitly a test double; the separate GPU evidence below is real. |
| Engine | Regression and media/lighting checks passed, including continuous contour smoothing, unchanged generated detail, exact protected-exterior preservation and tracked edit-margin support. All 12 supported model/task graph variants validated against the live pinned ComfyUI node schema. |
| Packaging | Two source-package tests passed, covering exclusions, fonts, archive integrity and unchanged-output reuse. Final archives carry per-file integrity manifests. |
| Modal | Private H100 worker actually executed the models. Warm-worker reuse, asset upload/download and application invocation passed. Progress no longer reports completion before the host finishes downloading. |
| Local transport | The native Comfy HTTP/WebSocket transport executed inside Modal. Local Comfy schemas and unsaved canvas imports were checked. No Mac video-inference performance claim is made. |
| Model switching | LTX Fast, LTX 2.3 and Wan VACE ran through their actual graph routes. Wan opening-frame conditioning was corrected and visually verified separately from loose reference-image conditioning. |
| Mask tracking | Real SAM2 on MPS and CUDA; the expanded tracked support passed 97-frame removal and 49-frame replacement tests on downloaded Higgsfield examples. Optical-flow/static and alignment checks also passed. The tests cover their recorded segments, not arbitrary motion. |
| Hosted Comfy Cloud | Actual native LTX generation and an app-submitted 49-frame masked edit completed through CLI OAuth. Eight targeted Cloud transport/CPU tests and hybrid-bundle regression checks passed. See the Cloud record below for exact execution boundaries. |
| Audio | Native LTX 2.3 generation produced stereo 48 kHz AAC with nonzero audio in a real 49-frame clip. Source-audio trimming/preservation was checked with deterministic media fixtures. |
| Workflow export | Real removal exported 44 nodes/71 links; replacement exported 23 nodes/33 links. API/UI graphs and portable inputs were checked against stored executed graphs. Unsaved ComfyUI canvas imports were topology-verified. |

## Final application examples

The hero removal is job `9a44a1f19f0743569d5ba4c9adfd49b0`: LTX 2.3, 1024×640, 49 frames at 24 fps, seed 44, static refined mask, two-stage graph, inward feathering and scene-lighting matching. Every decoded frame was inspected. The vase and its cast shadow are removed without an obvious persistent colour patch, ghost or red rim. Measured Comfy execution was 18.890 seconds on this warm H100 run; provisioning, queue and transfers are excluded. This is not a general latency guarantee.

The shadow-fixed application replacement is `3e609d6da5484a24b1d9337e31c9f3b4`: seed 46, 1024×640, 49 frames at 24 fps, full-resolution single-stage LTX 2.3. A controlled raw-decoder comparison proved the earlier staircase came from the mask composite, not generated shadow detail. Continuous signed-distance contour smoothing removes it without filtering the footage. Every output frame and shadow crop passed independent review: stable knight/base/table detail, no recurring staircase, obvious halo or boundary pulse. The actual graph records `feather_method=smooth-inward`; measured warm H100 Comfy time was 79.59 seconds. Earlier jobs `942e8b6f52314b65a7ec736d2e3c28d2` and `fe826683f5cb45b3a48ad32782115365` remain historical evidence.

## Three downloaded Higgsfield videos

Exactly three public example clips were downloaded from URLs exposed by the Higgsfield Genjutsu page, verified HTTP 200, hashed and fully decoded. Original camera-capture provenance is unverified. These are private validation inputs and are excluded from the source archive, public example bundle and gallery. Full clips are 15.04, 22.00 and 14.75 seconds; the tests cover only the ranges below. Every generated frame in each selected segment was visually inspected.

| Input / selected range | Actual application job | Result |
|---|---|---|
| Person handling paper, 0–4.0625 s; 65 frames at 16 fps | Wan `16ba3e12369543cd9341bdb64ecb6d63` | Qualified stylization pass: broad action retained, with softened fingers/face/paper detail and overly yellow highlights. The practical LTX comparison changed the person, props and action too much and was rejected; Wan was retained. |
| Toy car / train window, 0–4.0417 s; 97 frames at 24 fps | LTX removal `8e0d49752cb842db8d410de6fb67b672` | Pass: car/roof/taillight residue removed across the segment; sill and daylight-to-tunnel change remain coherent. Fill reconstructs the hidden scene; it is not ground-truth recovery. |
| Outdoor car / person, 12.5–14.5417 s; 49 frames at 24 fps | LTX replacement `b04aabb6da064b67926067c684b94d67` | Qualified pass: stable red-car replacement and foreground motion/disocclusion; old black outline removed. Car geometry changes, and nearby hand/card edges soften. This is not exact same-car recoloring. |

Initial car attempts completed technically but failed visual review because SAM2 tightened the selected region to the object silhouette and feathering restored original perimeter pixels. The explicit **Edit margin** fixes that support loss: tracked defaults to 12 pixels, static to 0; generation margin remains separate. Legacy node graphs default to zero edit margin. Reruns kept prompts/seeds unchanged and recorded margin 12. Source-audio technical comparisons show strong waveform correlation after accounting for AAC priming/timestamps; no subjective listening certification is claimed.

## Hosted Cloud record

Real Cloud generation probe `e2dac4de-77ae-4cb1-be3a-25e77a6c3f58` produced 17 frames at 512×320. Application job `5bf5ddd741ed4103b51960fe884b98b3` used exact named LTX 2.3 base/encoder/LoRAs through Cloud prompt `bb477775-e259-4fcd-a2d6-e65352e33ab8`, producing 49 frames at 1024×640/24 fps. All frames passed composite/boundary review. Its chess-piece silhouette is bishop/crown-like rather than the requested horse-head knight; it proves actual Cloud VFX execution, not precise prompt adherence. The 279.35-second provider measurement includes local preparation/transfers/compositing and is not pure GPU time.

Diffusion and native model nodes run on hosted Comfy Cloud. Source/mask preparation, final mask compositing and audio/encoding run on the app host. Optional SAM2 uses the configured local ComfyUI's exact `add_new_mask` initialization and SAM2.1 small checkpoint; it does not substitute native Cloud nodes that convert a painted mask to points. Static/flow modes require no local model runtime. The local SAM2 bridge completed a real 49-frame MPS probe. The requested 97-frame Cloud removal `63de4f21bd1e4998b8229f7eeb1c6b86` failed at the hosted execution-time limit after 709.53 seconds of provider execution, without an output. The exact published threshold/failing node was not exposed. A separately requested 49-frame job `c7c635d64f7a4f5db022755722f6f3c3` succeeded over 0–2.0417 seconds at 576×1024/24 fps; sampled aligned images show clean removal and the full clip decoded successfully. This does not establish the failed longer scope or full-frame perceptual review. Source audio is present; exact Cloud alignment remains unverified. The final generated-audio check `b1ddc70ea1b546b1879d18e4f91a1dfd` was cancelled at the user's request, so end-to-end Cloud native-audio export remains unverified. No further Cloud versions were tested.

Cloud bundles distinguish the canonical complete local-replay graph, actual native Cloud graph and CPU-processing manifest, with prepared inputs and tracking evidence where applicable. The native Cloud graph returns intermediate lossless frames; it alone does not produce the final composite. A static full bundle passed CRC, graph/input checks and a token/signed-URL/path privacy audit. Hosted node/model availability is checked before submission. CLI OAuth is the end-to-end verified authentication path; SDK API-key and custom deployment paths remain implemented and structurally tested without account-specific execution proof.

Earlier Modal/native ComfyUI verification also includes LTX Fast text/image animation, LTX 2.3 image animation and native-audio generation, Wan masked editing, reference generation, corrected first-frame animation and a warm painterly video restyle. The painterly example does not prove precise watercolor-paper or ink reproduction. The LTX weather route demonstrates a coherent restyle, but convincing added rain and exact scene preservation were not established. Cinematic, rainy-window and lamp cards are clearly labelled short illustrative generations, not proof of their named transformation presets or long-duration motion.

## Correct model and reproducibility

The VFX graph uses `ltx-2.3-22b-dev.safetensors`, `ltx-2.3-22b-distilled-lora-384-1.1.safetensors`, `gemma_3_12B_it_fp8_scaled.safetensors` and the official `ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors` adapter. LTX Fast is a separate lightweight generation profile and cannot be selected for masked editing. LTX 2.5 was audited as an available alternative, not benchmarked or advertised as implemented; see MODEL_AUDIT.md.

The local/Modal replay environment pins ComfyUI to `79cf64c21a1dba50749945ba9fe2e3a692f45438`; LTX nodes to `220e1d45aa0469f518e982102fca4dca92a61862`. Hosted Cloud manages its own runtime; these local pins do not attest to its server version or installed weight-byte hashes. Bundles include exact executed settings/graphs, portable source/mask paths, necessary model/node requirements and expected upstream model hashes. Source/mask bytes were checked against bundle hashes. Expected model hashes are metadata, not a claim that every installed weight file was independently rehashed. The 1,308,778,338-byte gated adapter download was explicitly SHA-256 verified before upload; its digest is `73dd0841c0d4f0eb26fb1f017781b841b2752021944ac5ecefe57917f6dae6b5`.

Static-mask bundles correctly omit SAM2 dependencies. Stored-job exports preserve the executed graph after template updates, changing only portable input filenames. Retrying a recipe intentionally uses the current implementation. Legacy optional node defaults remain supported.

## Evidence locations

- `artifacts/validation/frontend/recording/`: actual 165.84-second UI recording, event timings, requests, screenshots and exported canvases. The edited demonstration clearly labels accelerated waiting.
- `artifacts/validation/frontend/real-result/`: eight result interaction checks and download verification.
- `artifacts/validation/frontend/fidelity/`: matched component screenshots and ComfyUI import proofs.
- `artifacts/validation/app-removal-final/9a44a1f19f0743569d5ba4c9adfd49b0/`: complete hero result, all-frame contact sheet, graph, independent observations and bundle check.
- `artifacts/validation/app-replacement-final/fe826683f5cb45b3a48ad32782115365/`: actual replacement, full-clip critique and bounded feather comparisons.
- `artifacts/validation/app-replacement-contour/3e609d6da5484a24b1d9337e31c9f3b4/`: current shadow-fixed result, actual graph and all-frame review.
- `artifacts/validation/shadow-edge-diagnosis/`: raw-decoder isolation and continuous-contour regression evidence.
- `artifacts/validation/higgsfield-real-video/`: three private sources, HTTP provenance/hashes, exact segment recipes and failed/passing reviews.
- `artifacts/validation/comfy-cloud/`: live catalog, actual hosted jobs and hybrid export checks.
- `artifacts/validation/app-replacement-margin/942e8b6f52314b65a7ec736d2e3c28d2/`: historical replacement and controlled shadow comparison. Its additional UI recording is in `frontend/recording-shadow-margin/`.
- `artifacts/validation/engine-validation-summary.json`: real render cases, output hashes, Modal call IDs, timings, scoped reviews and regression/schema evidence.
- `artifacts/validation/ltx-adapter-integrity.json` and `ltx-vfx-expected-checksums.json`: model provenance and the distinction between expected metadata and byte verification.
- `artifacts/validation/launcher.json`: free-port selection, proxy health, allowed-origin behavior and clean child-process shutdown.
- `docs/CRITIQUE.md`: final decisions followed by retained failed rounds and corrections. Rejected outputs are not promoted as successful showcases.

## Boundaries of verification

Hosted Cloud was exercised through CLI OAuth as documented above; API-key/custom-deployment execution is not verified. Docker Compose configuration passed; the Docker daemon was unavailable, so container execution was not tested. Browser/platform emulation is not native Windows, Linux, iPhone or Safari-device certification; Firefox remains unverified. The portable graphs require their documented model files and node packs; local canvas warnings about missing weights were retained rather than hidden.

Output is lossy H.264: outside-mask preservation is not a claim of byte-identical encoded pixels. Include affected shadows and surrounding margin in the editable mask. Prompt-led presets vary with source, strength and model; the demonstrated short clips do not establish universal effect quality. Public publication, competition registration/social posting and submission have not been performed.

## Prepared release verification

The final frontend production build passed. The 70.396-second demonstration is 1920×1080/24 fps with stereo 48 kHz AAC; captions and selected full-size frames passed independent visual review. The native-audio section contains nonzero generated audio without measured clipping; other sampled sections are silent. No subjective listening-quality certification is claimed.

The examples archive contains 66 payload files plus its per-file hash manifest. CRC, safe relative paths, input/result hashes and graph semantics passed independent checks. It includes the preferred removal and replacement above, the approved warm painterly Wan restyle, clearly identified direct-engine native audio, and a hosted Cloud execution example using our own generated input. The downloaded Higgsfield sources/results are excluded. Every source archive file is covered by its release manifest; local runtime data, model weights and credentials are excluded by an allowlist.
