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

See `../docs/DIRECTION.md` and `../artifacts/reference/`. Only public Higgsfield pages were inspected; no logged-in access. Own OpenFrame branding replaces the reference brand. Implementation was completed before validation began. Evidence is under `../artifacts/validation/frontend/`: `final-interactions/results.json` records19 interaction checks, `real-result/results.json` records8 actual-result/playback/export/reuse checks, and `recording/` contains real UI→API→GPU runs with raw video and timing events. Final screenshot and browser/emulation reports live in `round3/`, `matrix-round3/` and `fidelity/`; read their reports for remaining limitations rather than assuming native-device certification.
