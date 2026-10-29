# Architecture

OpenFrame has three runtime boundaries: a browser studio, a local durable API and a selected ComfyUI execution provider. The application does not implement diffusion inference in its web server. Every generative model profile produces an explicit ComfyUI API graph.

## Request path

```text
React studio / scripts/render.py
              |
         FastAPI API
              |
      SQLite job + asset records
              |
      one background render worker
              |
        selected provider
        /       |        \
   local     Modal      Comfy API
 ComfyUI    ComfyUI     deployment
        \       |        /
        full output media
              |
   asset library + job provenance
```

`frontend/` is React, TypeScript and Vite. It uploads media and exchanges JSON with `/api`. The development server proxies that prefix to FastAPI. The built interface is served by the same API process, so frontend code does not need provider credentials. Headless clients use the identical endpoints.

`backend/app.py` owns request validation and HTTP endpoints. `backend/models.py` defines request shapes; `engine/catalog.py` supplies actual model/effect capabilities. The backend validates model/effect compatibility, source/mask requirements, exact frame/dimension constraints and available source duration before accepting a render.

## Durable state and media

`backend/store.py` uses SQLite in the configured data directory (`.openframe/` by default). Assets, jobs, presets and settings have durable records. The database uses WAL mode and a process lock; operations use short transactions. Run one API process because its render worker owns the single local queue.

Media bytes live on disk, outside SQLite. `backend/media.py` validates images/video, records dimensions/timing/audio metadata, produces small thumbnails and hashes files. Identical uploads reuse an existing asset if its file remains available. Files use generated identifiers; user filenames are display metadata. API responses do not expose internal filesystem paths.

Video frame extraction is on demand, directly into the response, rather than repeatedly persisting seek previews. Full output videos are registered separately from thumbnails. A thumbnail or sampler preview is never treated as final generated footage.

Deleting a job retains its media in the library. Deleting an asset requires removing referencing jobs first, protecting saved recipes from broken inputs. Saved presets clear source/mask/reference IDs so they can be reused with new footage. The separate per-job recipe preserves the exact input IDs and hashes.

## Job lifecycle

`backend/jobs.py` runs one background inference thread. An atomic transaction claims the oldest queued job. The worker resolves immutable asset IDs to local files and passes the request, assets, output directory, provider settings, progress callback and cancellation callback to `engine.runner.run_job`.

Progress is throttled to one persisted update per second. Completion, cancellation and failure are written immediately. The worker rejects empty or nonexistent output files and any engine output path outside that job's output directory. Only real media produced by the engine can complete a job successfully.

Queued cancellation is immediate. Running cancellation is cooperative: the engine must cancel or stop its remote/local work, then return. The studio exposes the cancelling stage while this happens. A failed render remains failed; there is no alternative provider or synthetic output fallback.

On restart, queued jobs remain pending. Jobs previously marked running become failed with an interruption message. The server does not blindly submit those jobs again, because their remote execution may have survived the local interruption. A user-triggered retry creates a new job using the recorded request and seed.

## Models, workflows and providers

`engine/catalog.py` is the source of supported model/effect combinations. Effect cards are recipes for generation, image animation, masked editing or restyling. They do not imply custom training for each card title.

`engine/workflows.py` builds only the selected model's graph. This matters because ComfyUI validates node classes before execution: adding every optional backend into one submitted graph would require their classes to be available even when not selected. Backend templates share user-facing concepts, while each retains its own conditioning and frame/dimension rules.

The initial model families are LTX and Wan VACE. The LTX Fast profile is a separate lightweight generation model, not a substitute for LTX 2.3's masked-editing path. Unsupported architectures require a new graph/profile implementation, rather than swapping an unrelated checkpoint filename.

LTX 2.3 masked editing uses different pipelines for the two effects. Removal runs a conditioned half-resolution pass, then a full-resolution refinement pass, followed by boundary blending and removal-specific lighting matching. Replacement uses one full-resolution pass with IC-LoRA source conditioning retained throughout; lighting matching stays off so it does not wash out the new object's colours. Both use the matched LTX 2.3 checkpoint/adapter profile. This is a concrete per-effect implementation, not a claim that one sampler layout is best for every scene.

Wan image-to-video supplies the uploaded image to VACE's control-video branch with a known black opening-frame mask; native padding allows later frames to be generated. Optional reference-guided generation uses the separate reference-image branch. A reference image does not imply exact source-frame or product-identity preservation.

`custom_nodes/openframe/` provides the workflow operations required for source video, masks, temporal propagation, compositing and final video/audio output. Tracking can use SAM2.1 mask propagation, optical flow or a static mask; the selected method is recorded in the request. An optional exported matte is a separate output role. Source video begins at `trim_start`, is resampled to the requested FPS and is cut to the requested frame count. The API rejects insufficient source duration; the media node also checks decoded frame availability. A generation mask and a final preservation mask are distinct concepts.

New graphs explicitly select `smooth-inward` feathering: a smoothed signed mask-distance contour feeds an interior smoothstep, capped by the original inward ramp. This reduces rasterized diagonal boundaries without blurring footage or changing exterior pixels. Dilation expands generation context, not the final preservation region. The source node's optional `feather_method` defaults to the earlier Gaussian behavior when absent; explicit earlier `inward` graphs retain their distance-ramp behavior. The save node's optional `match_lighting` likewise defaults to false; current removal graphs explicitly enable it. Stored execution graphs are exported unchanged except for portable input filenames, so an older job is not silently converted to the latest replacement or feathering pipeline. Retrying its request creates a new job using the current template.

`engine/runner.py` owns provider transport and job execution. Local execution uploads assets to the chosen ComfyUI instance and collects its real outputs. Modal executes a ComfyUI worker with persistent remote caches. A custom Comfy API endpoint requires the complete models and utility-node deployment.

`engine/cloud.py` handles hosted Comfy Cloud separately. An API key uses the SDK; otherwise an authenticated installed CLI can submit to the actual hosted GPU service through OAuth. This is not the partner-model Router API. Credentials remain in the SDK/CLI process and never enter exported graphs. Live node/model availability is checked before GPU submission; missing exact weights and unsupported tracking fail explicitly.

Hosted Cloud does not install arbitrary utility-node packs. `custom_nodes/openframe/media.py` therefore supplies the identical CPU mask, compositing and encoding operations to both the native nodes and the host adapter, without requiring Torch in the web-server environment. The app prepares aligned, lossless RGB source and generation-mask video. Native Cloud nodes load those frames, construct the green guide and execute the selected model graph; two-stage removal remains one Cloud job. Native SaveImage returns lossless 8-bit PNG frames. Local CPU processing composites the original plate, preserves/encodes audio and writes the final video. Generated pixels are quantized to 8 bits before this local composite; bitwise equality with a native float-buffer pipeline is not promised. The host bounds estimated media buffers to 2 GiB and streams final encoding; downloaded raw frames are transient while prepared inputs remain for provenance.

The hosted service can stop a submitted workload at its own execution limit. OpenFrame preserves that failure and the requested frame count; it does not automatically lower resolution, shorten duration or submit a paid retry. The observed 97-frame portrait removal failed, while an explicitly requested 49-frame version completed. These observations do not establish a universal service limit. Cloud metadata `seconds` measures transport through final encoding after initial local preparation; it is not pure GPU time and excludes the initial SAM2/preparation phase.

Static/optical-flow masks and uploaded mask videos need no local inference runtime. Optional SAM2 tracking uses `engine/cloud_tracking.py` to send a mask-only graph to the configured local ComfyUI connection. Provider checking reads an explicit node capability flag for the SAM2 package and exact small checkpoint; actual runtime success is still checked per job. The existing native source node initializes SAM2 with the painted mask via `add_new_mask`. The bridge requests zero dilation/edit margin/feather, downloads binary tracked masks, and then applies the shared host helper once. A local tracking failure never silently switches to optical flow and occurs before Cloud diffusion submission. Native Cloud SAM2 wrappers that derive sparse points from a mask were not substituted for this contract. Tracker provenance and the raw lossless tracked-mask video are retained for full-bundle replay. This is explicitly a mixed local-tracking/Cloud-diffusion execution path.

Provider credentials stay server-side. Saved settings override environment defaults. The API returns only presence flags for secret settings and removes known secret values from provider errors. Settings changes affect subsequent jobs; a running job receives a settings snapshot.

## Reproducibility and handoff

Each job records its resolved model, effect, provider, seed, parameters and source IDs. Successful execution stores the graph and engine metadata. `/api/jobs/{id}/workflow` exports its stored complete local replay recipe. `/api/jobs/{id}/bundle` streams a recipe ZIP containing graph, manifest, source hashes, pinned runtime/model and selected tracker requirements, custom-node code and setup instructions. With `include_media=true`, it also streams original source/mask/reference files under names already bound into the portable graph. No duplicate ZIP is written to server disk. Model weights and generated output media remain separate. For local/Modal/custom-deployment jobs, the full recipe is the actual executed graph. Hosted Cloud records its actual diffusion graph separately as `workflow_executed_api.json`, with a portable copy in `workflow_cloud_api.json`, prepared inputs and `CLOUD-PROCESSING.json` describing the local processing boundary. The Cloud graph alone produces intermediate frames, not the final composite. Pinned local runtime requirements describe replay, not Cloud's provider-managed runtime. A canvas graph is included only when supplied; the hosted hybrid route currently exports API graphs.

`scripts/package_release.py` creates a separately reviewable source archive from explicit source/document/public-asset allowlists. It excludes `.env`, local studio data, dependencies, model weights, reference screenshots and validation media. A manifest contains per-file SHA-256 values. An unchanged source tree reuses an identical existing archive rather than rewriting it.

## Verification boundary

The architecture supports local UI/API use and multiple compute targets. Actual verified executions, visual checks and remaining provider limitations belong in `docs/VALIDATION.md`. Source structure alone is not evidence of successful GPU inference or equivalent quality across models. Validation is performed after the complete requested implementation, following the user's development rule.
