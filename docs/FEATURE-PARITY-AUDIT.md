# Desktop image / video / VFX feature parity audit

Date: 29 October 2026. **Full feature parity is not implemented.** This is a read-only comparison of saved, user-authorized Higgsfield reference captures with the current source. No new product tests, inference, model benchmarks or mobile checks were run for this audit. The most recent Talking Portrait and planner-status changes are source-complete but their pending checks were stopped when the user changed the work order.

## Meaning of the statuses

- **Implemented**: the named control has a real persistence / transformation / job / export path in source. This does not certify output quality, every provider, or exact proprietary behavior.
- **Partial**: some UI or execution exists, but a material part of the reference behavior is absent, reduced, or replaced by prompt guidance.
- **Missing**: a relevant captured feature or launcher has no corresponding complete control and operation.
- **Unsupported**: the current architecture / models / integrations do not supply the capability; a label, placeholder or different operation would not satisfy it.

A saved screenshot proves a visible control, not its hidden implementation. Where only the supplied HTML or a launcher title describes a feature, the precise behavior still needs inspection. Those uncertainties are called out rather than filled with guessed requirements. Earlier successful renders establish individual execution examples; they do not establish feature parity. Existing validation evidence remains in `docs/VALIDATION.md` and the retained review record and is not extended by this audit.

Scope includes desktop still-image generation/editing, video generation/editing/VFX, characters, motion, product/advertising media, storyboards, and speech-conditioned **video**. Mobile, Canvas, a general-purpose Supercomputer agent, standalone audio/TTS products, web games, accounts, subscription billing and fake credits are excluded by the user's instructions. Audio used as a video input, narration or soundtrack remains relevant. A game-themed image effect is not automatically excluded merely because its category says “Games”.

## Reference and code keys

The audit is a baseline snapshot; newly assigned implementations are not counted until their source contracts are complete. Reference paths below are relative to the repository. The captures are private research evidence, not public product output.

| Key | Saved reference evidence |
|---|---|
| V | the retained review record: `create-clean.json`, `create-model-components.html`, `create-duration-components.html`, `create-ratio-components.html`, `create-quality-components.html`, `create-bitrate-components.html`, `reference-upload-components.html`, `prompt-elements-components.html` |
| E | Same folder: `editing-tools-clean.json`, `edit-workflow.json`, `edit-draw-empty.json`, `edit-workflow-model-components.html`, `edit-workflow-quality-components.html`, `edit-workflow-bitrate-components.html` |
| FX | Same folder: `effects-base.json`, `effects-change-components.html`, `effects-aspect-ratio-components.html`, `effects-resolution-components.html`, `preset-picker.html` |
| H | Same folder: `history-base.json`, `history-filter-components.html`, `filter-all-models-components.html`, `filter-date-range-components.html`, `history-view-components.html` |
| CF | the retained review record |
| C | Same folder: `cinema-{default,film-genre,film-era,film-tempo,camera-setup,camera-movement}`; `firefox-cinema-{lighting-settled,lighting-editor,light-color,color-palette,palette-editor,palette-wheel}`; full lighting/palette DOM files |
| I | Same folder: `firefox-influencer-{create,all-attributes,gender,age,ethnicity,skin-color,head-shape,eye-shape,eye-color,hairstyle,hair-color,facial-hair,neck,build,height,proportions,distinctive-features,accessories,style,motion,motion-models,motion-quality,object-swap-prompt,assets-picker}`; `codex-influencer-{style-dialog-settled,custom-style}` |
| M | Same folder: `firefox-marketing-{default,sidebar,styles,ad-styles,marketplace-styles,ugc-styles,motion-styles,tiktok-styles,tiktok-form,ad-reference,product-link,product-manual,product-picker,duration,aspect}` and corresponding DOM captures |
| S | Same folder: `codex-soul-{default,presets}.{jpg,txt}` and DOM; source HTML's `panel-soul` / identity descriptions |
| IMG | Same folder: `codex-image-{default,aspect,elements}`; `codex-image-current-model-catalog.{jpg,txt}`, `codex-image-current-draft.json`, `codex-image-flux3-{controls,resolution,ratios}` and DOM |
| P | Same folder: `codex-popcorn-{auto,manual,count,ratio,instadump-settled,instadump-upload}` and DOM |
| G | Same folder: `codex-genjutsu-{default,styles,custom,object-swap,models,quality,selected-style,source-picker-settled}` and DOM |
| K | Same folder: `firefox-katana-{default,instructions,how-it-works,recreate,preset-detail,publish-dialog,publish-settings}`; `codex-katana-preset-detail` and DOM |
| A | Same folder: `codex-apps-default.{jpg,txt}`, `codex-app-background-remover.*`; `docs/reference-mini-apps.json` |
| R | User's the retained review record. Research descriptions are not direct proof of all live behavior. |

Code keys: **Studio** = `frontend/src/App.tsx`; **Mask** = `MaskEditor.tsx`; **Result** = `JobResult.tsx`; **History** = `HistoryToolbar.tsx`; **Shared** = `apps/engine-apps-shared.tsx`; **Docs** = `apps/useAppDocument.ts` + `backend/apps.py`; **Sequence** = `apps/SequencePlanner.tsx` + `backend/sequences.py`; **Engine** = `engine/catalog.py`, `engine/workflows.py`, `engine/image_workflows.py`, `engine/character_workflows.py`, `engine/runner.py`, `custom_nodes/openframe/`. Paths without `frontend/src/` below are inside `frontend/src/apps/` unless stated otherwise.

## Common desktop controls and execution

| Feature/control | Status | Current code / operation and exact boundary | Evidence |
|---|---|---|---|
| Separate page layouts and routes | Implemented | `SuiteApp.tsx`, `registry.ts`: CF, Cinema, Image Studio, Characters, Influencer, Marketing, Katana, Genjutsu, Popcorn and MiniApps; old VFX studio at `/studio/vfx`. No claim all source navigation destinations exist. | V, CF–A |
| App switcher and cross-app navigation | Implemented | `AppSwitcher.tsx`, `SuiteApp.tsx`; actual routes. Cross-app media handoff is implemented in selected flows, not a universal asset/action bus. | C, S, P |
| Saved drafts / reopen / revision conflict protection | Implemented | Docs: persisted JSON state, explicit asset references, compare-and-swap revisions and immutable submitted document snapshots. | C, M, R |
| Uploads, generated outputs and file selection | Implemented | Shared `AssetPicker`, backend asset endpoints; actual image/video/audio files, pagination, generated-role filtering. | V, G, I, M |
| Asset folders, global tagged collections, collaborative asset workspace | Missing | Flat workspace assets plus app documents are not the source's complete Assets workspace. Only its entry/link is captured. | V, G, S headers |
| Public reference previews and explicit import | Implemented | `referenceLibrary.ts`, Shared; optional local cache or lazy public-URL inventory; imported media becomes a real asset. Reference previews are labelled, not counted as own outputs. | CF, G, I, M, A |
| Live community/trending ranking and newly published feed | Unsupported | Cached captured examples / local ordering / local likes only. No source community backend or live trend ranking. | G, C, K, CF |
| Local ComfyUI / Comfy Cloud selection | Partial | `SettingsPanel.tsx`, provider checks and engine adapters are real. Hosted Cloud supports the existing hybrid subset; all new image/motion/S2V operations are not supported there. | Own required portability; R |
| Full proprietary model menu | Unsupported | Real catalog exposes installed open profiles. Source Seedance/Kling/Genjutsu/Gemini/other vendor choices are not implemented simply by matching their menu names. | V model menu, G models |
| Queue, progress, cancel, retry and errors | Implemented | Studio/Shared/Docs + worker; genuine job status. Retry is explicit. Backend failure remains visible. | H, R |
| Scoped app history and result playback | Implemented | Docs + Shared `WorkspaceHistory` / `ResultDialog`. Not all apps reproduce every source history filter/control. | H, CF, G |
| Favorites / liked outputs | Implemented | Job favorite API and history/picker filters. These are local workspace favorites, not community likes. | H, G, C |
| History model/date/status filters | Partial | Full filter/date controls exist in Studio History. Most separate-app history panels expose basic history/favorites, not the entire filter menu. | H |
| History list/grid/masonry, fill and card size | Partial | `HistoryToolbar.tsx` and Studio implement these; Shared app history uses its own fixed layout. | H |
| Original result download | Implemented | Real asset URLs; image/video/audio result types rendered appropriately. | H, R |
| API workflow, editable Comfy graph and full project export | Partial | API graph and media bundle exist; native runs can export editable UI graph. Hybrid Cloud has native cloud graph + local processing evidence, not one complete editable canvas. Multi-shot sequence has no aggregate portable ZIP. | Own portability requirement |
| Exact reuse from immutable submitted settings | Partial | Studio and several app ResultDialog callbacks use app-context snapshots. MiniApps currently has result/history/export but no dedicated reuse callback. | H, R |
| Public publishing/share page/community preset publication | Unsupported | Local downloads/preset JSON are present; no source community publishing backend or hosted share pages. | K, C |

## Video Studio / editing tools / VFX

| Feature/control | Status | Code / operation and remaining work | Evidence |
|---|---|---|---|
| Text-to-video prompt and image-to-video source | Implemented | Studio + model-specific T2V/I2V graphs. | V |
| Prompt reference uploads / Elements | Partial | Source and supported optional image reference are consumed. No general named Elements registry resolving many objects/locations/characters in a prompt. | V, E, FX |
| Model search and selection | Partial | Real compatible catalog/search exists. Source's complete provider families and proprietary modes are unsupported. | V, G |
| Duration and frame count | Implemented | Model-aligned frame validation, source interval bounds and explicit fitting. Actual duration displayed rather than silent source padding. | V |
| Aspect ratio and quality | Implemented | Dimensions align to selected profile. Source 4K and other advertised limits are not universally available. | V, E, FX |
| Bitrate High / Standard | Implemented | Source now provides encoding_quality in Studio, utility and sequence controls; HDR HEVC exposes bitrate, while ProRes uses fixed422HQ. NativeVideoTools.tsx / SequencePlanner.tsx / engine graphs. No new runtime validation. | V, E |
| Source start / trim | Implemented | Source selected interval and matching mask frame used by native/Cloud processing. | Own necessary VFX control |
| Prompt-targeted video edit | Implemented | Masked LTX IC-LoRA / Wan VACE and full-frame restyle paths. | E |
| Draw to Edit: source preview, brush, erase, rectangle, clear, undo, brush size, overlay, save | Implemented | Mask component creates actual PNG masks; job consumes them. | E Draw |
| Draw to Video | Missing | Source dialog has a separate mode; no corresponding sketch-conditioned video operation. | E `edit-draw-empty.json` |
| Temporal mask tracking / preview | Implemented | SAM2, optical flow, static; tracked mask export, edit margin and feather support. Cloud SAM2 requires compatible local Comfy bridge. | Own VFX operation; E |
| Remove / replace selected objects with plate preservation | Implemented | Actual mask-conditioned generation and compositing; source/mask coverage remains consequential. | E |
| Extra replacement reference | Partial | Wan supports reference input; LTX masked edit is text-directed. Unsupported combinations reject rather than ignore the reference. | E, FX |
| Before/after comparison | Implemented | Result divider, source trim offset, matching crop and media playback. | Own result QA requirement |
| Saved effect presets / recipe export | Implemented | Studio and local preset endpoints. A prompt preset is not an independently trained effect. | FX |
| Extended effect catalog, effect ordering/chaining | Partial | Current effect list is a bounded set; source “Change” and “Reorder effect” imply a broader catalog/ordering flow not represented by one selected preset. | FX |
| Separate Character / Location / Products slots | Missing | No equivalent three-role reference binding and ordered multi-effect execution; one generic reference is insufficient. | FX Floating Fall |
| Extend Video / continuation | Implemented | NativeVideoTools.tsx exposes real LTX2.5 context-conditioned sequel/prequel, source interval, context/output frames and audio. Output contains selected context plus new footage, not the entire original; narrower than vendor30s/50-reference limits. | V, E |
| Reframe: resize and reposition for output format | Partial | VideoUtilities.tsx provides CPU crop/pad; NativeVideoTools.tsx separately provides generative outpaint with target canvas/source scale/anchors. No four-side reference conditioning or tracked framing trajectory. | E |
| Upscale existing video | Implemented | Dedicated NativeVideoTools.tsx uses actual LTX2.5 Pixel2× or tiled-refinement adapters and native bounds. Proprietary Topaz/ByteDance model names and their8K/600s promises are not reproduced. | E |
| Remove video background / transparent cutout | Implemented | Separate automatic LTX AlphaGen and prompted SAM3.1→trimap→ViTMatte paths. Real cutoutWebM/mask outputs; source dimensions/audio, concept/confidence/trimap controls. Quality/access remain unverified this revision. | E |
| SDR to HDR | Implemented | Dedicated HDR form and native adapter; HEVC10HLG, ProRes422HQ10HLG, opt-in bounded EXR16ZIP, separate SDR browser preview and actual master download. No new runtime validation. | E |
| FPS Boost / frame interpolation | Implemented | FrameTools.tsx / LDF-VFI actual interpolation, native source geometry, explicit interval/targetFPS/seed. ≤241inputframes,≤120fps/16×; final timestamp duration differs slightly from input. Not retiming. | E |
| Depth Map from media | Implemented | FrameTools.tsx provides model selection, relative-depth grayscale/Turbo/Inferno/Magma/Viridis preview, side-by-side, resolution/maxframes, raw16-bit FFV1 download. ≤300frames/1280longside, not vendor1800frames/1080p. ViGeo is explicitly noncommercial. | E |
| Tutorial / How it works | Implemented | Local instructional states describe current operations. They do not reproduce proprietary tutorial outcomes. | V, E, FX |

## Content Factory

Code: `ContentFactory.tsx`, Sequence, `engine/planner.py`.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Explore / My generations tabs | Implemented | Captured style gallery and actual sequence outputs/history. | CF |
| Generate here | Partial | Opens editable planning / explicit sequence execution. Does not yet produce the complete reference-led narrated/captioned short-video package automatically. | CF, R |
| Generate in Claude | Unsupported | A capability explanation is shown. No Claude MCP installation, conversation handoff or tool execution bridge. | CF |
| Brief textbox | Implemented | Saved and sent to the real CPU planner / explicit shot requests. | CF |
| Length15–300 seconds, five-second steps | Implemented | Saved target duration; measured assembled duration is separate. | CF length |
| Episodes1–4 | Implemented | Separate explicit episode plans and actual per-episode assembly. | CF episodes |
| Trending style selection / preview / sound toggle | Partial | Preview playback and selection exist; style name becomes planning guidance. No hidden original style recipe or automated visual analysis is reproduced. | CF |
| Add reference URL | Partial | URL can be stored/displayed, but user must remove it before planning/rendering; no social-reference retrieval/analysis path. | CF link |
| Add image/video reference | Partial | Files are real assets. Image can seed first-shot I2V; video is not automatically analyzed into a style/story plan. | CF reference |
| Additional attachments | Partial | Persisted/protected assets; the text planner does not see their pixels or audio. A saved attachment is not semantic conditioning. | CF |
| Automatic shot/story proposal | Implemented | Real Qwen CPU JSON proposal, persisted independently and explicitly reviewed. Current default/name/budget comes from backend. | R; Sequence |
| Editable shot order, description, camera text, model, source, frames/FPS | Implemented | Sequence editor submits individual actual requests. | R |
| Reference-video pacing/style/story extraction | Partial | Root added real sampled-frame/cut evidence analysis to the planner, editable observations and provenance. No audio understanding or reconstruction of hidden proprietary workflows. | CF, R |
| Narration generation and automatic synchronization | Implemented | SequencePlanner/backend narration source now supports per-shot TTS and alignment, actual waveform jobs, mix controls and measured assembly. Validation pending; source-complete is not output-quality proof. | R; Sequence narration UI |
| Subtitle transcription / captions / timing / typography | Implemented | SequencePlanner now contains narration/soundtrack/manual caption sources, editable timed cues and burn-in/export controls. Current source requires final end-to-end validation. | R |
| Background music and sound design selection | Partial | Existing audio asset can be attached/cropped; no music library/generation/mixing envelope or automatic sound-design plan. | R |
| Explicit sequential render, prior-frame continuity, failure recovery | Implemented | Durable sequence jobs, cancel/resume/retry and completed-shot retention. | R; Sequence |
| Transitions, beat alignment and timeline editing | Missing | Assembly currently concatenates compatible outputs. | R |
| Final per-episode video / individual shot exports | Implemented | Real FFmpeg assembly and output assets; no aggregate sequence ZIP. | R |

## Cinema Studio

Code: `CinemaStudio.tsx`, `CinemaCreativeEditors.tsx`, `cinema-reference.json`, Sequence.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Collapsible sidebar; Home / projects; new / search / order projects | Implemented | Separate persisted Cinema documents. | C |
| My elements | Partial | Shows workspace assets; no fully named, role-bound reusable cinematic Elements system. | C |
| My favorites | Implemented | Actual favorite jobs. | C |
| Community | Partial | Captured examples only; no live community project duplication/publication. | C |
| Image / Video tabs | Implemented | Real Klein image or LTX/Wan video requests. | C |
| Prompt textbox | Implemented | Saved and used in the submitted graph. | C |
| Reference gallery/upload and reference count | Partial | Images are consumed, but maximum is four total for Klein and one source for current Cinema I2V, versus source UI's0/50 reference slot. | C |
| Film Genre / Era / Tempo / Reset | Partial | All saved selector groups contribute prompt text. No separate film-scene planning engine or proof of equivalent learned control. | C |
| Camera Body / Lens / Aperture / Reset | Partial | Saved look/depth-of-field guidance goes into prompt. No explicit physical camera/lens model. | C |
| Movement gallery / search / order / prompt insertion | Partial | Choices append camera instructions/#tokens; no explicit per-frame camera-path conditioning or motion curve. | C movement |
| Palette presets / reset / new palette | Partial | Real editable palette data; inference receives palette words/HEX guidance, not a dedicated palette-transfer operation. | C palette |
| Palette HEX/HSV, harmony modes, add/remove swatches, randomize, name/save | Implemented | Actual local editor values and saved presets. Their downstream visual enforcement remains partial. | C palette editor/wheel |
| Palette from image | Implemented | Extracts colors from the selected asset and stores its reference. Not semantic look analysis. | C palette editor |
| Lighting preset grid / reset | Partial | Saved lighting choice becomes a prompt description. | C lighting |
| Custom light tabs / Add Light / position cube/orbit / six directions | Partial | Editor state exists and affects prompt descriptions; no scene geometry/light transport control. | C lighting editor |
| Light HEX/HSV, brightness, diffusion, apply/save | Partial | Values persist and become textual instructions, not deterministic relighting. | C light color/editor |
| Model / resolution / aspect / duration / native audio | Implemented | Actual supported profile parameters; source vendor/model/resolution menu is not fully reproduced. | C |
| Variant count | Implemented | Image batches or separately attributed video jobs. | C |
| Result playback, favorites, reuse, export | Implemented | Real results / immutable request context. | C, R |
| Multi-shot plan and episode assembly | Implemented | Explicit Sequence editor. Not a full cinematic timeline. | R |
| Shot extension before/after, transitions, arbitrary timeline rearrangement | Missing | No temporal extension or nonlinear video editor. | R |
| Cast roles bound to named scene entities across shots | Missing | Reference selection alone is not a role-binding/consistent-cast orchestration system. | R |

## General Image composer: newly captured controls

These captures arrived during this audit. They resolve the previous general-model/ratio evidence gap. The FLUX3 source profile and its controls have since been implemented. The updated rows below count source wiring only, not pending inference quality or provider validation.

| Feature/control | Status | Current behavior / required change | Evidence |
|---|---|---|---|
| General Image model catalog / search | Partial | Image Studio exposes actual open profiles. Captured vendor names are metadata, not an implementation target fulfilled by menu duplication. | IMG current catalog |
| Automatic best-model selection | Partial | SoulImage.tsx transparently selects by task, reference count, layout/preservation, adapter, size and provider. It does not claim learned prompt-quality ranking or parity with proprietary Auto. | IMG catalog |
| Aspect Auto plus ten explicit ratios | Implemented | SoulImage.tsx derives Auto from source or square and reads model aspect ratios, including the captured FLUX3 ratio menu. Native-grid dimensions are displayed and validated. | IMG FLUX ratios |
| Resolution768p/1K/1.5K/2K/4K | Implemented | SoulImage.tsx uses model resolution_presets including768/1024/1536/2048/4096 longest side for FLUX3; dimensions remain within actual model bounds. | IMG FLUX resolution |
| Separate generation quality and resolution | Partial | Source GPT-image composer has High quality and2K resolution separately. Current quality controls chiefly select output size; quality profiles must map to actual consumed steps/model settings. | IMG default |
| Image variants1–4 | Implemented | Real image batches / output records. | IMG |
| References with model-specific capacity | Implemented | Model-driven max_references; FLUX3 accepts10 total including source, with per-referenceMP and16MP combined cap. LegacyKlein remains4. Unsupported combinations reject. | IMG; backend work in progress |
| Prompt enhancement and original/enhanced prompt provenance | Implemented | FLUX3 expand or explicit full-caption mode, actual metadata.original/expanded/model_prompt provenance, no raw-prompt fallback. SoulImage.tsx / ImagePromptDetails.tsx. | IMG current draft |
| Elements picker: Uploads / AI Influencer / Elements / Generations / Liked | Partial | Uploads/results/likes and separate reference-set handoff exist; no complete integrated Elements registry/picker. | IMG elements |
| My Elements: All / Characters / Locations / Props; search/filter/New element | Missing | Character reference documents are one subset; locations/props, typed roles and New element creation/prompt binding are absent. | IMG elements |
| Dedicated image face swap / character swap modes | Partial | Current generic character edit exists; native face alignment/swap and complete separate model modes are absent. | IMG catalog |
| SVG generation / image vectorization | Missing | Source Ideogram Vector explicitly exposes vector output; current outputs are raster. A raster image with a vector-like style does not fulfill this operation. | IMG catalog |
| Consistent reference-style generation | Partial | Multi-reference image editing exists; there is no separate style-only conditioning guarantee or style/subject disentanglement enforcement. | IMG Recraft Styles description |

## Image Studio / Characters

Code: `SoulImage.tsx`, `SoulIdentity.tsx`, `root-apps.css`; actual image operation is Klein, not proprietary Soul.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Image prompt, model menu, generate | Implemented | Actual T2I or image-edit graph; native proprietary source model choices unsupported. | S |
| Reference images / remove / character selection | Implemented | Up to four consumed reference images; saved character-set selection. | S |
| Aspect / resolution / seed /1–4 variants | Implemented | Actual image request parameters and batch outputs. | S |
| Style gallery, search, selected style tile | Partial | Captured previews and style-name prompt guidance; original hidden style recipe is not reproduced. | S |
| Color Transfer | Missing | Visible in the current source Image composer; no corresponding dedicated color-transfer control/operation in Image Studio. Cinema palette text is not this feature. | S default |
| Source “Off” toggle beside quality | Missing / behavior unconfirmed | Control is captured but its opened menu/function was not captured. Do not guess whether this is enhancement, safety, or another model option. | S default |
| Photo series / photodump editable scenes | Partial | Four explicit scene image jobs exist. No automatic photo-pack recipe recreation, layout or identity consistency mechanism beyond shared references. | R |
| Moodboard collection / analysis / style conditioning | Missing | No dedicated moodboard workflow. The product is correctly named Image Studio rather than claiming a moodboard app. | R |
| Image history, result export, edit-result handoff | Partial | Real job outputs/downloads and edit-image handoff exist. Full immutable request reuse is not yet wired in Image Studio; storyboard animation handoff exists in Popcorn. | S, P |
| Character name / image collection / save / reopen / export | Implemented | Persistent reference sets, max four; protected asset references. | R |
| Character sheet generation | Partial | Prompt-guided multi-reference image generation, not structured verified multi-view reconstruction or an automatically parsed sheet. | R |
| Character→Image Studio handoff | Implemented | New image draft with selected reference set; existing saved image draft remains intact. | R |
| Soul ID dataset validation /20+photo training / identity adapter weights | Implemented | CharacterTraining.tsx and registry API provide20–50 unique photos, configured Local CUDA training/progress/cancel/retry-from-base, manifests and ready-adapter handoff. SoulImage selects matching FLUX3Base+strength; workflow inserts trigger. Not guaranteed identity or checkpoint resume. | R; execution verified, trained-only likeness fails |
| Cast backstory / structured persona generation | Missing | No structured textual character-generation pipeline. | R |
| General image edit / layers page | Implemented | Dedicated ImageLayers.tsx uses native Qwen-Image-Layered outputs; LayerEditor.tsx controls actual RGBA layer visibility/order/opacity/transforms/color, PNG and edit-recipe exports. Not Breakdown shopping analysis. | S/G headers |
| Image mask editing, local inpaint, erase/insert, outpaint | Partial | SoulImage/ImageRegionEditor provide FLUX3 spatial instructions plus source-native exact protected-pixel compositing. ExpandImage supplies padded canvas/protected original. Boxes guide generation; this is not a native masked-diffusion or semantic paint guarantee. | A Expand/paint; R |

## AI Influencer

Code: `AIInfluencer.tsx`, `motionRequest.ts`, Shared; metadata in `docs/reference-engine-apps.json`.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Create character / motion workspace | Implemented | Distinct character editor and motion input controls, actual jobs. | I |
| Gender / age / ethnicity / skin tone | Partial | Real saved selectors → Klein prompt; not guaranteed attribute disentanglement or a trained avatar. | I corresponding captures |
| Head shape / eye shape / eye color | Partial | Same prompt-directed mechanism. | I |
| Hairstyle / hair color / facial hair | Partial | Same prompt-directed mechanism. | I |
| Neck / build / height / proportions | Partial | Same prompt-directed mechanism, no explicit body geometry solver. | I |
| Distinctive features / accessories / style | Partial | Captured options and selections exist; photographic fidelity depends on generation. | I |
| Remaining captured attribute groups / randomization | Partial | All19groups/179options are represented in source metadata; randomized selections still feed a prompt. | I full DOM; reference-engine-apps |
| Reference photo / image edit / image output | Implemented | Real image-conditioning path. | I |
|15 style choices / custom style upload | Partial | Preset labels guide generation; custom image drives a real Klein preparation step. No exact source proprietary style implementation. | I style dialog/custom |
| Review prepared character before animation | Implemented | Real intermediate image must be accepted; output is not silently substituted. | I custom; adaptation |
| Source motion video / reference character | Implemented | Wan Animate uses actual pose/face preprocessing and reference image. | I motion |
| Motion / Objects swap tabs, model and quality | Partial | Real available motions/masked swaps; reduced open-model menu and input counts. | I motion-models/quality |
| Object/performer mask and tracking | Implemented | Real mask input and tracking on supported paths. | I swap; own necessary control |
| Keep source scene / Clean reference edges | Implemented; scoped visual pass | SCAIL-2 reference RGB cleanup plus `official-union` final support removed the broad white rim and retained coat/shoe in all 69 reviewed frames at 24 fps: selected 3.000–5.875 s, not the full 17.0417 s source. Hands/identity/action and source-shadow geometry remain imperfect. Fresh-on/legacy-off save/reuse and runtime capability guards are wired. | [Matched render, native-loader exact PNG equivalence and limits](research/recast-reuse-plan.md#influencer-reference-edge-cleanup-completed-selected-interval-proof) |
| Identity training / guaranteed same person across content | Partial | Genuine training is now available through Characters, separate from reference sets. No guarantee of perfect identity across generated content; Influencer does not have its own embedded training editor. | R |
| “Borrow style but never subject” exact disentanglement | Unsupported | Prompt asks for it; model behavior is not guaranteed or separately enforced. | I custom |

## Genjutsu

Code: `Genjutsu.tsx`, `motionRequest.ts`, Shared.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Create Video / Edit Video / Motion Control navigation | Partial | Links/workspaces exist for current operations; not all source model modes/edit tools. | G, E |
| Motion transfer / Objects swap | Implemented | Actual Animate2 Base/Distilled driving-video and appearance controls, legacy performer replacement, masked Wan/LTX swaps. Model-specific conditioning ranges/direction and saved documents; unverified new-model quality. | G |
| Source video / trim / duration / quality | Implemented | Actual video interval and model-aware request. | G |
| Character/product/reference-image count | Partial | One appearance image for motion/current swap; source offers multiple roles/images up to30 in captured states. | G default/selected-style |
| Prompt toggle and instructions | Implemented | Actual optional prompt selection. | G |
| Model search/menu | Partial | Compatible real profiles only; full source menu requires additional providers/model operations. | G models |
| Style Apply / right Styles workspace / remove style | Implemented | State and screen behavior exist. | G styles/selected-style |
|18 style choices | Partial | Captured previews + textual style direction or supported reference path; no original hidden style recipe. | G styles |
| Custom style image | Partial | Actual Klein preparation or Wan reference-conditioned restyle. Disentangling style from identity is not guaranteed. | G custom |
| Uploads / Presets / Generations / Liked drawer | Implemented | Real files, explicit public reference import, scoped jobs/favorites; recent/order controls. | G source-picker-settled |
| Motion library / trending / new / example expansion | Partial | Saved examples and local sorting; no live social feed. | G |
| Like / saved reference | Implemented | Local persisted saved-reference list; not source community likes. | G |
| Recreate example | Partial | Imports actual source preview / selects an operation; no analysis/reconstruction of the example's hidden workflow. | G |
| History / How it works / result exports | Implemented | Scoped real jobs and local operation guidance. | G |
| Long30s /4K / model-specific audio editing | Unsupported | Current profile bounds and capabilities differ; no UI-only limit increase can supply these operations. | G model descriptions |

## Popcorn

Code: `Popcorn.tsx`, `plannerStatus.ts`, `engine/planner.py`; image jobs use Klein.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Auto / Manual / Instadump tabs | Implemented | Separate editor states and pack modal. | P |
| Auto prompt→editable scene proposal | Implemented | Real CPU model JSON, persisted plan, explicit review; no render auto-start. | P Auto; R |
| Automatic analysis of attached images for story | Implemented | SequencePlanner now sends saved reference_asset_ids to the actual multimodal planning/analysis service; proposal evidence is reviewed before execution. Source-complete, not newly tested. | R |
| Manual numbered scene text / add / remove / reorder | Implemented | Up to eight explicit scene requests. | P Manual |
| Result count / aspect ratio | Implemented | Actual scene count and generated dimensions. | P count/ratio |
| Up to four reference images | Implemented | Consumed by Klein edit-image path. | P |
| Coherent continuing story/character across all frames | Partial | Shared brief/reference prompts only; no persistent scene representation or automatic continuity checking. | R |
| Hide/restore composer | Implemented | UI behavior, no effect on actual jobs. | P |
| Instadump pack search / select / preview | Partial | Four loaded captured packs are mapped; Editorial shots imagery was not captured. Original hidden recipes are unavailable. | P settled |
| Pack photo upload / replace / aspect / Back | Implemented | Exactly the chosen photo is retained; real asset, explicit scene review. | P upload |
| Create pack | Partial | Editable local pack direction/scenes, not a published reusable pack service. | P settled |
| Pack Generate10 behavior | Missing | Reference upload step advertises10 results; current adaptation prepares four editable scenes. This is a material count/flow difference. | P upload |
| Per-frame image generation/history/download | Implemented | Actual scene jobs with grouping and results. | P, R |
| Per-frame edit/version history | Partial | Reuse/generate exists, but no explicit storyboard frame-version graph or precise local edit mode. | R |
| Selected frame→Cinema video draft | Implemented | Creates a new video draft with the real image output. | R |
| Whole storyboard→linked animated sequence | Missing | Individual frame handoff is not automatic ordered clip generation and assembly from the storyboard. | R |
| Planning model/status/cancel/deadline | Implemented | Backend-derived model; recorded provenance; batch status; explicit execution limit not ETA; cancel/reopen. Latest status-copy changes were not tested after stop instruction. | Current source requirement |

## Marketing / Ads Studio

Code: `MarketingAds.tsx`, Shared, `backend/product_import.py` (product-link implementation), native image/video operations.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Own sidebar / projects / image/video modes | Implemented | Dedicated screen and saved documents/history. | M |
| Product / avatar upload and picker | Implemented | Real input assets and composition jobs. | M product picker |
| Product URL | Partial | Bounded Product/OG metadata and image import; no broad website/brand strategy analysis or JS-only page extraction. | M product-link |
| Manual product details | Implemented | Saved fields guide image composition. | M product-manual |
| Multiple product/avatar references | Partial | Real multi-reference Klein supports four total; no guaranteed product/logo/identity preservation. | M |
| Ad / Marketplace / UGC / Motion / TikTok styles | Partial | Captured template media and style guidance exist. No exact hidden ad timing/layout/recipe recreation. | M style captures |
| Ad-reference video | Partial | Actual Wan VACE restyle; no ad structure, beat, copy or choreography analysis. | M ad-reference |
| Image variations1–4 / aspect | Implemented | Actual image requests. | M aspect |
| Review composition→video | Implemented | Uses the accepted real composed image for I2V. | M |
| Duration / quality / model/provider | Implemented | Supported profile bounds; source proprietary variants not supplied. | M duration |
| Product background cutout | Implemented | Dedicated BiRefNet RGBA operation. | M; adaptation |
| Generate voiceover WAV | Implemented | Existing genuine Kokoro output; not a voice clone. | M; adaptation |
| Automatic voiceover mux / timed captions / lip-sync in ad | Missing | Separate WAV output is not integrated narrated or lip-synced ad production. Talking Portrait is separate. | M, R |
| Brand kit / typography / exact text/layout rendering | Missing | Prompted branded imagery does not implement deterministic brand/layout composition. | R |
| Auto ad copy, campaign variants, CTA/logo-safe layout | Partial | Prompt/manual fields exist; no dedicated structured campaign/copy/layout engine. | R |
| History/favorites/drafts/result exports | Implemented | Actual scoped operations. | M |

## Katana

Code: `Katana.tsx`, Shared, native restyle / motion / masked replacement.

| Feature/control | Status | Current behavior / gap | Evidence |
|---|---|---|---|
| Reference-video input | Implemented | Real video asset/interval. | K |
| Character inputs | Partial | One supported character reference; source multi-character/product roles are not fully bound. | K, R |
| Optional instructions | Implemented | Saved prompt sent to selected operation. | K instructions |
| Additional trim/duration/model/provider/mask settings | Implemented | Real operation parameters; automatic performer selection is available for SCAIL, with explicit mask selection for supported alternatives. Clean reference edges is an optional SCAIL capability; old omitted values remain off. | Current adaptation |
| Explore / category filters / preset detail / Recreate | Partial | Preview/filter/import works. Recreate does not reverse-engineer source choreography, transitions or timing. | K preset/recreate |
| Automatic edit analysis and recreation | Missing | No shot detector + visual/audio analysis + executable edit-plan reconstruction. | K, R |
| How it works | Partial | Describes actual OpenFrame workflows. No original Claude integration workflow. | K how-it-works |
| Send & Generate in Claude / install Higgsfield in Claude | Unsupported | No corresponding Claude/MCP bridge. Direct local app generation is a different flow. | K |
| Optional source-inverted stylization | Qualified, scoped | Local EditVid/Klein9B preserves the complete241-frame fighters choreography/camera movement in the native comparison; fast-motion trails and regenerated detail remain. Separate source/edit descriptions and fixed native recipe; FLUX9B non-commercial terms. No Cloud or independent PC installation proof; prior LTX failures retained. | `katana-editvid/full-length/` private receipts; runtime guide |
| Local preset export | Implemented | JSON recipe download. | K adaptation |
| Publish preset / title/thumbnail/privacy/community distribution | Unsupported | A local export is not source publishing. No hosted publication endpoint or permissions model. | K publish-dialog/settings |
| Result video / workflow / full project / history | Implemented | Actual selected operation output and export. | K |

## MiniApps launcher inventory

`codex-apps-default.txt` captures **40 visible titles**, not proof of all94 reported in the supplied research. The current source contains15 OpenFrame launchers including Talking Portrait. Similar names are not counted as equivalent dedicated engines.

| Captured launcher | Status | Current mapping / missing operation |
|---|---|---|
| Virality Predictor | Missing | No video-content analysis/scoring; any claimed predictive metric would need a defined method and evidence. |
| Expand image | Implemented | ExpandImage.tsx + OpenFrameExpandImageCanvas: target ratio/canvas/anchor, optional advanced prompt, FLUX3 generation, exact protected original pixels/alpha. No source resizing; actual native mask compositing. |
| Angles2.0 | Missing | No explicit multiview camera/geometry workflow. |
| Shots | Missing | No dedicated one-image→nine-shot generation flow. Cinema/Popcorn are not this launcher. |
| Transitions | Implemented | Transitions.tsx has two image/≤5s video inputs, native endpoint-conditioned5/10s bridge, editable prompt directions, optional original-segment assembly and workflow exports.23reference previews do not reveal proprietary effect recipes. |
| Skin Enhancer | Missing | No dedicated texture-preserving skin retouch controls. |
| AI Stylist | Missing | Captured card describes an AI fitting room; no corresponding fitting-room workflow. |
| Relight | Partial | Klein prompt-led image edit; no dedicated relighting conditioning. |
| Outfit Swap | Partial | Two-reference Klein edit; no dedicated garment fit/mask/virtual-try-on pipeline. |
| Style Snap | Missing | Instant personal-look/style variations; no dedicated variation workflow. |
| Face Swap | Missing | No dedicated face-swap / face alignment / identity-transfer operation. |
| Headshot Generator | Partial | Real reference-guided Klein portrait edit; proprietary identity/output behavior not reproduced. |
| Character Swap2.0 | Partial | Generic two-reference Klein edit, not an explicit local scene-character replacement workflow. |
| Recast | Partial | Actual Wan motion/masked performer replacement is available; full captured proprietary flow/input set not reproduced. |
| Video Face Swap | Missing | Whole-body recasting is not dedicated temporal face replacement. |
| ClipCut | Missing | Captured card explicitly says “Turn One Selfie Into an Instant Outfit Reel”. CPU Trim Video is a separate utility and cannot count as this operation. The captured detail form confirms selfie upload and Continue; no genuine outfit-reel pipeline is implemented. |
| Urban Cuts | Missing | Beat-synced AI outfit videos; no outfit-sequence generation and beat-aligned assembly. |
| Video Background Remover | Implemented | Dedicated prompted SAM3.1/ViTMatte and automaticLTX routes with concept/trimap/confidence or explicit automatic behavior, native RGB/audio, alpha/cutout outputs. Not merely still-image BiRefNet. |
| Breakdown | Missing | Detail capture `codex-breakdown-default` is “AI Lens: Visual Breakdown”: upload + Generate, with copy about components and shop links/brands/prices. The earlier gallery wording does not prove editable RGBA decomposition. Separate `/layers` decomposition must not be presented as complete Breakdown analysis/shopping parity. |
| Japanese Show | Missing | Photo→retro four-panel TV-show scene; no dedicated panel composition recipe. |
| Click to Ad | Partial | Marketing has product→composition→I2V building blocks, not the dedicated source launcher/automatic ad workflow. |
| Billboard Ad | Partial | Prompt-guided image composition; no deterministic planar placement/typography guarantee. |
| Bullet Time Scene | Partial | Product Reveal I2V prompt is not explicit multiview/bullet-time trajectory reconstruction. |
| Truck Ad | Missing | No corresponding placement/template workflow. |
| Bullet Time White | Missing | No dedicated bullet-time workflow; generic orbit language is not equivalent. |
| Game Dump | Missing | Captured card says twelve video-game styles of a person. This is an in-scope image transformation, not a playable game. |
| Nano Strike | Missing | AI tactical-shooter character transformation; no corresponding image workflow. |
| Nano Theft | Missing | Person→realistic open-world game style; no corresponding image workflow. |
| Simlife | Missing | Person→life-simulation character; no corresponding image workflow. |
| Plushies | Missing | Photo→plushie-style animation; no dedicated preparation/animation recipe. |
| AI Meme Generator | Missing | No template/text-layout image composition tool. |
| Background Remover | Implemented | Dedicated BiRefNet still-image soft-alpha PNG output; source dimensions retained. |
| Micro-Beasts | Missing | No mapped template; input/output details need inspection. |
| Signboard | Missing | Captured card describes placing a person on a stylish mural; no corresponding image composition flow. |
| Paint App | Partial | Source card specifically promises retro paint-app art. Current preset is generic whole-image brush/painting guidance; exact retro composition recipe is absent. This launcher alone does not establish an interactive brush editor requirement. |
| On Fire | Missing | No corresponding dedicated template; prompt-only generic replacement cannot be claimed equivalent. |
| Skibidi | Missing | No mapped template/animation recipe. |
| Mukbang | Missing | No mapped template/animation recipe. |
| Cloud Surf | Missing | No mapped template/animation recipe. |
| Idol | Missing | No mapped template/animation recipe. |

Additional current launchers: Vanish, Replace, Restyle, Change Weather and Motion Transfer have real engine routes. They do not fill the unmapped source launcher gaps. Weather's gallery card is explicitly illustrative, not proof of exact transformation. Native current mini-app implementation is `MiniApps.tsx`; common launch controls include search/category, source/reference/mask, provider/model, dimensions, frames/trim, strength, seed, tracking, history/results and export. Relight/outfit/paint/billboard names currently describe prompt recipes rather than separately trained operations.

### Talking Portrait addition

| Control / operation | Status | Source path / boundary |
|---|---|---|
| Separate `/apps/talking-portrait` launch and labelled portrait example | Implemented | MiniApps dedicated form; preview is not claimed as a speech result. No direct source detail-page parity claimed. |
| Portrait image and audio upload/picker/player | Implemented | Real stored inputs; audio uses its own player, not a video-frame thumbnail request. |
| Audio start and exact interval validation | Implemented | Saved `audio_start`; rejects recording shorter than requested frames/FPS; explicit fit action only. |
| Native model bounds / default77frames / fixed16fps / min73 / max161 | Implemented | Derived from current Wan S2V catalog; old unsupported saved model requires explicit reselection. Source complete; new checks paused. |
| Prompt / resolution / aspect / seed / provider | Implemented | Actual speech-conditioned request, no extra image references/mask. |
| Result / history / workflow / media export | Implemented | Existing genuine scoped job/result/export path. No new runtime pass asserted. |
| Exact speech synchronization / robust gesture quality | Partial | Purpose-trained Wan S2V graph is implemented; model-quality validation is unfinished and now paused. Previous LTX speech approach failed quality and is not offered for new requests. |
| Script→speech→portrait workflow and long-script segmentation | Missing | Uploaded audio path only. No integrated script/voice/segment/assembly flow in this MiniApp. Standalone TTS product is excluded. |

## Necessary work before claiming the relevant feature set complete

This is an implementation dependency plan, not a model benchmark or a promise that generic prompts reproduce proprietary effects.

1. **Finish reference contracts for uncaptured relevant states.** Color Transfer and additional model-specific Image options; the unidentified “Off” control; image Layers editor; Soul ID/Cast creation/training; complete Effects ordering/input roles; mini-app detail pages and category “See all” results. The current40-launcher capture cannot establish all94. Record exact inputs, outputs, parameter ranges and hidden menus before implementing.
2. **Add actual video utility operations.** Extend with temporal context; reframe/reposition; video upscale; video background matting; FPS interpolation; depth estimation; SDR/HDR conversion. Each needs a native operation/schema/export path and its own real parameters, not a renamed existing prompt preset.
3. **Add image-region editing and compositing.** Masks/inpaint/outpaint, edit history, deterministic text/placement where source tools require it; then implement Expand/Paint/Signboard/Meme/placement launchers against those operations. Establish actual contracts for relight, outfit/skin edits and multiview shots before calling them dedicated features.
4. **Implement reference understanding.** Uploaded image/video/audio analysis, shot boundaries, motion/pacing/style descriptors and explicit editable analysis output. This is required for CF reference links, Katana recreation and ad-reference structure. Preserve provenance and do not silently substitute a generic text plan.
5. **Complete video/story orchestration.** Storyboard→ordered clips; transitions/timeline; narration creation and alignment; captions; audio mixing; final assembly and aggregate portable sequence package. Preserve existing explicit review/start/cancel/recovery and original requested durations.
6. **Complete identity/character requirements.** Confirm source training contract, implement dataset validation/training/checkpoint registry if still required, role-bound multi-character conditioning, and dedicated temporal face swap where requested. Four reference photos must not be described as training or identity lock.
7. **Complete ad/template workflows.** Structured brand/product/copy/layout data, explicit avatar/product roles, actual template timing/compositing and integrated narrated/speech-conditioned ads. Existing prompt presets remain labelled as such until their full operations exist.
8. **Bring common desktop controls to each separate app.** Scope-appropriate history filtering/view controls, immutable reuse, input role handling, and complete result actions. Verify each control changes a consumed field or a real persisted operation; eliminate inert data-only inputs.
9. **Resolve unsupported integrations explicitly.** Full vendor-model menus, Claude/MCP handoffs and community publishing require actual adapters/services/credentials or an agreed exclusion. They cannot be fulfilled through copied labels. Accounts/billing remain excluded.
10. **Only after the agreed feature implementation is complete**, resume targeted contract/desktop checks and compare strongest eligible models against task-specific criteria. Preserve failed examples, exact prompts/seeds/assets and execution provenance. Model quality and feature completeness are separate gates.

## Current conclusion

The application has real image/video/VFX primitives, separate desktop workspaces, durable documents/jobs and portable exports. It is a substantial implemented subset. The source-backed gaps above remain material, especially proprietary effect recipes, deterministic advanced image editing, full Elements roles, dedicated face/garment/multiview tools, outfit reels and the wider mini-app catalog. Newly implemented utility, region, planning/narration and training source still requires sequential validation. A matching layout or a successful individual render does not close those gaps.

## Current coding gate — implemented source, awaiting final validation

The rows updated above include the selected utility/motion/character integration revision. No new tests, builds, inference or benchmarks were run during this coding phase. Desktop scope is frozen. Remaining missing/partial rows are explicit capability limits, not hidden operative controls. Raw HDR archives use a separate SDR preview; audio inputs never request video-frame thumbnails; auxiliary masks/depth/layers are excluded from ordinary source pickers.

The numbered work list above is the original audit backlog, not authorization to expand the frozen scope. Dedicated native utilities, image-region/Expand/Layers controls, multimodal planning, narration/captions and genuine character training are now source-wired; the remaining vendor-specific capabilities stay unimplemented unless explicitly listed otherwise.
