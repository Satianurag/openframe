# OpenFrame studio direction

## Brief
Build an open-source ComfyUI video/VFX product, closely reproducing the public Higgsfield studio layout and interaction language. The user explicitly requested the reference appearance; alternate concept explorations are therefore superseded. Focus on video generation, masked edits and reusable workflows. No login, billing or invented model results. Own OpenFrame identity; Higgsfield is a private research reference, not an affiliation.

## Captured reference
Public URLs: https://higgsfield.ai, /ai/video, /ai/video?model=genjutsu, /effects/use. Screenshots and measured DOM/style records under artifacts/reference/. Desktop 1440×1000, mobile 390×844, model/duration/ratio/quality/bitrate menus and preset picker. The public studio is accessible without login. No account access attempted.

Keep: charcoal #0f1113 canvas; lime #d1fe17 primary action; compact horizontal navigation; approximately 320px left controls; 20px stage panel radius; layered upload/prompt/control areas; tightly spaced uppercase scene headings; large image/video-led presets; model pickers and history context. Use the actual server model catalogue rather than displaying inaccessible paid models.

Adapt: OpenFrame branding; no signup, promotional discounts or price claims. Compute selection and ComfyUI export replace commercial account controls. Hero imagery must be original illustrations or actual OpenFrame GPU outputs; reference screenshots are not shipped as product media.

## Visual system
Inter UI is intentionally retained because the measured reference uses it; Space Grotesk700 matches the measured public headings. The earlier Barlow interpretation was corrected after full DOM/style inspection; its unused files were removed. Fallbacks are Arial/Helvetica. Ground #0f1113, panel #131517, control #222426, raised #292b2d, line #303234, text #f7f7f8, secondary #a2a5a8, action #d1fe17. Radius family: 5–8px utility controls, 10–12px inputs/cards, 18–20px major panels. Spacing: 4/8/12/16/24/32px.

Desktop shell: topbar + controls + stage. Mobile: full-width media stage, fixed compact nav, controls as a full-height sheet above navigation. Core actions stay reachable without horizontal page scrolling.

## Content and states
Main navigation Explore, Video, VFX, Library; Cloud link and compute settings. Stage Effects, History, How it works. Effects come from API with explicit workflow-preset semantics. All media in history comes from actual server job outputs. Illustrative catalogue cards are labeled style illustrations; no claims they are renders.

Controls: effect, source image/video, reference, painted mask, prompt, compatible model, duration, aspect ratio, resolution, FPS, seed, steps, guidance, negative prompt, source audio, preservation and SAM2/optical-flow/static tracking. Compute is distinct from model selection.

Empty: practical instructions and one creation/upload action. Loading: structure-matched skeleton. API error: persistent error with preserved draft. Offline: reconnect banner, browser-saved draft. Slow job: actual server progress, no invented ETA. Failed render: actual error, edit and retry. History/library filter empty: clear filter path. Delete confirmations for persisted media/jobs. Mask seed frame explicitly identified.

## Signature
The before/after slider reveals the original plate underneath the actual generated video. It shares playback timing and clearly labels original/generated. No marketing animation necessary. Render indicator uses a subtle 2.5s border pulse only while server reports running; reduced-motion removes it.

## Validation timing (historical implementation plan)
Reference capture is complete. Per user instruction, all product screenshots, build checks, interaction testing and cross-viewport validation are deferred until the parent announces full implementation complete. This document records design intent, not a verified visual match.

## Font delivery
Inter400/500/600/700 and Space Grotesk700 are self-hosted in frontend/public/fonts/. SIL Open Font License files and exact source URLs are included. No external font request is required.

## Strict reference revision
The authoritative audit is artifacts/reference/fidelity/: full public HTML, active popup DOM, computed styles and rectangles, and screenshots for create/edit, model/duration/aspect/quality/bitrate, preset picker, asset picker, History Filter/View/date, Draw entry, and mobile. Main source1440×1000 measurements:44px banner,36px nav,320px controls at x16/y90, main panel x344/y90,130px preset,168px upload,172px prompt,54px model/settings,48px Generate. Source heading40/48, Space Grotesk700, letter spacing−.04em. Right-anchored model/options and600px asset popover replace the earlier centered pickers.

Working content exceptions: OpenFrame branding and real ComfyUI compute controls replace login/pricing; only supported open models and workflow presets appear; FPS replaces the commercial bitrate selector; advanced settings replace unsupported Motion Control; job status filtering is a separately labelled section in the existing model-filter submenu. We do not show controls for unavailable proprietary capabilities. The public Higgsfield mobile Generate route displays “MOBILE ACCESS COMING SOON”; OpenFrame retains its working mobile composer. The public Draw entry was inspected without uploading third-party media or signing in; the functional mask editor implements our actual tracking workflow.

Original generated previews carry exact provenance under frontend/public/previews/. General shows actual LTXFast output; Remove Object shows the approved LTX2.3 API render9a44a1f19f0743569d5ba4c9adfd49b0 with its exact source and mask provenance; its preview metadata identifies that model even when the editable generation model differs. Cinematic, Weather and Product use clearly labelled illustrative LTX Fast generations, not transformation or reveal-motion proof. Restyle uses approved API job b4e93a0d70c04675b824cf79d2e6a12e: a warm painterly change, not precise watercolor-paper reproduction. The remaining cards are explicitly labelled workflow illustrations. Private Higgsfield reference media is not bundled.

Validation uses identical1440×1000 and390×844 reference viewports. Browser/emulated-platform matrices are not native Windows/Linux/iPhone certification; WebKit testing is not a claim of testing a physical Safari device. Final fidelity evidence must identify concrete geometry/content differences, not infer pixel identity from a generic design score.

Progress labels translate engine node names into plain user-facing stages; raw engine identifiers remain in API/workflow evidence. Comparison playback uses a shared time base with the selected trim offset, centered source cropping, and an aspect-preserving fullscreen surface.

The implementation-first gate has now been completed. Current validation evidence lives in artifacts/validation/frontend/final-interactions/, real-result/, recording/, round3/ and matrix-round3/. The initial design rounds are retained as history, not evidence that the later strict-reference revision was already verified.

The Replace Object preview now uses actual app render3e609d6da5484a24b1d9337e31c9f3b4, with smooth-inward contour feathering. All49frames were reviewed: periodic shadow stair steps are removed with slight boundary softness. Removal9a44a1f19f0743569d5ba4c9adfd49b0 remains the hero. The earlier UI replacement and removal interactions remain recorded in recording/events.json and actual-ui-full.webm; those recordings are historical execution evidence, not the new preview’s provenance.

## Component fidelity matrix

Measurements below use1440×1000; mobile references use390×844. Source HTML, popup DOM, computed styles, rectangles and state images are archived together in `artifacts/reference/fidelity/`. Corresponding implementation state captures are in `artifacts/validation/frontend/fidelity/` and the final `settled/` folder. This is measured layout fidelity, not a claim that the entire commercial product is pixel-identical.

| Component | Measured reference | Implemented match / explicit difference |
| --- | --- | --- |
| Shell |44px banner,36px nav; controls x16/y90/w320; stage x344/y90 | Same desktop geometry; own OpenFrame branding and compute links. |
| Create controls | Preset130px, upload168px, prompt172px | Same geometry; input requirements follow the selected actual model/task. |
| Main selectors | Model x25/y688/302×54; duration x25/y750/147×54; aspect x180/y750/147×54 | These rectangles matched independent review. Quality follows at y812; operational FPS replaces proprietary bitrate choice. |
| Generate | x25/y874/302×48; lime#d1fe17;12px radius | Same placement and styling; submits an actual persisted API job. |
| Typography | Inter UI; Space Grotesk700 headings40/48 with−.04em tracking | Self-hosted matching families; nested selector values verified at weight500. |
| Model menu |402px right-anchored menu with search | Matching placement, surface and search; only actual compatible open models appear, so menu height/options differ. |
| Duration / aspect / quality | Rounded anchored menus; duration uses24px gray track and rectangular tick thumb | Matching control treatment; model frame/dimension grids determine valid values. |
| Media picker |600px popup beside controls | Matching placement and tabs; real uploads/library items, no commercial account assets. |
| Preset browser | Right-pane cards instead of centered modal | Matching card and search structure; original outputs carry visible model/provenance badges. Illustrative T2V samples are distinguished from actual transformations. |
| Edit tools | Full-height left rail; inner example card ends at y770 | Matching rail and quiet lower stage; unsupported proprietary tools are omitted. |
| Draw entry |1280×880 modal at x80/y60;425×250 preview;207×48 upload action | Matching composition using owned media. Actual brush/erase/rectangle/undo and tracked-mask controls extend the public entry state. |
| History Filter / View |220px Filter,188px View;32px card-size track;1×6px ticks; diagonal fill arrows | Main popup shape restored. Separately labelled Job status lives in the Models submenu. Calendar uses inclusive local dates. |
| Mobile |52px banner,44px nav, stage x16/y106/w358 and three-column help composition | Matching public layout. Working mobile composer is intentional: the source instead displays a coming-soon message. Desktop close control remains hidden after resizing from mobile. |
| Results / comparison | Public authenticated result state unavailable within requested no-login scope | Functional original UI: actual output/source, synchronized playback/seek/speed/fullscreen, result/mask/workflow/canvas/project downloads. No fake History results. |

## Final validation ledger

- `final-interactions/results.json`:19 input, selection, mask, preset, settings, history and mobile checks; no unintended generation POSTs or browser errors.
- `real-result/results.json`:8 checks of actual output metadata, comparison20/50/80, playback/seek/speed, fullscreen geometry, downloads, mobile controls and exact recipe reuse.
- `recording/events.json` and `actual-ui-full.webm`: real UI replacement and removal submissions, progress, completion, comparison and exports. Waits are real in the raw165s recording; any condensed demo must label accelerated/cut waiting.
- `round3/scan.json`: four viewport scans. `matrix-round3/` plus its targeted `only-l10n/` rerun: browser/emulated platform, high-contrast, reduced-motion,320px reflow and expanded-string checks. Firefox was unavailable and is explicitly skipped.
- `preview-role-proof.json`: each bundled MP4 matched byte-for-byte to its actual API output with role=result; mask outputs are excluded from gallery promotion.
- `fidelity/comfy-final-removal-import-proof.json`: final44-node/71-link graph imported in a private unsaved ComfyUI context, without local execution. Missing local model files are recorded separately; actual GPU execution occurred on Modal.

Remaining differences are the deliberate content/capability exceptions in the table, unavailable native-device/Firefox coverage, and the documented model-output limitations. Reference screenshots remain private validation material and are not shipped as product media.

`pagination-proof.json` adds four isolated helper checks for500-item server limits, offsets, uniqueness and total-bounded loads. No mock rows were inserted into the API or displayed in History. The final controlled replacement recording is in `recording-shadow-margin/`; its exact provided JSON initialized a separate browser draft before the actual Generate click, without inventing an import UI or resampling the mask.
