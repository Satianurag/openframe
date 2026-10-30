# OpenFrame frontend

React, TypeScript and Vite. API requests are relative to `/api`; Vite uses `OPENFRAME_API_URL` (default `http://127.0.0.1:8000`) for its FastAPI proxy. The root development launcher selects free ports and configures this automatically. The production build is served by the backend.

```sh
npm ci
npm run dev
npm run build
```

## Source layout

- `App.tsx`: studio state, API actions, input controls and navigation.
- `StudioPanels.tsx`: effects catalogue, history, media library and help views.
- `MaskEditor.tsx`: source-frame selection painting and PNG mask export.
- `JobResult.tsx`: video player, synchronized before/after comparison, output downloads.
- `SettingsPanel.tsx`: compute configuration and connection checks.
- `SceneArt.tsx`, `previews.ts`: original illustrative effect cards and verified-media registry.
- `ui.tsx`, `Icon.tsx`: shared small presentation components.
- `api.ts`, `types.ts`: typed HTTP boundary.
- `styles.css`, `reference.css`: shared styles plus measured reference geometry.
- `Popovers.tsx`, `HistoryToolbar.tsx`: anchored controls and history filtering/view preferences.

Formatting: `npx prettier --write src`. No external UI library or analytics is used. React, Vite and TypeScript are pinned in the lockfile. Inter and Space Grotesk are self-hosted under `public/fonts/` with their SIL Open Font Licenses and source ledger. No external font request is required; system fallbacks remain available.

## Adding a model or effect

The server catalogue is authoritative. Add the supported capability to the engine, with truthful task, input and grid constraints. The UI filters compatible models by each effect's `model_ids` and renders inputs from requirements. Optional reference controls require `supports_reference` and a compatible `reference_tasks` entry; source-image support is conveyed separately through tasks.

Release connections are local ComfyUI and Comfy Cloud, with local ComfyUI as the fresh default. Provider visibility and `model.enabled_providers` come from the server. A saved recipe using a disabled connection remains identifiable and requires an explicit compatible selection; it is never silently rerouted. Hosted Cloud supports only the declared model/task subset and retains the documented CPU preparation/compositing boundary.

For LTX VFX, hosted2.5 is restricted to masked inpainting (Remove/Replace). Its native Cloud graph returns video, with app-side source/mask preparation and any selected extra finishing. The existing2.3 path uses local CPU finishing from Cloud-generated frames. Hosted2.5 source/schema/portable-graph checks are not an account-specific live execution claim. Water and Sphere Relight remain local ComfyUI operations in the public configuration.

Sphere Relight is exterior-only and follows its fixed1280×704/24fps single-stage recipe. The browser prepares an actual PNG lighting sphere; angle changes invalidate that image until Apply. The image and scalar controls are preserved on reuse, with no hidden caption rewrite. Source audio retains the selected recording, generated audio creates new sound only on supported editing paths, and Silent omits it. Water and Sphere Relight offer source/silent only. Water's reviewed49-frame comparison retained the overall McLaren silhouette and arm motion with visible rain/wet surfaces, but small-detail and parking-line drift remained; exact preservation is not guaranteed.

Full project exports for hosted jobs include both the local replay recipe and actual Cloud graph, prepared inputs and processing provenance. The isolated Cloud graph does not reproduce app-side preparation or finishing. Portable local replay still requires the declared weights and node dependencies; credentials are not bundled. The lazy sphere renderer and its MIT/Three.js licenses are explicitly included in the source release selection.

Register original, verified preview images in `src/previews.ts`. Until registered, effects use authored scene illustrations. Never ship Higgsfield reference screenshots as product assets or label illustrations as generated results.

## Interaction contract

- Uploads and completed outputs are real server media; no mock success path.
- Draft settings are debounced into browser localStorage; keys never enter that store.
- Active jobs poll every two seconds. Jobs, presets and media persist on the server.
- The mask seeds the first frame of the chosen trim. Other frames can be inspected but painting is locked to the seed frame.
- Model-specific frame and dimension grids are respected in controls; the server remains authoritative.
- Source-video duration is checked and trim warnings remain visible with the result.
- Full project ZIP downloads use a direct streaming link rather than buffering large media in browser memory.
- `Cmd/Ctrl+Enter`: generate. `Cmd/Ctrl+K`: choose model.
- Mobile controls use a dedicated sheet; the media stage remains full width.

## Visual provenance

The interface's reference/design decisions are described in `../docs/DIRECTION.md` and `../docs/DESIGN.md`. OpenFrame uses its own branding and labels illustrative previews separately from generated results. Reference screenshots are not shipped as product output.

The application can load the checked-in public reference URL inventory when no optional media cache exists. Remote previews require network access. Current output/control limits are summarized in `../docs/DESKTOP-VALIDATION.md`; browser emulation is not native-device certification.
