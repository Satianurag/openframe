# OpenFrame API

OpenFrame runs a single-user FastAPI service at `http://127.0.0.1:8000`. Interactive endpoint documentation is at `/docs`, and the OpenAPI schema is `/openapi.json`. Run **one Uvicorn worker**: the application owns one inference queue per process. A local SQLite database persists assets, jobs, settings and presets across restarts.

The frontend calls the same API described here. Local ComfyUI and direct Comfy Cloud use the same job-request envelope; their available tasks and processing boundaries differ. An accepted job means it entered the queue, not that a GPU render succeeded.

## Discover supported capabilities

```bash
curl http://127.0.0.1:8000/api/catalog
```

The response contains `models`, `effects`, `providers` and `limits`. Use these records to populate selectors. Each effect identifies its `task`, supported `model_ids` and required source/mask media. Effect cards are workflow/prompt presets, not claims of separately trained effect models.

Model records include dimension bounds/multiples, frame bounds/multiples, default steps/guidance/FPS, and supported capabilities. The API validates these before queueing. Provider availability is initially `null` (not checked); run the explicit connection check to obtain a live result.

## Upload and inspect media

```bash
curl -F 'file=@source.mp4' http://127.0.0.1:8000/api/assets
curl -F 'file=@mask.png' http://127.0.0.1:8000/api/assets
```

Use the returned immutable `id` values in a render request. Asset records include `kind`, `name`, `url`, `thumbnail_url`, dimensions, byte size, SHA-256 and, for video, duration/FPS/audio presence. Internal filesystem paths are not returned. Identical bytes reuse an existing asset when its stored file remains available.

- `GET /api/assets?limit=100&offset=0`: newest-first library, with `items`, `total`, `offset`.
- `GET /api/assets/{id}`: metadata.
- `GET /api/assets/{id}/file`: full media; HTTP range requests are supported by the file response.
- `GET /api/assets/{id}/file?download=true`: attachment download.
- `GET /api/assets/{id}/thumbnail`: cached JPEG preview if one exists.
- `GET /api/assets/{id}/frame?time=1.25`: PNG video frame; images return a PNG with orientation applied. No new frame files are persisted for each seek.
- `DELETE /api/assets/{id}`: delete an unreferenced asset. A referenced asset returns `409` until its referencing renders are deleted.

Uploads are bounded by `OPENFRAME_MAX_UPLOAD_MB` (default 512 MiB). Ingestion validates media content using Pillow or ffprobe, not just the filename. FFmpeg/ffprobe are required for video ingestion and frame extraction. Supported image ingestion formats are PNG, JPEG, WebP, GIF and TIFF; the frame endpoint provides a browser-friendly PNG. Mask images should use white for editable regions and black for preserved regions.

## Configure compute

`GET /api/settings` returns public settings and `has_comfy_api_key` / `has_comfy_cloud_api_key` flags. It never returns the secret values. `comfy_cloud_auth` contains only `mode` (`api-key`, `cli-oauth` or `missing`), `cli_installed` and `cli_signed_in`; it does not expose a CLI session or token.

```bash
curl -X PATCH http://127.0.0.1:8000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"default_provider":"local","comfy_url":"http://127.0.0.1:8188"}'
curl -X POST http://127.0.0.1:8000/api/providers/local/check
```

Settings fields:

| Field | Default / purpose |
| --- | --- |
| `default_provider` | `local`; normal choices `local`, `comfy-cloud` |
| `comfy_url` | `http://127.0.0.1:8188` |
| `comfy_api_key` | Optional bearer credential for protected self-hosted Comfy |
| `comfy_cloud_url` | `https://cloud.comfy.org`, or a compatible Comfy API deployment |
| `comfy_cloud_api_key` | Credential for the selected Comfy API endpoint |
| `comfy_cli_path` | Optional installed `comfy` executable; empty searches PATH and existing uv tool installs |

Secrets supplied in PATCH remain server-side. Omitting a secret leaves it unchanged; sending an empty string clears its saved value. URLs must be HTTP(S) and must not contain embedded credentials. Environment defaults use the same names prefixed with `OPENFRAME_` in uppercase; saved settings override those defaults. `.env.example` lists the fields.

A connection check is read-only and returns `available`, `detail`, `checked_at`, and provider-specific diagnostics. It does not submit a render. `enabled_providers` and task-scoped `provider_tasks` are the availability contract. Private testing is disabled in the public configuration; historical private-provider records retain their original provenance.

For hosted `https://cloud.comfy.org`, an API key uses the official SDK. Without one, OpenFrame can reuse an existing server-side `comfy-cli` 1.23+ OAuth login (`comfy cloud login`). No application login or billing purchase occurs. A configured key takes precedence; OAuth is not silently used after a rejected key. The hosted connection check reports `auth_mode`, available exact model profiles and `supported_tracking_methods`; the CLI route also reports remaining free runs/credit balance. Zero balance and no free allowance is unavailable. A model selector does not guarantee that its exact weights are installed on every provider; submission checks exact filenames and rejects missing profiles without substitution.

Hosted Cloud runs native model/diffusion nodes, including both LTX removal passes in one graph/job. LTX2.5 inpainting additionally uses native final composite/video nodes; its explicit local finishing boundary is described below. For the older LTX2.3/Fast/Wan routes, the app prepares aligned source/mask video and performs final plate compositing/audio encoding using the same CPU helpers as the custom nodes. Static masks, optical flow and supplied mask videos need no local model runtime. SAM2 uses an optional mask-only graph on the configured `comfy_url`/`comfy_api_key` connection; that instance must report the current OpenFrame nodes, SAM2 package and exact `sam2.1_hiera_small.pt` checkpoint. It initializes from the actual painted mask with `add_new_mask`, without approximating it with points. Cloud connection checks include `local_sam2` diagnostics and advertise `sam2` only when that local runtime is detected. Unavailable or failed local tracking stops before a Cloud GPU submission. Edit margin/dilation/feather apply once after tracking; the tracker graph and raw tracked-mask video remain in the full project bundle. This route is Cloud diffusion plus local SAM2, not self-contained Cloud tracking. Local media buffers are limited to an estimated 2 GiB per clip. Prepared uploads use lossless RGB video. Paths requiring local finishing download lossless 8-bit PNG frames, so those generated pixels are quantized before the local composite. Custom SDK endpoints continue to require the full OpenFrame node pack and weights.

Observed hosted limits are workload-dependent: the 97-frame, 576×1024 two-stage removal verification was stopped by the service with `Job execution time exceeded maximum limit`; a separately requested 49-frame version succeeded. This is evidence for those cases, not a published frame cap. A failed request is never silently shortened or retried. Execution-limit errors retain the provider message and advise fewer frames/lower resolution or local ComfyUI execution. Hosted generated-audio transport is implemented, but its final end-to-end check was cancelled at the user’s request during output download; it is not a verified audio pass. Source audio was present in the successful tracked result, but exact synchronization was not established.

For a hosted Cloud job, the normal workflow export is its stored complete local replay recipe. The bundle separately records the actual native Cloud execution graph and local-processing manifest; older Cloud graphs alone produce intermediate frames. The new 2.5 graph returns native composite video and optional raw video, with separately declared app finishing when needed. Full-media bundles include originals and prepared inputs. New 2.5 bundles include native API and UI canvases; these are the hosted stage, not a single canvas for app preprocessing/finishing. See `CLOUD-PROCESSING.json` and the bundle README before re-executing only the Cloud stage.

## Submit a render

```json
{
  "model_id": "ltx-2.3",
  "effect_id": "remove-object",
  "provider": "local",
  "prompt": "A clean uninterrupted background, consistent lighting and camera movement.",
  "negative_prompt": "",
  "seed": 42,
  "width": 768,
  "height": 512,
  "frames": 97,
  "fps": 24,
  "steps": 8,
  "guidance": 1,
  "source_asset_id": "<32-character uploaded video ID>",
  "mask_asset_id": "<32-character uploaded mask ID>",
  "strength": 0.75,
  "trim_start": 0,
  "mask_tracking": true,
  "mask_tracking_method": "sam2",
  "export_mask": true,
  "mask_dilation": 8,
  "mask_feather": 8,
  "preserve_outside_mask": true,
  "preserve_audio": true
}
```

Save the JSON as `request.json`, replace both asset IDs, then:

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H 'Content-Type: application/json' --data-binary @request.json
```

Important semantics:

- `seed: -1` chooses a 32-bit random seed once, before queueing, and records the chosen value in the job. Explicit seeds may range from 0 to 2^53−1 so browser JSON round-trips remain exact. A retry reuses that recorded recipe/seed.
- LTX dimensions must be multiples of 32; Wan VACE dimensions must be multiples of 16. Read current min/max values from the catalogue.
- LTX frames must equal `8n + 1`; Wan frames must equal `4n + 1`, within the selected profile's maximum. The API rejects invalid counts rather than silently rounding them.
- `frames / fps` is the requested output duration. Source video starts at `trim_start`, is resampled to the requested FPS and is trimmed to that duration. The request is rejected if not enough source remains, allowing only a 1ms metadata rounding tolerance. Source frames are never silently repeated to fill a longer request.
- A shorter selected duration produces a job `warnings` entry describing the used interval. Display this in clients.
- `mask_tracking_method` selects `sam2` (default), `flow` or `static`. SAM2 propagates the painted initial mask using SAM2.1; flow uses optical flow. Neither guarantees perfect tracking through every occlusion. `mask_tracking:false` forces `static` for compatibility. Inspect the exported mask.
- `export_mask:true` requests a mask-video output for VFX jobs. Job outputs and generated asset responses carry `role` (`result` or `mask`) so clients can choose the rendered result for comparison and offer the matte separately. Legacy asset roles are resolved from the recorded source job, never guessed from filenames.
- Sampling steps accept 1–50. Omitted frame/FPS/step/guidance values use the selected model’s catalogue defaults.
- `strength` accepts 0.05–1, `mask_dilation` 0–64, and `mask_feather` 0–32. Strength semantics depend on the model/task: Wan uses source-conditioning strength and LTX inpainting uses guide strength (higher values increase source guidance); LTX restyling uses the denoising schedule (higher values permit more transformation). Existing recipe values are not silently inverted.
- `mask_edit_margin` accepts 0–64 or null/omitted. Normalization chooses 12 pixels for SAM2/flow inpainting and 0 otherwise. It explicitly expands the editable support before feathering, so tracked semantic silhouettes retain enough room to remove an object's boundary/shadow. This is distinct from `mask_dilation`, which adds generation context outside that editable support. The resolved value is recorded in the job; explicit 0 preserves the supplied support.
- New masked-edit graphs use `smooth-inward`: the mask distance contour is smoothed, then feathered inward to zero; image pixels themselves are never blurred. `mask_dilation` expands generation context; it does not expand the final preserved/exterior boundary. Paint enough margin around the object and its shadow for feathering. The graph's optional `feather_method` remains Gaussian when omitted by an older stored graph; explicit older `inward` graphs retain their original distance ramp. This is an execution-node compatibility field, not a new request parameter.
- LTX 2.3 `remove-object` uses a conditioned half-resolution pass plus full-resolution refinement and removal-specific lighting matching. `replace-object` uses a full-resolution single conditioned pass with lighting matching disabled to retain the new object's colours. These choices are recorded in the generated graph rather than exposed as unsupported interchangeable pipeline options.
- Wan `image-to-video` uses known opening-frame control conditioning. Optional `reference_asset_id` uses separate reference guidance on supported tasks and does not promise exact identity preservation.
- `preserve_audio` preserves source audio where the workflow supports it; it does not invent an audio track for silent footage.
- A provider must be configured. An explicit connection check is useful, but availability can still change between checking and generation.
- No successful synthetic fallback exists. Engine errors fail the job.

## Track, cancel and reuse jobs

### Optional Katana EditVid requests

`flux-klein-editvid` supports Katana `restyle` on configured Local ComfyUI only. Its released Apache code uses **FLUX Non-Commercial License v2.1** 9B weights; there is no hosted Cloud route or automatic substitute. See [the pinned runtime/dependency guide](../custom_nodes/openframe/EDITVID-RUNTIME.md). Supply `restyle_source_prompt` describing the original scene separately from the desired edit `prompt`. The released four-step recipe is fixed; source/silent audio, explicit source interval and 9–241 frames at24fps are supported within the catalogue's source/output pixel bounds. Extra references, masks, generated audio and prompt enhancement are rejected. The native full241-frame private evaluation preserves source choreography with visible fast-motion trails/fine-detail changes; it does not establish an independent PC installation or universal identity fidelity.

### FLUX3 image requests

`flux3-klein` and `flux3-klein-int8` support `create-image`/`edit-image` on a
configured Local ComfyUI host with the matching nodes and pinned model files.
They are not advertised as hosted Comfy Cloud profiles. Read
[the exact component/control contract](FLUX3.md) and
[the scoped runtime/quality evidence](DESKTOP-VALIDATION.md); a recorded private
GPU run does not establish installation on an independent PC.
`reference_asset_ids` is bounded by the selected model: ten total images for
FLUX3 including the editing source, versus four for the older Klein profile.
`image_prompt_mode` is `expand` (requires the native prompt-upsample checkpoint)
or `caption` (at least 80 characters). `image_layout` accepts up to 32 positive-area
normalized TLBR boxes with unique IDs; `image_reference_megapixels` accepts
0.25–4, bounded to 16 megapixels across all references. CFG is fixed to 1 and
negative prompts are unsupported by these distilled profiles.

`image_preservation` selects `none`, `outside-mask` or `inside-mask`. Preservation
requires `edit-image`, a source and a grayscale image mask at exactly the source
dimensions. White means editable for `outside-mask`, protected for `inside-mask`.
The API derives a 16-aligned generation canvas and the node crops back before
copying protected source pixels into the PNG. This is explicit compositing, not
a reference-fidelity claim. `metadata.image_prompt` records the original,
expanded and final model prompt; `image_processing` records preservation and
output dimensions; `image_pipeline` records pinned component configuration.

### Source-specific video controls

New video models expose their own limits in the catalogue. `motion_prompt` is
bounded to 3000 characters; `pose_strength`, `reference_strength` and
`audio_conditioning_strength` accept 0–2. Pose start/end percentages accept 0–1
with start no later than end. `enhance_prompt` and `video_refinement` apply only
to compatible profiles. Do not infer compatibility from a field's presence.

`video-extend` uses `context_frames` (1–129, `8n+1`, default17) from `trim_start`;
the requested `frames` is the complete context-plus-continuation result and must
exceed that context. Source-duration checks use the context, not the generated
tail. `outpaint_scale` accepts 0.1–1 and outpaint anchors accept 0–1. Pixel-2x
upscaling and alpha extraction use trusted source dimensions, pad inference to
32 and crop back to the exact target; they reject conflicting output dimensions.
`upscale_mode: "tiled-refine"` retains its explicit requested canvas instead.

`trim-video` and `video-reframe` retain actual source FPS. An explicit conflicting
FPS is rejected; omitted FPS inherits the source. Reframing uses `reframe_fit`
(`crop`/`pad`) and `anchor_x`/`anchor_y` (0–1). `encoding_quality` accepts `legacy`,
`standard` and `high`; existing recipes retain legacy encoding unless an explicit
new operation normalizes its own supported quality. These are media operations,
not an implementation of a similarly named proprietary outfit effect.

Job records contain `id`, `status`, `progress` (0–1), `stage`, timestamps, the resolved `request`, `warnings`, `outputs`, `error` and `favorite`. Status values are `queued`, `running`, `succeeded`, `failed`, `cancelled`.

| Request | Behaviour |
| --- | --- |
| `GET /api/jobs?limit=100&offset=0` | Newest-first job list plus total/offset |
| `GET /api/jobs/{id}` | Current state; poll around every two seconds while active |
| `POST /api/jobs/{id}/cancel` | Cancel queued jobs immediately; request cooperative cancellation of running inference |
| `POST /api/jobs/{id}/retry` | Create a new job from a terminal job's recorded request |
| `PATCH /api/jobs/{id}` with `{"favorite":true}` | Save favorite state |
| `DELETE /api/jobs/{id}` | Delete a terminal job record; retain its media in the library |

`outputs` hold full media asset records, not inference previews. Download each output through its `url`. Success requires the expected media kind and full requested image batch; mask-only, wrong-kind, or partial-batch responses fail explicitly.

Cancellation is not instant GPU termination. The job remains running with a cancelling stage until the engine observes the request. Retrying/deleting an active job returns `409`. On application restart, a previously running job becomes failed with an explicit interruption message; it is **not automatically resubmitted**, because remote inference may still be running. Check the provider before retrying an interrupted render. Queued jobs remain queued and resume normally.

The local queue processes one render at a time. Progress persistence is throttled to at most once per second; terminal state changes are written immediately. This avoids repeatedly rewriting unchanged per-step state.

## Export and reproducibility

- `POST /api/workflows/export` with a render request downloads an API-format ComfyUI graph.
- `GET /api/jobs/{id}/workflow` downloads the executed API graph if available, otherwise a graph built from the recorded request. Add `?format=ui` for the editable canvas graph captured from the execution provider; it returns `409` when unavailable.
- `GET /api/jobs/{id}/bundle` streams a recipe ZIP containing the portable API graph, manifest, pinned model/runtime and selected tracker requirements, the OpenFrame custom node pack and setup instructions.
- Model `expected_sha256` and `size_bytes`, when provided, are upstream expectations for the pinned file revision. Bundle creation does not read or verify installed model-weight bytes. Input-media SHA-256 values describe the actual uploaded files.
- `GET /api/jobs/{id}/bundle?include_media=true` streams a full project ZIP including original source, mask and reference media. Copy the included `input/` contents into ComfyUI/input; the relocated graph already references those names.
- A job with a stored execution graph uses that graph for both portable and original exports; the portable graph changes only input filenames. Later workflow-template changes do not replace its nodes or settings. Only a job without a stored graph falls back to the current template and recorded request. The original executed graph is retained separately. When the execution provider supplies a canvas-format graph, `workflow_ui.json` is also included.
- Older graphs retain their recorded pipeline and optional-node defaults (`feather_method:gaussian`, `match_lighting:false` when absent). Retrying a request builds a new graph from the current template; exporting an existing execution preserves the old graph.

The default recipe ZIP remains small and excludes media. The full project option includes original input media in bounded streaming chunks without creating a duplicate archive on the server disk. Both variants record settings, seed and source hashes. Model weights and generated output videos are not embedded; download outputs separately. Install the matching models/nodes before running the graph. No provider secrets are exported.

## Saved presets

`POST /api/presets` accepts `{"name":"My removal recipe","request":{...}}`. Presets retain generation settings but clear source/mask/reference asset IDs so a recipe can be applied to new footage. They validate supported model/effect and parameter combinations. `GET /api/presets` lists saved recipes; `DELETE /api/presets/{id}` removes one.

## Errors and local operation

API errors use FastAPI's `detail` field. `422` covers incompatible requests/invalid media, `404` missing records/files, `409` state/reference conflicts and `413` oversized uploads. Provider runtime failures appear on the job rather than being mistaken for an empty successful result.

The application is a local single-user studio, not an authenticated multi-tenant service. Startup scripts bind to `127.0.0.1`. Browser mutation requests from unapproved origins are refused. The data directory and SQLite database remain local; API keys are excluded from public settings and error messages. Use `OPENFRAME_ALLOWED_ORIGINS` for an explicitly configured alternate frontend origin.

Separate app documents, revision-safe saves, scoped history and additive image/audio inputs are specified in [APPS-API.md](APPS-API.md). Existing VFX routes remain available; app provenance does not alter an executed render request.
## Additional media capabilities

These contracts describe implemented paths. Capability detection and graph validation are not quality acceptance; [DESKTOP-VALIDATION.md](DESKTOP-VALIDATION.md) separates actual runtime, visual review, unresolved limitations and unverified routes.

`expand-image` / `image-outpaint` uses either distilled FLUX3 profile and an uploaded source image. The target is256–4096pixels per side on the16pixel grid; it must contain the complete original and enlarge at least one axis. `outpaint_anchor_x/y` place the original without resampling. No external mask is accepted. Current graphs anchor the padded source during denoising with an outside-region noise mask, then restore original RGB/alpha exactly. This preserves source pixels, not generated geometry or lighting continuity. `metadata.image_canvas` records exact placement and padding; stored older graphs retain their recorded behavior.

The LTX2.5 `transition-video` profile uses `source_asset_id` and `end_asset_id`, each an image or a video no longer than5seconds. Native first/last-frame guides condition121 or241generatedframes at24fps. Start-video selection uses its actual last decoded frame; end-video selection uses its first. Optional `reference_asset_id` accepts one midpoint still image for this task; it is conditioned in both native sampling passes and recorded in `metadata.transition_midpoint_guide`. It guides generation rather than forcing exact midpoint pixels. Other tasks accept only their explicitly declared reference roles/capabilities; a midpoint image is not interchangeable with an edited full starting frame. `transition_include_inputs` optionally fits/resamples actual input clips and concatenates them with the generated bridge. Images are not held or looped as extra footage. `metadata.transition_inputs` and `metadata.transition` preserve endpoint and assembly provenance; the actual assembled duration is measured. This is distinct from a sequence's deterministic crossfade. Read the selected profile's own bounds/fit policy; the separate matched first/last-frame LTX2.3 profile retains its own native recipe.

`video-depth` supports `video-depth-small` (Apache default) and explicit `vigeo-1.1` (noncommercial Research weights). It accepts a video interval of2–300frames, retains source FPS/aspect and uses an even canvas within1280long-side/921600pixels. Omitted dimensions fit within768long-side without upscaling. No prompt, mask or reference is consumed. The normal result is a grayscale viewing MP4; auxiliary role `depth` is a lossless FFV1 gray16 MKV. Preserve `metadata.depth`: codes1–65535 map through one clip-global minimum/maximum;0is invalid. These are relative predictions, not metres. See [selection evidence](research/video-depth-benchmarks.md).

`layer_count` is a bounded2–8integer (default4) for the image-layers operation. Its model/effect capability metadata determines image input, provider and output support; unsupported combinations fail instead of substituting image generation.

Depth preview fields are `depth_colormap` (`grayscale`, `turbo`, `inferno`, `magma`, `viridis`) and `depth_side_by_side` (default false). They alter only the viewing MP4; lossless numeric depth remains unchanged. The current whole-clip wrapper retains the documented300-frame bound rather than claiming the reference site's1800-frame capacity.

LTX extension accepts `extension_direction: sequel|prequel`. HDR accepts `hdr_output_format: hevc10|prores10|exr16` (default hevc10). EXR is an explicit generated-only ZIP asset (`kind=archive`, `role=result`) with a separate SDR preview. Its manifest records scene-linear ACEScg half-float frames; the archive has no audio. Bounds:241frames,1920long-side/1088short-side and4GiB estimated raw RGB16 data. Archive registration checks members, EXR signatures and manifest without ffprobe; ZIP source uploads are rejected. Recipe bundles record output assets but do not duplicate generated archives.

Prompted `semantic-matte` uses the SAM3.1/ViTMatte profile on a configured Linux/WSL2 CUDA ComfyUI host, source video and a foreground description. Install its isolated runtime using the bundled [RECAST-RUNTIME.md](../custom_nodes/openframe/RECAST-RUNTIME.md); the connection check reports prerequisites, not successful inference. The model's access/license conditions still apply. Hosted Comfy Cloud is unsupported for this profile. Optional `trimap_radius` is1–64 (default12), `subject_confidence`0.1–0.9 (default0.5). Source dimensions/FPS are preserved within its catalogue bounds. This is distinct from LTX automatic alpha generation.

### Character training on Local ComfyUI

Character training uses a configured Linux/WSL2 CUDA ComfyUI host with the pinned isolated trainer and model files described in [CHARACTER-TRAINING-RUNTIME.md](../custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md). The lightweight application host needs no training weights. Training is not available on hosted Comfy Cloud and is not a prerequisite for VFX. A connection check exposes `training_available`/`training_detail`; prerequisite detection is not an optimization or identity-quality proof.

`POST /api/apps/{soul-id-cast|ai-influencer}/documents/{document_id}/characters` accepts `expected_revision`, `name`, `dataset_asset_ids`, `trigger_token`, `steps`, `resolution`, `rank`, `learning_rate`, `seed`, `provider: "local"` (the default). The dataset must already be attached:20–50 distinct still PNG/JPEG/WebP files, at least128pixels per side, no more than32MiB each/512MiB total. The response is `{character,job}`. Training submits the genuine training graph through the configured ComfyUI connection and ordinary serialized application queue. Cancellation uses the existing job endpoint; retry starts a new training job rather than claiming checkpoint resume.

`GET /api/characters` lists persisted records; `GET/PATCH/DELETE /api/characters/{id}` reads, renames or removes an inactive unreferenced registry record. `GET /api/characters/{id}/manifest` downloads provenance. Deletion does not erase the model cache on the ComfyUI host. Training jobs/dataset assets remain protected while referenced. Only a successfully validated adapter becomes ready. Inference uses `character_adapter_id` and `character_strength`0–2 on matching `flux3-klein-base`, on the same registered provider/ComfyUI host. The server checks the host binding and trusted native path; the native loader verifies the adapter SHA, and the graph inserts the trigger after caption expansion. Distilled profiles and cross-host/provider reuse are rejected. Bundles include adapter path/hash requirements, not private weight bytes. A completed training process does not guarantee identity generalization.

### Sequence narration, music and captions

Ming synthesis and Qwen recognition/alignment use the configured Local ComfyUI connection and an optional Linux/WSL2 CUDA runtime. Install the pinned isolated environments and models on that host using [NARRATION-RUNTIME.md](../custom_nodes/openframe/NARRATION-RUNTIME.md), then check `narration_runtime` and exact model capabilities. Hosted Comfy Cloud does not expose this custom speech path. Choose `audio_provider: "local"` explicitly for new sequence requests. Existing uploaded audio and manual-caption assembly need only the application's FFmpeg runtime; they do not require speech inference.

Each shot accepts `narration:{text,voice,language,speed,start}`. Voices are `US_Emma`, `UK_George`, `灵小柔`, `灵楷`; language is English/Chinese, speed0.75–1.5, start seconds within the shot. Empty text creates no speech job. Actual Ming speech and optional Qwen recognition/alignment run as separate persisted child jobs on the existing serialized application queue, through ComfyUI HTTP uploads/prompt/history and the installed native nodes. Results expose `narration_job_id`, status/progress, `narration_output` and measured duration. Overlong speech fails instead of being cut. Consecutive speech cannot overlap across visual transitions.

Episode options add `background_audio_asset_id`, `background_audio_start`, `background_gain`, `duck_background`, `narration_gain`, `shot_audio_gain`. Assets must be attached and cover the measured duration; music is not looped. Existing `audio_asset_id` is the foreground soundtrack and cannot be combined with per-shot narration. `keep_shot_audio` explicitly mixes scene audio with narration. The assembly records gains, ducking and a0.95peak limiter.

`captions:{mode,language,burn_in,cues}` supports none/narration/soundtrack/manual. Soundtrack mode requires the explicitly selected foreground soundtrack. Generated cues come from recognized words, not evenly distributed script text. Each editable cue is `{start,end,text}` within the actual episode; cue intervals must be ordered and non-overlapping. SRT/VTT are available at `/api/sequences/{id}/episodes/{zero_based_index}/captions.srt` and `.vtt`.

Inactive corrections use `PATCH /api/sequences/{id}/episodes/{ei}/shots/{si}/narration` with `{expected_revision,narration}`, or `PATCH /api/sequences/{id}/episodes/{ei}/captions` with `{expected_revision,cues,burn_in,reassemble}`. Both return a full updated sequence. Narration correction retains completed video and invalidates only changed speech, derived captions and assembly; explicitly resume missing work. Caption-only reassembly requires all shot/narration media complete and reuses it without inference. Clearing cues/removing burn-in is supported. New assembled outputs get new immutable paths; older assets remain retained. Existing CPU/API and recorded private-runtime proofs are described in the validation report; they are not a claim that every independent host installation has been verified.

### Local visual planning

`GET /api/planner` reports available planning profiles. For the current visual planner, use `provider: "local", model_id: "qwen3.8-planner"` with `POST /api/apps/{app_id}/documents/{document_id}/plans`. The configured ComfyUI host must expose `OpenFrameVisualPlanner` and the pinned isolated CUDA environment/model from [PLANNER-RUNTIME.md](../custom_nodes/openframe/PLANNER-RUNTIME.md). Explicitly attached images and bounded timestamped video samples are analyzed; audio and arbitrary social URLs are not. References must belong to the saved document. The proposal records observations, hashes, sampled times, host identity and exact graph/model provenance. Reopen it with `GET /api/plans/{id}`, review/edit shots and approve a sequence separately; planning never silently starts generation. Legacy CPU text planners remain separately labelled choices, not automatic fallbacks. Hosted Comfy Cloud planning is unsupported. The recorded private GPU loopback exercised this actual Local HTTP/node/runtime path, but does not prove installation on an independent PC.



### Explicit LTX editing audio

For LTX2.3 and LTX2.5 `inpaint`/`restyle`, optional `audio_mode` is `source`, `generated`, or `silent`. The model catalogue declares this per task in `audio_modes_by_task`. It is authoritative over the two legacy booleans: source sets `preserve_audio=true, generate_audio=false`; generated sets the reverse; silent sets both false. Source uses the selected trimmed original recording and stays silent when that source has no audio. Generated uses native joint audio/video diffusion and its decoded waveform, without an original-audio override. Silent exports no audio stream. This control does not promise separately editable sound effects or audio outside the selected visual mask.

Omitting/nulling `audio_mode` retains historical execution exactly: LTX2.5 editing freezes source audio or silence according to `preserve_audio`, ignoring the old `generate_audio` switch; LTX2.3 keeps original-audio priority with its historical generated-audio fallback. Stored graphs are not rewritten. Unsupported model/task/provider combinations fail validation. LTX2.5 hosted Cloud is implemented for inpainting only; LTX2.3 retains the native-diffusion/local-mux route. Cloud wiring checks do not establish generated-audio runtime quality.

Execution metadata records `audio_policy`; output asset metadata records whether an actual audio stream exists. API/UI graphs and full bundles retain the selected mode and actual audio routing. The actual private generated-edit run reviewed case has 49 video frames, non-silent stereo 48kHz audio, and identical decoded result/raw audio from a silent input. Audio is 2.010s versus 2.041667s video, consistent with the native causal audio-latent lattice. This establishes generation/routing, not perceptual audio quality or a live Cloud pass. `export_uncomposited=true` optionally adds role `uncomposited`: native decoded RGB, padding cropped, before Laplacian blending and final original-plate compositing. It is auxiliary output, never counted as an additional final result.


### Native LTX2.5 hosted inpaint boundary

`provider_tasks["comfy-cloud"]=["inpaint"]` is enforced. The adapter translates only media helpers in the recorded IC-LoRA graph; native checkpoints, sampling, refinement and explicit audio routing remain selected. The optional full edited starting frame retains both native image-guide stages. Source/mask/audio/reference preparation remains local. Static/flow masks need no local model runtime; SAM2 still needs the configured exact local tracker.

Native Cloud output is a composited H264 CRF17 video, plus requested `uncomposited` video before plate compositing. Source audio is an explicitly trimmed prepared waveform; generated audio comes from native AV decoding; silent mode connects no audio output. With removal lighting correction, `inpaint_composite_mode="plate-fit"`, or Standard/High bitrate selected, the native video is role `preview`; the app consumes pre-composite PNGs and native audio to create a separately named `result`. Plate fitting uses the exact original floating mask and source, then one alpha composite. It does not consume the preview or blend its feather twice. SciPy is part of the `cloud` extra; missing plate-fit dependencies fail before a Cloud submission.

`workflow_cloud_api.json` and `workflow_cloud_ui.json` use relocated prepared inputs. `CLOUD-PROCESSING.json` records the native encoding and local finishing. The canonical local replay graph is separate. Native composite masks are 8-bit (maximum rounding error 0.5/255); local finishing retains the original floating mask but receives 8-bit generated PNGs. These are disclosed transport differences, not an exact floating-point equivalence claim. No new live Cloud inference was performed.

### Sphere Relight

`ltx-2.3-relight` / `relight` accepts a source video and one prepared lighting-sphere PNG. `relight_rotation` (−180..180), `relight_elevation` (5..85), and `relight_intensity` (.2..3) record renderer controls; they do not synthesize an image on the server. `relight_sphere.filename` is portable as the reference input. The released recipe is fixed 1280×704/24 fps, 9–121 frames on the 8n+1 lattice, 8 steps/CFG1/strength1; source/silent audio only. Masks, extra references, layout and enhancement are rejected. Use configured Local ComfyUI; the matching adapter is absent from the inspected hosted Cloud catalogue. Lighting and identity fidelity require visual review.
