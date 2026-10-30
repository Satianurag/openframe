# OpenFrame

**An open-source image, video and VFX studio built on ComfyUI.** OpenFrame brings source selection, mask painting, model controls, saved projects and portable workflows into a browser interface inspired by Higgsfield. It connects to your **Local ComfyUI** or supported **Comfy Cloud** operations.

The VFX workflow uses **LTX as its core video model**. This is an independent project, not an official Higgsfield product or a claim of complete feature parity.

## What you can do

- **Edit video:** remove or replace masked objects, use an edited starting frame, recolor/restyle, and choose supported structural conditioning and source-preserving finishing.
- **Change lighting and weather:** dedicated exterior LTX Relight with a rendered lighting sphere; Water-Simulation for rain and wet surfaces; generic restyle remains separately selectable.
- **Use video tools:** Extend, generative Reframe, Upscale, background removal, SDR-to-HDR, FPS interpolation and depth. Each tool exposes its actual model limits and output formats.
- **Create images:** FLUX3 generation/editing, ordered references, layouts, batches, region editing, outpainting, layers and portrait relighting.
- **Build sequences:** editable shot lists, image storyboards, durable multi-stage jobs, narration, music, captions and video assembly. Motion transfer, character replacement and talking portraits have separate interfaces.
- **Keep your work:** saved projects, history, cancellation/retry, comparisons, full-quality downloads, editable ComfyUI canvases, API graphs and reproducibility bundles.

Named presets are editable workflow directions, not guarantees of a particular result. Optional model profiles retain their own licenses and hardware requirements.

## Start the application

Install **Python 3.12**, [uv](https://docs.astral.sh/uv/), **Node.js 22.12+ with npm**, and **FFmpeg/ffprobe**. The interface and API do not require a GPU; generation needs a compatible ComfyUI host or supported Cloud operation.

From this repository:

```bash
python3 scripts/dev.py
```

On Windows, `py scripts/dev.py` can be used instead. The launcher reuses existing dependencies, installs missing frontend dependencies, and starts the API and Vite together. Open the URL printed by Vite, normally `http://127.0.0.1:5173`. It selects free ports in 5173–5193 and 8000–8020; Ctrl+C stops both processes. The API exposes interactive documentation at `/docs`.

For a built interface served by the API:

```bash
cd frontend
npm ci
npm run build
cd ..
uv run --python 3.12 --extra cloud uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Configure connections in **Settings**, or copy `.env.example` to `.env` for environment defaults. Keep `.openframe/` across upgrades: it contains the database, projects and uploaded/generated media. Credentials stay on the application server and are excluded from workflow exports.

## Connect Local ComfyUI

1. Install and start a compatible [ComfyUI](https://github.com/Comfy-Org/ComfyUI) on your inference machine.
2. Install the OpenFrame nodes and the selected profile's weights. For LTX2.5:

   ```bash
   uv run --python 3.12 python -m engine.setup --comfy-dir /path/to/ComfyUI --model ltx-2.5
   ```

3. Run the dependency-install commands printed by setup **inside ComfyUI's Python environment**, then restart ComfyUI. Setup preserves existing checkouts and reports required pinned revisions. Downloads can be large; reuse an existing model cache. Gated weights require repository access and Hugging Face authentication first:

   ```bash
   uv run --python 3.12 hf auth login
   ```

4. In OpenFrame **Settings**, select **Local ComfyUI**, enter its URL (default `http://127.0.0.1:8188`) and check the connection.

For optional SAM2 mask tracking, provision `--model sam2` and install the pinned tracker package printed by setup. See [workflow installation](workflows/README.md) for model/node requirements. Installing the web application alone does not install inference models.

Some optional features need additional Linux/WSL2 CUDA runtimes on the ComfyUI host: [visual planning](custom_nodes/openframe/PLANNER-RUNTIME.md), [narration](custom_nodes/openframe/NARRATION-RUNTIME.md), [performer tracking/matting](custom_nodes/openframe/RECAST-RUNTIME.md), and [character training](custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md). These are separate from the basic LTX setup.

## Connect Comfy Cloud

The launcher and built-server command above include the `cloud` dependencies. In **Settings**, select **Comfy Cloud**, use `https://cloud.comfy.org`, and configure your API key. Alternatively, sign in on the application server with an installed Comfy CLI:

```bash
comfy cloud login
```

Settings can detect that session; an executable-path setting supports nonstandard CLI installations. Check the connection before choosing a model. OpenFrame rejects unsupported combinations rather than silently switching providers.

**Cloud support is task-specific.** LTX2.5 currently supports **inpainting only** on hosted Cloud, including supported removal/replacement paths. Its other operations do not inherit Cloud support. Dedicated Water and exterior Relight require Local ComfyUI. Earlier LTX2.3/Fast/Wan routes have their own capability checks against available weights and nodes.

The application still prepares media on the app host. LTX2.5's hosted graph produces a native video; selected lighting correction, plate-fit finishing or bitrate encoding additionally runs on the app host. Earlier hybrid routes use app-side compositing/encoding. SAM2 tracking requires a configured Local tracker; static/optical-flow alternatives have different requirements. The LTX2.5 Cloud adapter has schema, media-processing and export checks, **not a completed live Cloud render claim**.

## Make and export an edit

1. Open **Video / VFX**, choose a preset and a compatible LTX profile.
2. Select the source interval and output dimensions. Paint the affected object, shadows and nearby interactions when using a mask.
3. Choose tracking and preservation settings, then describe the desired result. Supported editing profiles expose **Source / Generate / Silent** audio; source audio applies to the selected interval.
4. Generate, then inspect the whole result for motion, edges, lighting and sound.
5. Download the result and export its workflow or full project bundle.

Exports record the actual selected model, settings and dependencies. A full project includes its media; a lightweight recipe omits media. Cloud projects also record the hosted graph and app processing. Sequence exports contain individual shot projects and an assembly manifest, not one universal ComfyUI graph. Weights and credentials are never bundled.

For headless use, supply your own source and mask:

```bash
uv run --python 3.12 python scripts/render.py recipes/ltx-masked-vfx.json --provider local --source source.mp4 --mask mask.png --output renders
```

Use `--url http://127.0.0.1:PORT` if the API uses another port. The client uploads inputs, follows the queued job and downloads real outputs; Ctrl+C requests cancellation.

## Scope and limitations

Video examples validate selected intervals, not automatically an entire uploaded clip. Model frame limits, frame-rate lattices and output dimensions are explicit. Generated edits can change fine details, identities, hands, shadows or backgrounds; mask preservation applies to the declared compositing region, not a blanket pixel-perfect promise. Exterior Relight uses a fixed released recipe and sphere guidance, not calibrated physical lighting. Water can add rain/wet surfaces while small-detail drift remains.

Character training and reference-assisted generation are distinct: the tested standalone adapters did not reliably preserve likeness. A reference-assisted result improved likeness but also copied the reference composition. Depth, transitions and other model-specific effects likewise need visual review. Native GUI workflow roundtrips demonstrate import/export compatibility, not inference on every machine.

## Submission and license

The submission demonstration is **57.02 seconds**, 1920×1080 at 24 fps. It shows actual LTX removal/replacement, exterior Relight and sphere controls, a native ComfyUI canvas, generated audio/video, and the Local/Cloud connection boundary. It passed full decoding and visual review. Demo and example archives are separate submission assets; they are not assumed to exist in a fresh source checkout.

Application code: [MIT](LICENSE). Model weights, upstream nodes and optional runtimes retain their own terms; see [third-party attribution](docs/THIRD_PARTY.md). No model weights, credentials or Higgsfield commercial demo footage are included in the source release.
