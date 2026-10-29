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
```

For semantic mask tracking install the pinned SAM2 package (CUDA extension is not
needed for this workflow):

```sh
SAM2_BUILD_CUDA=0 python -m pip install git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4
```

Model weights stay under their original upstream licenses. The manifest pins every
Hugging Face revision. Do not redistribute the weights with the application.

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
Generation-only setup can use `--base-only` without that adapter. For authenticated
Modal provisioning, set `OPENFRAME_HF_SECRET` to a Modal secret containing `HF_TOKEN`
when deploying. Credentials are never bundled with workflow exports. The cache
can also contain a directly uploaded, verified official checkpoint.

## Editing and exporting

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

Hosted `https://cloud.comfy.org` uses a native diffusion graph plus explicit local
media processing. The app checks exact model filenames and available nodes,
uploads lossless aligned source/generation masks, then downloads generated PNG
frames for the shared plate compositor and audio/video encoder. Both LTX removal
passes remain in one Cloud job. An API key uses the official SDK; an installed
authenticated Comfy CLI can alternatively use OAuth on the hosted service.

Static/optical-flow masks require no local model runtime. Optional SAM2 uses the
configured local ComfyUI connection for a mask-only graph with the exact SAM2.1
small checkpoint and `add_new_mask` initialization. It does not silently replace
painted masks with sparse points. The shared helper applies edit margin,
generation dilation and final feather once after tracking. Provider checking
advertises this method only when the local runtime is detected. This is genuine
Cloud diffusion with local tracking/compositing, not self-contained Cloud SAM2.

The normal workflow export remains the complete stored local replay recipe.
Hybrid bundles also retain the actual Cloud graph, prepared inputs, tracker
provenance when used, and a processing manifest. The Cloud graph alone produces
intermediate frames. Cloud-managed node/model bytes are not attested by the
local pinned requirements; generated PNGs quantize RGB to 8 bits before compositing.
Custom Comfy API endpoints still require a Build with the full node pack/weights.
Modal executes the same graphs on an isolated ComfyUI worker; weights are prepared
on CPU and cached before any GPU render starts. See `deploy/modal_app.py`.

The green placeholder is used only as IC-LoRA conditioning. Before each Laplacian boundary blend, the original plate’s masked hole is filled with generated pixels. This avoids green low-frequency contamination from blending against the conditioning placeholder, which was visible in our protected-plate GPU validation of the upstream wiring.

New object-removal graphs also enable the save node’s optional `match_lighting` flag. It uses normal Poisson/gradient-domain compositing to reconcile generated illumination with the protected plate, including masks touching the frame edge. Outside-mask pixels are then restored exactly before video encoding. Replacement graphs keep their generated colours. The node defaults this flag to false, preserving the semantics of older exported workflows.

Object replacement uses one conditioned pass at the requested resolution. In our comparative real render, retaining the IC-LoRA reference throughout produced better scene and colour continuity than the second-stage candidate, without an extra colour transform. This is a per-effect default, not a claim that one pass is universally superior.

New graphs select `feather_method: smooth-inward`: the signed mask-distance contour is smoothed before an inward opacity ramp. This removes stair steps from rasterized diagonal boundaries without blurring video pixels. A conservative distance bound preserves holes and the original painted exterior exactly before encoding. Raw-decoder comparison isolated the observed replacement shadow artifact to mask compositing, not diffusion. The earlier `inward` mode and default `gaussian` mode remain unchanged for existing exported graphs. `mask_feather: 0` keeps an unfeathered binary mask. CPU mask preparation, compositing and encoding are shared with hosted-provider pre/post processing in the self-contained `custom_nodes/openframe/media.py`; model inference remains in ComfyUI.

Strength is model/task-specific: Wan VACE and LTX inpaint use source-conditioning strength (higher preserves more source structure); LTX restyle uses a denoising amount (higher can regenerate more of the scene). Wan image animation anchors the uploaded opening frame through its control-video/mask branch; its separate reference input gives looser subject guidance and does not promise identity or composition preservation.

`engine/models.py` includes expected SHA256 values and byte sizes from pinned official metadata for all LTX VFX weights. These are expected integrity values, not a claim that every locally cached weight was byte-rehashed during validation. The gated adapter was separately matched against its official checksum.

Hosted verification scope: a 49-frame portrait removal completed after a separately
requested 97-frame case hit the service execution limit. OpenFrame does not
silently shorten jobs; reduce the requested scope explicitly or choose Modal/local.
The final hosted generated-audio check was cancelled during download at the user’s
request, so that end-to-end path remains unverified. Source audio was present in
the tracked result; exact alignment was not established.
