# Separate app API

This API is additive. Existing `/api/jobs`, assets, settings and VFX execution retain their contracts. App documents and associations live in the same SQLite database; media is shared by immutable asset ID. No schema migration rewrites earlier render requests or execution graphs.

## Catalog and documents

`GET /api/apps` returns `{items:[{id,name,operations:[{id,label,available,reason,effect_ids,model_ids}]}]}`. Public suite navigation exposes9 functional workspaces: `content-factory`, `cinema-studio`, `ai-influencer`, `marketing-ads`, `soul-image`, `soul-id-cast`, `popcorn`, `katana`, `genjutsu`, plus the `mini-apps` navigation hub. The separate `/studio/vfx` editor is the tenth functional main workspace. The backend retains `supercomputer`, `canvas` and `speak` identifiers for compatibility, but these are excluded from published navigation. `available` means an implemented operation, not that a provider is connected, its weights are installed, or its output quality is verified. Check `enabled_providers`, task-specific capabilities and the provider separately. Unsupported operations do not fall back to generic video generation.

- `GET /api/apps/{app_id}/documents?limit=100&offset=0`: `{items,total,offset}`, newest updated first.
- `POST /api/apps/{app_id}/documents`: creates a document and returns HTTP201.
- `GET /api/apps/{app_id}/documents/{id}`: retrieves one document within that app.
- `PATCH /api/apps/{app_id}/documents/{id}`: partial fields plus mandatory `expected_revision`; supplied `state` replaces the entire state object. Omitted fields remain unchanged. No-op saves retain the revision and timestamp.
- `DELETE /api/apps/{app_id}/documents/{id}?expected_revision=N`: deletes only the document. Completed jobs, historical snapshots and media remain.

Create body:

```json
{
  "title": "Window scene",
  "schema_version": 1,
  "state": {"prompt": "A clean window ledge", "source_asset_id": "recorded-run"},
  "asset_ids": ["recorded-run"]
}
```

The response adds `id`, `app_id`, `revision` (initially1), `created_at`, `updated_at`. All listed assets must exist. Recognized `asset_id`/`*_asset_id` and list forms in state, including camel-case equivalents, must appear in `asset_ids`. References from current documents and saved job snapshots protect media from deletion. Removing a document does not remove a completed job's historical reference protection.

State is a JSON object, at most256KiB,12 nesting levels and10,000 values. Text values are at most16,000 characters, titles160, attachments128. Credentials, filesystem-path fields and embedded `data:`/`file:` media are rejected. Upload media separately. Only schema version1 is accepted. Revision conflicts return409; reload or explicitly reconcile instead of blindly resaving.

Content Factory state has the following validated shape:

```json
{
  "prompt": "",
  "length": 30,
  "episodes": 1,
  "mode": "local",
  "tab": "explore",
  "reference_url": null,
  "reference_asset_id": null,
  "attachment_asset_ids": [],
  "style_id": null
}
```

Length is15–300 seconds in5-second increments; episodes1–4; mode `local|claude`; tab `explore|generations`. Reference links must be HTTP(S) without embedded credentials. Saving a link does not fetch or analyze it. Series rendering uses the separately reviewed sequence plan and explicit start endpoints below; saving a brief never starts generation. Claude execution remains unavailable. Other app state objects are bounded documents; their operation requests remain independently validated by the render schema.

## App renders and provenance

`POST /api/apps/{app_id}/documents/{id}/jobs` accepts:

```json
{
  "expected_revision": 3,
  "operation": "replace-object",
  "step_id": "shot-1",
  "group_id": "scene-1",
  "request": {
    "model_id": "ltx-2.3",
    "effect_id": "replace-object",
    "provider": "local",
    "prompt": "A matte black chess knight",
    "source_asset_id": "recorded-run",
    "mask_asset_id": "abcdef0123456789abcdef0123456789ab"
  }
}
```

Every render input must first be attached to the saved document. The exact operation must belong to that app and match `request.effect_id`. Unsupported operations return409 before any job is inserted; implemented operations require a real render request. Invalid fields/inputs return422. A stale document revision returns409. Job creation, immutable document snapshot and association commit together before the worker is awakened.

The job response is the existing job record plus `app_context:{app_id,document_id,document_revision,operation,step_id,group_id}`. The engine receives only its render request, not the app layout. `step_id` and `group_id` are attribution labels, not a dependency scheduler or automatic batch execution.

- `GET /api/apps/{app_id}/jobs?document_id=...&operation=...&preset_id=...&limit=100&offset=0` returns `{items,total,offset}` containing only associated jobs. All three filters are optional and apply before counting/pagination. `preset_id` matches the immutable app step or saved document preset, allowing separate tool history across documents.
- `GET /api/jobs/{id}/app-context` returns the association and immutable `document_snapshot`; legacy unassigned jobs return404 here and remain in global history.
- Existing cancel/favorite/delete actions apply unchanged. Retry preserves the original app/document snapshot and request, creating a new job. Deleting a job removes its association; output assets remain.
- Workflow bundles include `APP-CONTEXT.json` for associated jobs and app provenance in the manifest. The stored executed graph remains authoritative; app state never rebuilds an old execution graph.

## New media and render inputs

Audio-only WAV, MP3, M4A, FLAC, OGG, WebM and AAC recordings with a readable duration are accepted by `/api/assets`. Their kind is `audio`, with duration/sample-rate/channel metadata, no fake image thumbnail, and no video-frame endpoint. Image/video ingestion is unchanged.

Additive render fields include `audio_asset_id`, `audio_start` (seconds, default0), `reference_asset_ids` and `batch_size`. Counts are model-specific: FLUX3 accepts up to10 total image inputs, including the editing source; the older Klein profile accepts4. Other profiles can impose smaller counts and fixed batch1. Non-image tasks use the single reference field only for their declared role, such as an edited full starting frame or character reference. A video-conditioning recording must cover `audio_start + frames/fps`; it is never silently looped.

Effect IDs include `create-image`, `edit-image`, `speak`, `motion-transfer`, `character-replacement`. Image operations normalize to one frame and1fps; their real image outputs may contain the selected batch. The Talking Portrait tool consumes a portrait and uploaded recording using its explicitly selected supported profile; the current LongCat1.5 recipe is distinct from the retained Wan S2V recipe. It is not a text-to-speech engine. Read fixed FPS, frame lattice, duration and dimensions from that model's catalogue rather than sharing bounds between profiles. LTX is not eligible for new Speak submissions: its uploaded-audio test produced a static mouth. Stored LTX execution graphs remain exportable unchanged; an old recipe without a stored graph returns422 if it cannot be rebuilt. Motion transfer requires a driving video and reference character image. Recast's automatic native performer selection and legacy painted-mask replacement have different mask requirements, validated by profile. The provider adapters retain recording/reference inputs in portable exports.

These image/motion/talking profiles use configured Local ComfyUI with their exact runtime/model prerequisites. Hosted Comfy Cloud does not support these custom routes; requests are rejected before submission rather than substituted. Supported LTX/VFX Cloud tasks retain their separate contracts in [API.md](API.md). Runtime, native-canvas and visual acceptance are reported separately in [DESKTOP-VALIDATION.md](DESKTOP-VALIDATION.md); source availability is not a quality pass.

`remove-background` uses BiRefNet and preserves the input image's dimensions (up to4096px) in an RGBA PNG. `generate-speech` selects an actual catalogue speech model: Ming uses the configured isolated CUDA ComfyUI runtime; retained Kokoro uses its CPU dependencies. Voice choices, script length and speed bounds belong to the selected model. Speech output is a measured audio asset, not a guessed video duration. It can explicitly feed Talking Portrait or existing-video/sequence assembly. Neither operation is advertised through hosted Cloud. See [API.md](API.md#sequence-narration-music-and-captions) for Local speech prerequisites.

## Explicit shot sequences and optional visual planning

Content Factory, Popcorn, Cinema, Marketing/Ads and the Billboard tool reuse durable sequence primitives while retaining separate screens/documents. An editable shot list is not inferred from a reference link. A nonempty document `reference_url` rejects planning/execution with an explicit unsupported-analysis error; upload actual inputs and describe the plan instead.

`GET /api/planner` reports the configured Local Qwen3.8 27B visual runtime and separately labelled legacy CPU text planners. Prerequisite detection is not inference verification. `POST /api/apps/{app_id}/documents/{id}/plans` queues a planning request with `expected_revision`, `prompt` (1–3000 chars), `style` (≤200), `target_duration` (15–300, step5), `episodes` (1–4), `seed`, `provider:"local"`, `model_id:"qwen3.8-planner"`, optional `reference_asset_ids` (up to4) and `reference_notes` (≤3000). Visual analysis requires the configured Linux/WSL2 CUDA ComfyUI runtime in [PLANNER-RUNTIME.md](../custom_nodes/openframe/PLANNER-RUNTIME.md), not a smaller CPU fallback. References must be saved-document image/video assets; videos are limited to5minutes. At most16 timestamped video frames are inspected per reference; audio and social links are not analyzed. Read `/api/plans/{id}`, list `/api/apps/{app_id}/plans?document_id=...`, or cancel with `POST /api/plans/{id}/cancel`. Successful proposals include episodes/shots, reference observations and exact model/host/sampling provenance. Proposed voiceover remains text until explicitly accepted as narration. No render starts until the user reviews and starts that separate sequence. Submitted prompt metadata is persisted immediately; errors remain errors with no canned fallback. Hosted Comfy Cloud planning is unsupported.

`POST /api/apps/{app_id}/documents/{id}/sequences` saves a **draft**, accepting:

```json
{
  "expected_revision": 3,
  "episodes": [{
    "title": "Episode one",
    "target_duration": 30,
    "audio_asset_id": null,
    "audio_start": 0,
    "keep_shot_audio": false,
    "shots": [{
      "id": "shot-1",
      "label": "Opening wide shot",
      "source_from_previous": false,
      "request": {
        "model_id": "ltx-2.3", "effect_id": "text-to-video", "provider": "local",
        "prompt": "An explicit visual shot description", "width": 512, "height": 320,
        "frames": 97, "fps": 24
      }
    }]
  }]
}
```

An optional `planner_id` links the reviewed sequence to a completed proposal in the same app document; its model provenance is copied into the sequence, while edited shot requests remain authoritative. Each episode has 1–64 explicit video shots; a sequence has 1–4 episodes and a maximum1MiB plan. Shot IDs are unique. Episode shots must share width/height/FPS. The sum of frame-aligned durations must not exceed300s per episode. A bounded assembly-buffer estimate can reject very large combinations of shot count and resolution. Editorial `target_duration`, frame-aligned `planned_duration` and measured `actual_duration` are separate; no loop, stretch or hidden trim fits a target. Content Factory's saved episode count/length must match the requested targets.

`source_from_previous:true` is allowed only after an earlier shot and only for image-to-video without a separate source image. After the prior shot succeeds, its actual last frame becomes a registered input image. The dependent job records its resolved request and the source job/output/timestamp. This is frame continuation, not automatic long-range character consistency or a generated transition.

- `GET /api/apps/{app_id}/sequences?document_id=...` and `GET /api/sequences/{id}` return sequence state, episodes and ordered shot statuses. List envelopes are `{items,total,offset}`.
- `PATCH /api/sequences/{id}` replaces an **unstarted draft** using the same body plus `expected_sequence_revision`. A sequence's `revision` is separate from the app document revision. Stale edits return409.
- `POST /api/sequences/{id}/start` requires `{expected_revision:sequence.revision}`: approval of the reviewed saved plan. It does not require a second automatic approval of each already reviewed shot.
- `POST /api/sequences/{id}/cancel` cancels the active leaf job/assembly and prevents later shots. Completed media is retained.
- `POST /api/sequences/{id}/resume` or `/retry` operates only on cancelled/failed sequences. Completed shots remain; the incomplete or failed shot is retried explicitly. An assembly failure reruns assembly, not completed Comfy renders. Active old jobs must terminate before resume.
- `DELETE /api/sequences/{id}` accepts only drafts/terminal records and retains jobs/media. Its shot jobs cannot be deleted while sequence provenance still references them.

The existing serial worker dispatches at most one leaf render at a time. Already queued VFX jobs retain FIFO priority. Shot rows are updated independently rather than rewriting an entire large plan for every progress event. Intermediate jobs and immutable app-document snapshots commit atomically. Restart recovery marks interrupted sequences/planners failed without automatic remote resubmission; recorded provider call IDs must be checked before explicit retry.

An episode assembles only when every required shot has a valid final video. FFmpeg concatenates them in order, with no implicit geometry/FPS changes or transitions. Duration and total frame count are checked before completion. Per-shot job IDs, resolved requests, input derivations, output asset IDs and hashes are preserved in episode provenance. A later failure leaves the overall sequence failed even if earlier episodes are downloadable.

Assembly is silent by default. `keep_shot_audio:true` explicitly retains every shot's audio and is rejected up front when a shot has no configured audio source. Alternatively, provide one attached audio asset and start offset; it must cover the measured episode and is trimmed only to the actual episode length. The two audio modes are mutually exclusive. No soundtrack is silently generated, chosen, looped or mixed. Assembly has a30-minute CPU bound and supports cancellation.

Supercomputer project documents use `state.kind:"project"`; chat `state.project_id` must refer to a different, existing project in the same app. A project cannot be deleted while chats reference it. A document with active planning or sequence execution must be cancelled before deletion. These are local project/grouping semantics, not a general connector or web/code agent.

## Product-link metadata import

`POST /api/import/product` with `{url:"https://public.example/product"}` returns201 and `{title,description,source_url,image_url,asset,warnings}`. `asset` is a normal imported media asset. Attach its ID to the saved Marketing document before generation. The importer chooses one still PNG/JPEG/WebP from Product JSON-LD, Open Graph or Twitter image metadata, preferring Product metadata. It does not execute JavaScript, analyze video, scrape authenticated sessions or invent product attributes. Blocked sites or missing readable images return422 and require manual upload.

Connections permit only public HTTP(S) on standard web ports. All resolved addresses must be public; the actual socket is pinned to a validated address while preserving certificate hostname verification. Every redirect repeats validation. Credentials, local/private/link-local destinations and metadata-network address forms are rejected. Limits are two concurrent imports, a30-second network budget,5-second DNS lookup, three redirects per resource,2MiB HTML, at most three image candidates and12MiB/32megapixels per image. Only the selected validated image is written; hash deduplication reuses an existing asset. Public metadata remains untrusted user-visible source material, not executable instructions or proof of an advertising claim.


## Portable image, audio and sequence exports

Leaf jobs export the stored executed graph and a portable graph that changes only media filenames. A full project ZIP includes the original PNG/JPEG and WAV/video inputs, including every ordered image-reference slot and the uploaded Speak audio. Audio trim remains in the recorded graph. Kokoro recipes include their pinned Python dependencies, spaCy wheel, OS espeak-ng requirement and all six model/config/voice files; `destination` gives each exact path relative to ComfyUI. Every recipe includes the complete OpenFrame node package, including its speech module even when speech is not used. Wan Animate recipes additionally identify the pinned pose/face node package and its dependencies; character replacement includes SAM2 only when selected.

A sequence exports its JSON manifest and individual shot workflows/full project ZIPs. It is not represented as one ComfyUI graph: each shot is a separate render, and FFmpeg assembles the verified outputs. The manifest retains ordered shots, derived previous-frame inputs, hashes, exact requests, audio choice and measured duration. Download each episode separately. There is currently no aggregate sequence ZIP or automatic cross-installation remapping of app asset IDs; each full shot project carries portable media filenames for standalone ComfyUI replay.
