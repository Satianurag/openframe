# OpenFrame workflow pack

These are real ComfyUI API graphs. Every diffusion stage uses native ComfyUI model
nodes. The OpenFrame custom nodes handle video decoding, tracked masks, plate
compositing and export; the Lightricks node pack supplies LTX IC-LoRA guidance.

## Installation

Use a current ComfyUI installation compatible with the pinned revision in
`engine/models.py`. Install `custom_nodes/openframe` into `ComfyUI/custom_nodes` and
install its requirements in ComfyUI's Python environment. For LTX 2.3, install the
pinned Lightricks/ComfyUI-LTXVideo node pack too.

From the OpenFrame project root, download only the profiles you need:

```sh
python -m engine.setup --comfy-dir /path/to/ComfyUI --model ltx-0.9.8
python -m engine.setup --comfy-dir /path/to/ComfyUI --model ltx-2.3
python -m engine.setup --comfy-dir /path/to/ComfyUI --model wan-vace
python -m engine.setup --comfy-dir /path/to/ComfyUI --model sam2
python -m engine.setup --comfy-dir /path/to/ComfyUI --model flux-klein-4b
python -m engine.setup --comfy-dir /path/to/ComfyUI --model wan-animate
python -m engine.setup --comfy-dir /path/to/ComfyUI --model birefnet
python -m engine.setup --comfy-dir /path/to/ComfyUI --model kokoro-82m
```

Reference-to-video uses the official LTX 2.5 Ingredients IC-LoRA. The LTX 2.5
profile includes that adapter, and the OpenFrame pack ships the
`OpenFrameReferenceSheet` node that tiles one to nine ordered stills into the
single sheet injected on every frame; no extra dependency or node pack is
required. The gated LoRA repository must be accepted before provisioning.

For semantic mask tracking install the pinned SAM2 package (CUDA extension is not
needed for this workflow):

```sh
SAM2_BUILD_CUDA=0 python -m pip install git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4
```

Model weights stay under their original upstream licenses. The manifest pins every
Hugging Face revision. Do not redistribute the weights with the application.

## Separate image, speech and character workflows

FLUX.2 Klein 4B generates PNG images rather than video frames. Its native
`ReferenceLatent` chain accepts up to four images in order (the source first for
editing), with batches of one to four variants. References keep their own aspect
ratios; the output canvas has its requested dimensions. This is reference-guided
generation/editing, not identity training or a guarantee of exact face, garment,
product or typography reproduction. The selected 4B model and text encoder use
Apache-2.0 terms; the FLUX.2 autoencoder also uses Apache-2.0, distinct from the
non-commercial diffusion models in its source repository. The three pinned files
total 12,451,820,124 bytes (11.60 GiB), before any existing-cache reuse.

Speak uses Wan 2.2's purpose-trained S2V model with a portrait and an uploaded
recording. `LoadAudio` and `TrimAudioDuration` select the recording; wav2vec2
features and the portrait feed native `WanSoundImageToVideo` conditioning.
The full BF16 model uses the official 20-step / CFG 6 path, without a partially
matching acceleration adapter. Its native audio alignment requires 16 fps and
73–161 frames (`4n+1`; default 77). The original selected waveform is saved with
the generated video. `audio_start` selects the recording offset; its remaining
duration must cover `frames / fps`. The initial LTX 2.3 configuration preserved
audio but failed visible mouth-motion review, so it is not offered for new Speak
jobs; historical executed graphs remain reproducible. This is not a general
claim that LTX cannot perform audio-conditioned generation.
For a written script, first generate a recording with the separate Kokoro
speech operation and then select that audio asset in Speak. The pinned Apache-2.0
Wan S2V and audio-encoder files add 33,222,641,100 bytes (30.94 GiB), reusing the
existing Wan UMT5/VAE files. Prepare them on CPU with `--model wan-s2v`.

Kokoro 82M runs on CPU inside ComfyUI and saves 24 kHz PCM WAV.
This build exposes four built-in English voices (`af_heart`, `am_michael`,
`bf_emma`, `bm_george`), speed 0.5–2, and scripts up to 2,000 characters. Audio
longer than 180 seconds is rejected, never silently truncated. This is synthesis
with public voices, not voice cloning. The pinned config, model and voice files
total 329,308,287 bytes (about 314 MiB), under Apache-2.0.

Install the CPU dependencies in ComfyUI's Python before using it:

```sh
python -m pip install 'kokoro==0.9.4' 'misaki[en]==0.9.4' 'spacy>=3.8,<3.9' https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

Install `espeak-ng` through the operating system package manager. The node checks
these dependencies and the local model/voice files before generation; it does
not fetch missing assets while executing. Use the local setup command above to provision only the selected profile into the user's own ComfyUI installation.

Background Remover uses native ComfyUI BiRefNet inference and writes an RGBA PNG
with soft alpha at the source image's canvas size. It is independent of SAM2's
binary tracking mask. The pinned MIT-licensed checkpoint is 444,473,596 bytes
(about 424 MiB). Alpha edges and translucent/fine foreground detail still need
visual inspection; segmentation is not guaranteed perfect for every material.

Wan Animate uses its own 14B model, CLIP vision reference, and actual ViTPose
body/hand landmarks plus cropped facial-motion frames. Motion transfer omits
background conditioning. Character replacement additionally uses the painted,
tracked mask and blacked-out source background in `WanAnimateToVideo`, then the
same protected-plate compositor. This targets one prominent performer; multiple
people, occlusion and mismatched reference body proportions need care. It does
not transfer arbitrary objects through human pose estimation.

Install `kijai/ComfyUI-WanAnimatePreprocess` at the revision in `engine/models.py`
and install `onnxruntime>=1.20,<2` and `matplotlib>=3.9,<4` in ComfyUI's Python.
OpenFrame uses CPU ONNX preprocessing, with separately provisioned detection
weights; there are no runtime downloads hidden in the graph. The checkpoint is
the FP8 conversion used by ComfyUI's official template. The new Animate,
vision, acceleration/relight adapters and pose files total about 24.45 GB
(22.77 GiB), while UMT5, Wan VAE and SAM2 are reused when already cached.
Upstream Wan/ViTPose licences and the detector's own component terms apply;
do not infer every auxiliary model's licence from the wrapper repository.

Primary implementations:
- [Native Klein editing](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_image_edit_4b_distilled.json)
- [Native Wan S2V graph](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/video_wan2_2_14B_s2v.json)
- [Native Wan Animate](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_animate.json)
- [Wan pose and face preprocessing](https://github.com/kijai/ComfyUI-WanAnimatePreprocess/tree/0e0b6a2a555625acf4d4aefb780e27d06937132f)
- [Native BiRefNet graph](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_birefnet_remove_background.json)
- [Kokoro implementation](https://github.com/hexgrad/kokoro)
- [Pinned Kokoro model and public voices](https://huggingface.co/hexgrad/Kokoro-82M/tree/f3ff3571791e39611d31c381e3a41a3af07b4987)

These new routes require separate end-to-end validation. Existing video/VFX
evidence does not establish their image fidelity, speech synchronization or
character-motion quality. Hosted Cloud compatibility is not inferred from local
node availability; no new Cloud tests are part of this expansion.

## Optional video shot planning

The separate CPU planner uses the official Apache-2.0
[Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/a09a35458c702b33eeacc393d103063234e8bc28)
model. Its pinned weight shards total 15.23 GB (14.19 GiB), plus tokenizer files.
The optional local text planner requires an explicitly provisioned model directory and compatible Torch/Transformers runtime; configure `OPENFRAME_PLANNER_MODEL_DIR`. The public application does not provision or require a rented GPU worker.
The legacy `qwen-planner` 1.5B cache is retained, but it failed the tested brief's
starting-state/continuity requirements and is no longer the app default.

Planning accepts a creative brief, style, seed, 1–4 episodes, and 15–300 seconds
per episode in five-second increments. It generates distinct chronological
shots in batches of up to six, carrying previous-shot and episode summaries
forward. Each episode has up to 30 explicit shots. The model writes concrete
visual descriptions, camera instructions and optional narration; it cannot
execute tools or submit renders. The proposal remains editable before the
application creates any ComfyUI jobs.

The requested editorial duration is allocated exactly across those shots,
each at most ten seconds. Model frame alignment and the actual assembled
duration are separate values shown before execution. No clip is silently
stretched or looped to fill a long request. Invalid JSON, missing/repeated shots
or exceeded limits cause an explicit failure after at most two attempts per
batch; no template plan is substituted. Its deadline is five minutes plus three
minutes per proposed shot, bounded to 10 minutes–6 hours, exposed in status and
saved request/result metadata. Execution and transport enforce this budget,
with one minute of transport allowance. This is a
deadline rather than a latency estimate. The actual two-shot API proof took
219 seconds; the maximum 120-shot request has not been benchmarked. Narrative
quality still requires review even when JSON is valid.

Local planning is optional: provision `qwen-planner-7b` with `engine.setup`,
install Torch/Transformers in the backend environment, and set
`OPENFRAME_PLANNER_MODEL_DIR` to `ComfyUI/models/planning/qwen2.5-7b-instruct`.
Capability checks never download missing files. Planning is distinct from the
actual image/video/audio workflows, which continue to execute inside ComfyUI.

## Inputs and parameters

Place `source.mp4` and a painted `mask.png` in ComfyUI/input for VFX. White means
change, black means preserve. Image animation uses `source.png`. Additional
reference images are supported by Wan VACE for generation, inpainting and restyling;
image-to-video already uses its source as the reference. The mask is drawn on the source's
first selected frame. Source images/masks are centre-cropped to the requested
output aspect ratio consistently.

The source clip is resampled to the requested FPS and trimmed to the requested
frame count. Short sources are rejected; frames are not silently repeated.
LTX frame counts are 8n+1, Wan counts are 4n+1. `trim_start` is in seconds.
Audio is trimmed consistently and remuxed when Preserve audio is enabled. If the
source has no audio, requested generated audio is used instead. LTX 2.3 can create
new audio; LTX Fast and Wan VACE cannot.

`mask_tracking_method` supports SAM2.1, optical flow or a static mask. A supplied
mask video is used directly. `mask_edit_margin` expands the editable support before feathering (12 output pixels by default for tracked inpainting, zero for static masks); it prevents a tight tracked silhouette from restoring the original object edge. `mask_dilation` then adds extra generation context. The final mask is feathered inward, so decoded source pixels outside the expanded edit support are preserved before lossy video encoding. Reduce the edit margin near foreground occluders, and inspect the exported mask. The native node defaults its optional `edit_margin` to zero for existing graphs. `export_mask` includes the actual blend mask video as a separate output.

Distilled LTX schedules default to eight steps. Other step counts interpolate the
schedule and are experimental. LTX 2.3 uses the official dev+distillation adapter
combination and in/outpainting IC-LoRA for masks. Its object-removal path follows the
[published two-stage graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.3/LTX-2.3_ICLoRA_Inpaint_Two_Stage_Distilled.json):
half-size generation, Laplacian boundary blending, Lanczos enlargement and VAE
re-encoding, two refinement steps, then another Laplacian blend. The requested
step count controls the first pass; refinement always adds two steps. For quality
work, use an output whose shorter side is at least 576 pixels. Smaller outputs
serve as drafts. Internal edge padding keeps both stages on the latent grid and
is cropped away before saving; requested dimensions and aspect are unchanged.
OpenFrame optionally composites the original plate outside the selected mask
after blending, giving stronger preservation than an unconstrained whole-frame edit.

The LTX inpainting adapter requires access to its official Hugging Face repository.
Generation-only setup can use `--base-only` without that adapter. Authenticate
with Hugging Face on the ComfyUI host when provisioning gated files. Credentials
are never bundled with workflow exports. The cache can also contain a directly
uploaded, verified official checkpoint.

## Editing and exporting

FLUX3 native image generation/editing is implemented as separate BF16 and INT8
distilled profiles, retaining the older Klein 4B workflows. See
[FLUX3 components, controls, preservation and license](../docs/FLUX3.md).
These newly added profiles await runtime validation; they are not covered by
earlier Klein or video execution evidence.

The app exports the exact API graph used for a job. With the nodes installed, a
current ComfyUI frontend can import API-format graphs. To create explicit editable
canvas-format files from the installed node schemas:

```sh
python -m engine.export --output workflows --comfy-url http://127.0.0.1:8188
```

The exporter preserves connections and widget ordering from `/object_info`,
rather than inventing a UI schema. Exported `.ui.json` files can be opened in
ComfyUI. API graphs can be submitted to `/prompt` or Comfy API v2.

## Cloud

Hosted `https://cloud.comfy.org` is contacted directly, using an API key through
the official SDK or an authenticated installed Comfy CLI. No rented-GPU relay is
required. The LTX2.5 adapter currently supports masked inpainting only: host CPU
prepares the exact source interval, masks, audio and optional edited starting
frame; native hosted nodes run the recorded IC-LoRA sampling, final plate
composite and video/audio encoding. Optional raw decoded video is also returned.
Removal additionally applies its recorded seamless-clone lighting correction
locally; explicit replacement plate fitting reuses the attributed PaintAPlate
helper before one alpha composite. Standard/High bitrate targets also use the
shared local encoder because native SaveVideo exposes CRF only. These cases
retain the native CRF17 Cloud composite as a clearly named preview.
Schema, preparation and transport contracts are checked; a live 2.5 Cloud render
has not been run. Other 2.5 tasks are rejected rather than substituted.

The earlier LTX2.3/Fast/Wan hosted routes retain their existing hybrid behavior:
Cloud returns generated PNG frames, and the host composites/encodes the result.
Both LTX2.3 removal passes stay in one Cloud job.

Static/optical-flow masks require no local model runtime. Optional SAM2 uses the
configured local ComfyUI connection for a mask-only graph with the exact SAM2.1
small checkpoint and `add_new_mask` initialization. It does not silently replace
painted masks with sparse points. The shared helper applies edit margin,
generation dilation and final feather once after tracking. Provider checking
advertises this method only when the local runtime is detected. This is genuine
Cloud diffusion with local tracking/compositing, not self-contained Cloud SAM2.

The normal workflow export remains the complete stored local replay recipe.
Hybrid bundles also retain the actual Cloud graph, prepared inputs, tracker
provenance when used, and a processing manifest. LTX2.5 native exports return
composited video, but do not perform the optional host lighting correction.
Older hybrid exports return intermediate frames. Cloud-managed node/model bytes
are not attested by local pinned requirements. Prepared composite masks are 8-bit
(maximum rounding error 0.5/255, exterior zeros unchanged); the optional host
lighting correction uses the original floating-point mask and 8-bit PNG inputs.
Custom Comfy API endpoints still require a Build with the full node pack/weights.
Private GPU test infrastructure is excluded from the public source/package.
Historical test receipts retain their original provider; they are not local or Cloud verification.

The green placeholder is used only as IC-LoRA conditioning. Before each Laplacian boundary blend, the original plate’s masked hole is filled with generated pixels. This avoids green low-frequency contamination from blending against the conditioning placeholder, which was visible in our protected-plate GPU validation of the upstream wiring.

New object-removal graphs also enable the save node’s optional `match_lighting` flag. It uses normal Poisson/gradient-domain compositing to reconcile generated illumination with the protected plate, including masks touching the frame edge. Outside-mask pixels are then restored exactly before video encoding. Replacement graphs keep their generated colours. The node defaults this flag to false, preserving the semantics of older exported workflows.

Object replacement uses one conditioned pass at the requested resolution. In our comparative real render, retaining the IC-LoRA reference throughout produced better scene and colour continuity than the second-stage candidate, without an extra colour transform. This is a per-effect default, not a claim that one pass is universally superior.

New graphs select `feather_method: smooth-inward`: the signed mask-distance contour is smoothed before an inward opacity ramp. This removes stair steps from rasterized diagonal boundaries without blurring video pixels. A conservative distance bound preserves holes and the original painted exterior exactly before encoding. Raw-decoder comparison isolated the observed replacement shadow artifact to mask compositing, not diffusion. The earlier `inward` mode and default `gaussian` mode remain unchanged for existing exported graphs. `mask_feather: 0` keeps an unfeathered binary mask. CPU mask preparation, compositing and encoding are shared with hosted-provider pre/post processing in the self-contained `custom_nodes/openframe/media.py`; model inference remains in ComfyUI.

Strength is model/task-specific: Wan VACE and LTX inpaint use source-conditioning strength (higher preserves more source structure); LTX restyle uses a denoising amount (higher can regenerate more of the scene). Wan image animation anchors the uploaded opening frame through its control-video/mask branch; its separate reference input gives looser subject guidance and does not promise identity or composition preservation.

`engine/models.py` includes expected SHA256 values and byte sizes from pinned official metadata for all LTX VFX weights. These are expected integrity values, not a claim that every locally cached weight was byte-rehashed during validation. The gated adapter was separately matched against its official checksum.

Hosted verification scope: a 49-frame portrait removal completed after a separately
requested 97-frame case hit the service execution limit. OpenFrame does not
silently shorten jobs; reduce the requested scope explicitly or choose local ComfyUI.
The final hosted generated-audio check was cancelled during download at the user’s
request, so that end-to-end path remains unverified. Source audio was present in
the tracked result; exact alignment was not established.
