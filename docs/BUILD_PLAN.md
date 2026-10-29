# OpenFrame build plan

## Product
A video and VFX studio matching the public Higgsfield editor's layout and controls, without a login requirement. ComfyUI executes actual inference. LTX is the default VFX model for the competition bonus; other supported profiles are selectable. Local, Modal and configured Comfy API deployments share the same product controls. Branding, model choices, original media and the working mobile composer are documented differences from the reference.

## Completion checklist
- [x] Public reference screenshots of navigation, effect discovery, video studio, input controls, selectors and accessible responsive states.
- [x] Video generation studio: real catalogue, presets, prompt/negative prompt, model and compute selection, valid dimensions/frame count/seed/steps.
- [x] Image/video uploads, source preview, mask painting and editable mask controls.
- [x] Real LTX VFX inference and a second selectable model family.
- [x] Frame/mask alignment, temporal mask tracking, preservation/composite and audio policy.
- [x] Durable job queue with progress, actionable failures, cancellation, retry and recovery.
- [x] Library, history, favorites, saved recipes, before/after view, download.
- [x] ComfyUI graph export and reproducibility bundle with source/model/node metadata.
- [x] Working Comfy API transport and Modal worker; hosted Comfy Cloud execution verified through CLI OAuth with explicit local processing.
- [x] Installation, license, dependency attribution, model requirements and competition demo guide.
- [x] Initial implementation completed before tests and extensive product QA began.
- [x] Final integration checks after corrections, two-stage LTX GPU VFX, and output inspection.
- [x] Component screenshots and responsive/accessibility review; repair issues and recheck.
- [x] Prepare the final source package, reproducible VFX examples and verified demonstration evidence.

Validation evidence must distinguish implemented, exercised and not verified. Unsupported remote configurations must fail truthfully. No simulated completion, fake users, fake metrics, stock testimonials or unimplemented toolbar actions.

## Work ownership
Frontend agent: reference capture and application UI.
Backend agent: durable service, media/jobs/presets/settings/API.
Engine agent: Comfy graphs, model profiles, custom nodes and Modal worker.
Root: integration, documentation, coverage tracking, release artifacts and verification coordination.

## Competition fit
The entry must run on ComfyUI; LTX must be core to the demonstrated VFX workflow. Ship open-source application code with local setup instructions and inspectable workflows. Prepare a <=2 minute demonstration and source links. External registration, public posting and submission require the user's explicit action/authorization; preparation is in scope.

Source: https://comfy.org/open-source-higgsfield/ (reviewed 2026-10-29).
