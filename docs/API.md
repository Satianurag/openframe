# OpenFrame API

OpenFrame runs a single-user FastAPI service at `http://127.0.0.1:8000`. Interactive endpoint documentation is at `/docs`, and the OpenAPI schema is `/openapi.json`. Run **one Uvicorn worker**: the application owns one inference queue per process. A local SQLite database persists assets, jobs, settings and presets across restarts.

The frontend calls the same API described here. Local, Modal and Comfy API compute use the same job request; providers do not share identical deployment requirements. An accepted job means it entered the queue, not that a GPU render succeeded.

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
  -d '{"default_provider":"modal","modal_app":"openframe-comfy"}'
curl -X POST http://127.0.0.1:8000/api/providers/modal/check
```

Settings fields:

| Field | Default / purpose |
| --- | --- |
| `default_provider` | `local`; choices `local`, `modal`, `comfy-cloud` |
| `comfy_url` | `http://127.0.0.1:8188` |
| `comfy_api_key` | Optional bearer credential for protected self-hosted Comfy |
| `comfy_cloud_url` | `https://cloud.comfy.org`, or a compatible Comfy API deployment |
| `comfy_cloud_api_key` | Credential for the selected Comfy API endpoint |
| `comfy_cli_path` | Optional installed `comfy` executable; empty searches PATH and existing uv tool installs |
| `modal_app` | `openframe-comfy` |
| `modal_environment` | `main` |
| `modal_function` | `render` |
| `modal_volume` | `openframe-assets` |
| `modal_progress_dict` | `openframe-progress` |

Secrets supplied in PATCH remain server-side. Omitting a secret leaves it unchanged; sending an empty string clears its saved value. URLs must be HTTP(S) and must not contain embedded credentials. Environment defaults use the same names prefixed with `OPENFRAME_` in uppercase; saved settings override those defaults. `.env.example` lists the fields.

A connection check is read-only and returns `available`, `detail`, `checked_at`, and provider-specific diagnostics. It does not submit a render. Modal authentication uses the SDK/CLI environment; the studio does not collect Modal tokens in the browser.

For hosted `https://cloud.comfy.org`, an API key uses the official SDK. Without one, OpenFrame can reuse an existing server-side `comfy-cli` 1.23+ OAuth login (`comfy cloud login`). No application login or billing purchase occurs. A configured key takes precedence; OAuth is not silently used after a rejected key. The hosted connection check reports `auth_mode`, available exact model profiles and `supported_tracking_methods`; the CLI route also reports remaining free runs/credit balance. Zero balance and no free allowance is unavailable. A model selector does not guarantee that its exact weights are installed on every provider; submission checks exact filenames and rejects missing profiles without substitution.

Hosted Cloud runs native model/diffusion nodes, including both LTX removal passes in one graph/job. The local app prepares aligned source/mask video and performs final plate compositing/audio encoding using the same CPU helpers as the custom nodes. Static masks, optical flow and supplied mask videos need no local model runtime. SAM2 uses an optional mask-only graph on the configured `comfy_url`/`comfy_api_key` connection; that instance must report the current OpenFrame nodes, SAM2 package and exact `sam2.1_hiera_small.pt` checkpoint. It initializes from the actual painted mask with `add_new_mask`, without approximating it with points. Cloud connection checks include `local_sam2` diagnostics and advertise `sam2` only when that local runtime is detected. Unavailable or failed local tracking stops before a Cloud GPU submission. Edit margin/dilation/feather apply once after tracking; the tracker graph and raw tracked-mask video remain in the full project bundle. This route is Cloud diffusion plus local SAM2, not self-contained Cloud tracking. Local media buffers are limited to an estimated 2 GiB per clip. Prepared uploads use lossless RGB video; Cloud returns lossless 8-bit PNG frames, so generated pixels are quantized to 8 bits before the local composite. Custom SDK endpoints continue to require the full OpenFrame node pack and weights.

Observed hosted limits are workload-dependent: the 97-frame, 576×1024 two-stage removal verification was stopped by the service with `Job execution time exceeded maximum limit`; a separately requested 49-frame version succeeded. This is evidence for those cases, not a published frame cap. A failed request is never silently shortened or retried. Execution-limit errors retain the provider message and advise fewer frames/lower resolution or Modal/local execution. Hosted generated-audio transport is implemented, but its final end-to-end check was cancelled at the user’s request during output download; it is not a verified audio pass. Source audio was present in the successful tracked result, but exact synchronization was not established.

For a hosted Cloud job, the normal workflow export is its stored complete local replay recipe. The bundle separately records the actual native Cloud execution graph and local-processing manifest; the Cloud graph alone produces intermediate frames. Full-media bundles include the originals and prepared Cloud inputs. Hosted jobs currently provide API-format graphs rather than a full-pipeline UI canvas. See `CLOUD-PROCESSING.json` and the bundle README before re-executing only the Cloud stage.

## Submit a render

```json
{
  "model_id": "ltx-2.3",
  "effect_id": "remove-object",
  "provider": "modal",
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
- `export_mask:true` requests a mask-video output for VFX jobs. Job outputs carry `role` (`result` or `mask`) so clients can choose the rendered result for comparison and offer the matte separately.
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

Job records contain `id`, `status`, `progress` (0–1), `stage`, timestamps, the resolved `request`, `warnings`, `outputs`, `error` and `favorite`. Status values are `queued`, `running`, `succeeded`, `failed`, `cancelled`.

| Request | Behaviour |
| --- | --- |
| `GET /api/jobs?limit=100&offset=0` | Newest-first job list plus total/offset |
| `GET /api/jobs/{id}` | Current state; poll around every two seconds while active |
| `POST /api/jobs/{id}/cancel` | Cancel queued jobs immediately; request cooperative cancellation of running inference |
| `POST /api/jobs/{id}/retry` | Create a new job from a terminal job's recorded request |
| `PATCH /api/jobs/{id}` with `{"favorite":true}` | Save favorite state |
| `DELETE /api/jobs/{id}` | Delete a terminal job record; retain its media in the library |

`outputs` hold full media asset records, not inference previews. Download each output through its `url`.

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
