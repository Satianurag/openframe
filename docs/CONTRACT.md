# OpenFrame implementation contract

Scope: a video-generation and VFX studio matching Higgsfield's public UI structure and visual treatment. ComfyUI executes every generative backend. No user login/payments in this release. Durable jobs, media library, uploads, VFX masks, comparison, presets, workflow export, local/Modal/Comfy cloud connections. Do not fake successful generation or advertise unimplemented actions.

Stack: React + TypeScript + Vite frontend; FastAPI backend with SQLite persistence; Python engine calling real ComfyUI. Local single-user app, configurable remote compute. Python modules under backend/ and engine/; run from project root. Frontend dev proxy /api -> localhost:8000, built frontend served by FastAPI.

## API
GET /api/health -> {status,version}
GET /api/catalog -> {models:[{id,name,family,description,tasks:string[],aspect_ratios:string[],...}],effects:[{id,name,description,category,prompt,model_ids:string[],requires_video:boolean,requires_image:boolean,requires_mask:boolean,...}],providers:[{id,name,configured,available,detail}]}
GET /api/settings -> {default_provider,comfy_url,comfy_cloud_url,modal_app,...}; PATCH same. Never return API tokens. Optional secret provided on update should be saved server-side and redacted.
POST /api/providers/{id}/check -> {available,detail,models?:string[]}
POST /api/assets multipart file -> {id,name,kind,url,thumbnail_url,width,height,duration,fps,...}
GET /api/assets -> {items:[asset]}; GET /api/assets/{id}/file streams media; DELETE /api/assets/{id} removes only unreferenced user asset.
POST /api/jobs JSON -> job. Request: {model_id,effect_id,provider,prompt,negative_prompt,seed,width,height,frames,fps,steps,guidance,source_asset_id?,mask_asset_id?,reference_asset_id?,strength?,preserve_audio?,preserve_outside_mask?,mask_tracking?,...}
Job: {id,status:queued|running|succeeded|failed|cancelled,progress:0..1,stage,created_at,updated_at,request,outputs:[asset],error?,favorite:boolean}
GET /api/jobs -> {items:[job]}; GET /api/jobs/{id} -> job; POST /api/jobs/{id}/cancel -> job; POST /api/jobs/{id}/retry -> new job; PATCH /api/jobs/{id} {favorite:boolean}; DELETE /api/jobs/{id} only terminal job.
POST /api/workflows/export with same request -> JSON workflow download. GET /api/jobs/{id}/workflow -> graph JSON. GET /api/jobs/{id}/bundle -> downloadable reproducibility bundle if practical.
GET /api/presets -> {items:[]}; POST /api/presets {name,request} -> preset; DELETE /api/presets/{id}.

## Engine boundary (engine agent owns all engine/ and deploy/)
engine.catalog.get_catalog() -> dict with models/effects/providers metadata (backend augments provider configuration).
engine.workflows.build_workflow(request:dict, assets:dict|None=None) -> ComfyUI API graph dict. Assets values are uploaded Comfy filenames for source, mask, reference. Exports must include needed custom-node instructions.
engine.runner.run_job(request:dict, assets:dict, output_dir:Path, settings:dict, on_progress:Callable[[float,str],None], is_cancelled:Callable[[],bool]) -> dict {outputs:[{path:str,kind:str,...}],workflow:dict,metadata:dict}. assets maps source/mask/reference to local absolute paths. Synchronous worker function; backend runs in worker thread. Raise explicit exception on failure, cancellation distinguishable. Never synthetic success fallback.
engine.runner.check_provider(provider:str,settings:dict) -> dict {available:bool,detail:str,...}.

Frontend should get catalogue from API. It may keep visual effect descriptions client-side but use server IDs. Coordinate model/effect IDs with engine agent promptly. Baseline tasks: text-to-video, image-to-video, video inpaint/removal, video restyle; extend working capabilities only. Model profiles initially LTX and Wan VACE, final actual checkpoint choices engine-owned.

## Ownership and timing
frontend agent: frontend/**, docs/DIRECTION.md, artifacts/reference/**.
backend agent: backend/**, pyproject.toml, .env.example; coordinate dependencies with engine.
engine agent: engine/**, deploy/**, workflows/**, custom_nodes/**.
root: README, scripts, docs plan, integration and final validation.
Do not write/run tests or perform product QA until root announces full implementation complete. Reference inspection/screenshots, reading source/docs and provisioning dependencies are allowed. Do not overwrite another agent's files. Use shared directory; no extra worktrees.
