# OpenFrame

A ComfyUI video and VFX studio matching the public Higgsfield video editor's layout and controls. Paint a mask, choose an effect and model, render locally or on a GPU worker, compare the result, and export the workflow that produced it. OpenFrame uses its own branding, supported open-model choices and original demonstration media, without an account screen.

OpenFrame is an independent open-source project. The reference interface is Higgsfield; inference is performed by your selected ComfyUI worker.

## Features

- Text-to-video and image animation, with selectable LTX and Wan model profiles.
- Masked video removal/replacement, full-scene restyling and editable effect recipes.
- Browser mask painting, optional temporal tracking, generation strength and preservation controls.
- Source audio preservation where applicable; explicit model-specific frame/dimension constraints.
- Local ComfyUI, Modal GPU workers and configured Comfy API deployment connections.
- Persistent job queue, progress, cancellation, retry, history and favorites.
- Media library, saved recipes, before/after comparison and full-quality downloads.
- ComfyUI workflow export and per-job reproducibility bundle.

Effect cards are workflow/prompt presets. They are not a claim that every named transformation has a dedicated trained model or guaranteed visual outcome. See [validation evidence](docs/VALIDATION.md) for what has actually been exercised.

## Run the studio

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22.12+, npm and FFmpeg/ffprobe. The web application itself does not need a GPU. Generation requires one of the execution providers below.

```bash
# From this repository:
python3 scripts/dev.py
```

Open the Vite URL printed in the terminal, normally `http://127.0.0.1:5173`. The launcher selects free frontend and API ports in 5173–5193 and 8000–8020 and configures their connection automatically; interactive API documentation is at the API's `/docs`. The launcher installs missing frontend dependencies and uses the project's Python environment with Modal/cloud client extras. Ctrl+C stops both processes. If running the CLI against a non-default API port, pass `--url http://127.0.0.1:PORT`.

To run a built interface from the API server:

```bash
cd frontend
npm ci
npm run build
cd ..
uv run --python 3.12 --extra modal --extra cloud uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Create `.env` from `.env.example` if you want environment defaults. Settings can also be configured in the application. Credentials are stored on the server and excluded from exported workflows/bundles. The default data directory is `.openframe/` and includes uploaded/generated media, saved recipes and the SQLite database. Keep it across upgrades.

## Choose compute

### Modal GPU

Use your existing Modal authentication, or authenticate with the Modal CLI before deployment. The app uses your Modal account's private function invocation; it does not require a public inference endpoint.

For masked LTX VFX, first obtain access to the [official inpainting adapter](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting). For automated downloads, create a Modal secret named `openframe-huggingface` containing `HF_TOKEN`, with permission to read that gated model. The token stays in Modal's secret store, outside application code and workflow exports.

```bash
uv run --python 3.12 --extra modal modal deploy deploy/modal_app.py
OPENFRAME_HF_SECRET=openframe-huggingface uv run --python 3.12 --extra modal modal run deploy/modal_app.py --prepare --model ltx-2.3
```

The second command prepares LTX 2.3 and its SAM2 tracker on CPU. Prepare each other profile you want with `--model ltx-0.9.8` or `--model wan-vace`, without the secret prefix; reuse the existing cache on subsequent runs. LTX 2.3 generation without its gated editing adapter can be prepared with `--base-only`, also without a secret. Then select **Modal GPU** in the studio settings. The deployment keeps model weights on a persistent Modal volume; your laptop receives inputs/outputs rather than the model cache. An unprepared profile fails with setup instructions instead of downloading weights on a GPU. GPU execution and storage use your Modal account. The worker configuration and exact models live in `deploy/` and `engine/`.

### Local ComfyUI

Start a compatible ComfyUI instance and configure its URL in Settings (default `http://127.0.0.1:8188`). Install the OpenFrame custom nodes and the checkpoint/text-encoder/VAE files required by the chosen model profile. Use the local setup command to install the profile files and node packs:

For the gated LTX editing adapter, obtain repository access and authenticate locally with `uv run --python 3.12 hf auth login` before setup.

```bash
uv run --python 3.12 python -m engine.setup --comfy-dir /path/to/ComfyUI --model ltx-2.3
```

Run the pip commands printed by setup in ComfyUI's Python environment. For the default SAM2 tracker, also install the pinned SAM2 package and run setup with `--model sam2`; see [the workflow installation guide](workflows/README.md). The model manifest identifies the required files. The app uploads source media to ComfyUI and collects the actual outputs.

The frontend/API can run on macOS, Windows or Linux. Inference compatibility depends on the selected model, ComfyUI installation and GPU; do not infer local model support from the fact that the web interface starts.

### Comfy Cloud / Comfy API deployment

For hosted Comfy Cloud, install the `cloud` extra and either configure an API key or sign in with an installed Comfy CLI (`comfy cloud login`) on the app server. Settings can detect that CLI session without exposing its credentials; an optional executable-path field handles nonstandard installations. Real hosted execution was verified through CLI OAuth. API-key and custom-deployment transports remain separate supported configurations, without an end-to-end account-specific verification claim.

Hosted Cloud runs the native model/sampling graph. OpenFrame prepares aligned source/mask inputs and performs final compositing, audio handling and encoding locally using the same utilities as its Comfy nodes. Static and optical-flow masks need no local model runtime. SAM2 uses the configured local ComfyUI's exact mask-initialized tracker and small SAM2.1 checkpoint; Settings reports whether that optional runtime is detected. This is explicitly mixed execution. A missing tracker or model fails clearly instead of silently selecting another method.

Exports include the complete local-replay graph, actual Cloud-executed graph, prepared inputs and a processing manifest. The Cloud graph alone returns intermediate frames. Custom Comfy API Builds can still execute the complete graph when they include the required models and OpenFrame node pack. See [Comfy's Developer Platform](https://comfy.org/platform/) and [SDK documentation](https://docs.comfy.org/development/api-development/sdks).

OpenFrame does not silently redirect a failed cloud job to another provider. The job records the selected provider and reports execution failures.

## A VFX session

1. Open Video / VFX and select **Vanish** or **Replace**.
2. Choose an editing-capable model such as **LTX 2.3**. LTX Fast is a separate lightweight generation profile, not the masked-editing backend.
3. Upload the source video and paint the full target area, including affected shadows and a small surrounding margin. Fresh LTX VFX selections recommend a 1024-pixel longest side; the smaller preview option remains available.
4. Select tracking/preservation settings and describe the desired visible result.
5. Choose compute and generate. Follow progress in the studio/history.
6. Review the full result against the original, including motion, edges and affected shadows.
7. Download the video and export the workflow/reproducibility bundle.

A generation mask and the final allowed-change region serve different purposes. **Edit margin** expands the allowed region before feathering (default 12 pixels for tracked edits, 0 for static masks); **Generation margin** adds model-conditioning context. Edit margin can include adjacent pixels, so inspect occluders and nearby objects. If an edit must change shadows, reflections or interactions, include those affected areas. Continuous inward contour smoothing avoids a stepped mask boundary without blurring generated footage.

## Headless use

The API accepts the same request used by the frontend. Save a request as JSON (or use a saved job JSON with its `request` field), then run:

```bash
uv run --python 3.12 python scripts/render.py recipes/ltx-masked-vfx.json --provider modal --source source.mp4 --mask mask.png --output renders
```

The script uploads supplied media, queues one job, follows its status and downloads the actual output files. Ctrl+C requests cancellation. Existing asset IDs work when the files are already in this studio's library.

## Packaging

```bash
docker compose up --build
```

This builds the frontend and API image and binds it to localhost port 8000; set `OPENFRAME_PORT=8010` when that port is occupied. It uses a named volume for studio data. This is the application container; inference still runs through the selected provider. Pass Modal credentials through environment configuration when invoking Modal from inside a container. Never include them in images, source control or workflow exports.

## Project structure

- `frontend/`: React/TypeScript interface.
- `backend/`: FastAPI, media storage, durable job queue and settings.
- `engine/`: model/effect catalogue, ComfyUI graph builders and provider execution.
- `custom_nodes/`: reusable OpenFrame media/mask/compositing nodes.
- `deploy/`: Modal GPU runtime and persistent cache configuration.
- `workflows/`: inspectable workflow and model/setup artifacts.
- `scripts/`: local launcher and headless recipe client.
- `recipes/`: editable example requests; source/mask files are supplied when rendering.
- `docs/`: interface direction, architecture, validation, attribution and competition package.

## Competition and reuse

The demonstrated VFX workflow uses LTX as its core video model. Other model profiles remain optional. [The competition package](docs/COMPETITION.md) covers the demonstration and submission assets; publishing/submission is a separate user action.

Application code: [MIT](LICENSE). Runtime dependencies and model weights retain their own licenses; see [third-party attribution](docs/THIRD_PARTY.md). No model weights or Higgsfield commercial demo footage are bundled here.

## Review package

Prepared alongside the source archive: `openframe-demo.mp4` (70.40 seconds), `openframe-examples.zip` (portable workflows, inputs, expected outputs and provenance), and standalone removal/replacement comparison videos. The source archive excludes model weights, credentials, local studio history and validation recordings. See [validation](docs/VALIDATION.md) for measured results and limitations, and [competition preparation](docs/COMPETITION.md) for the remaining publication/submission steps.
