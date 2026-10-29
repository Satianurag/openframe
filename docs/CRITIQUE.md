# Visual critique

Reviewer: the same backend agent across rounds. Rounds 1–2 were independent of the frontend implementation. During the subsequent strict-fidelity revision, this reviewer authored the bounded HistoryToolbar component; that component must receive separate frontend integration/visual verification, while the main screen review remains independent. Audience: video and VFX creators. The user explicitly requests the public Higgsfield appearance; fidelity takes precedence over the rubric's preference for a new visual category. OpenFrame keeps its own identity and does not claim affiliation.

Reference: `artifacts/reference/video-viewport.png`, `video-mobile.png`, `effects-viewport.png`, `genjutsu-viewport.png`, and `preset-picker.png`. The intended visual system is a 320px creation sidebar, dark `#0f1113` ground, lime `#d1fe17` action, compact top navigation, and a media stage. Scores concern rendered evidence, not backend capabilities or planned GPU demonstrations.

## Final decision

| Area | Final disposition |
| --- | --- |
| Main desktop/mobile studio | Approved with own-brand, supported-model and working-mobile differences; strict component geometry was checked against captured public references. History controls were reviewed separately by the root agent. |
| Main removal demonstration | **Approved:** actual UI job `9a44a1f19f0743569d5ba4c9adfd49b0`, clean 49-frame output, exact executed graph and portable bundle verified. |
| Replacement demonstration | **Approved after contour fix:** application API job `3e609d6da5484a24b1d9337e31c9f3b4`, stable black knight and smooth shadow. All 49 frames and shadow crops reviewed. The older UI job below is historical. |
| Source-image animation / tracking | Corrected Wan opening-frame route and real SAM2-to-LTX route pass their short-clip checks; LTX image animation also passes. |
| Gallery claims | Warm painterly restyle approved with that label. Cinematic street, rainy window and plain lamp are illustrative generated footage; they do not prove those editing effects. |
| Three public-source video segments | Tracked train-window removal passes all 97 frames; outdoor replacement passes the boundary/motion review with changed car geometry and softened adjacent detail. Person restyle is qualified, with yellow highlights and soft fine detail; its LTX comparison was rejected. Inputs/results remain private validation material. |
| Hosted Cloud | Genuine static and shorter tracked executions completed. The longer tracked request hit the service execution limit. Tracked visual evidence is sampled; exact audio alignment and cancelled native-audio export remain unverified. |
| Handoff | Final removal bundle preserves executed semantics, includes original media and expected pinned model hashes, and excludes unnecessary static-mask tracking dependencies. Only the separately recorded adapter check verified downloaded model bytes. |

The rounds below retain the review history, including rejected candidates and the corrections they motivated. Later follow-up sections and `VALIDATION.md` record current jobs and remaining limits; earlier rounds are historical.

## Round 1 — 29 October 2026

Inspected the 390, 768, 1280 and 1440 desktop/mobile first screens; both numbered full-page slices at 390 and 1440; the matrix contact sheet; the later High Contrast screenshot; model picker, settings and mobile creation-panel states. Evidence is under `artifacts/validation/frontend/round1`, `matrix`, and `components`. Full-page captures include internally scrolling surfaces and fixed controls; fixed-navigation repetition in stitched images is not itself a browser defect.

| # | Criterion | Score / 5 | Visible evidence |
|---|---|---:|---|
| 1 | Concept on the page | 4 | Effect choices, model selection, workflow export and a prominent Generate action communicate an open video studio directly. |
| 2 | Reference specificity (user override) | 4 | The dark stage, 320px sidebar, lime action and compact navigation reproduce the requested reference grammar rather than a generic dashboard. |
| 3 | Not a slop face | 4 | The screen is organized around a creative task and media choices, without ornamental KPIs, testimonials or decorative dashboard statistics; the dark palette is required by the reference. |
| 4 | First screen | 3 | The task and action are clear on desktop and phone, but abstract cards provide no visible evidence of actual generated or edited video. |
| 5 | Typography | 3 | The condensed display titles give hierarchy, but the scan records 51–64 text elements at 11px and the reference's functional labels are visibly more readable. |
| 6 | Colour | 4 | Lime identifies active choices and the main action consistently; dark surfaces and neutral secondary text retain a coherent hierarchy. |
| 7 | Richness | 3 | The original illustrations form a consistent art direction, but their repeated geometric silhouettes look like a prototype beside the reference's photographic video imagery. |
| 8 | Structure and rhythm | 4 | Creation controls and the media stage are clearly separated; filters, cards and the lower workflow-export panel have distinct, useful roles. |
| 9 | Craft | 3 | The settings and model dialogs are aligned and polished, but the default 900px-high sidebar partially hides the Resolution/FPS row and the model search says “Search choose a model.” |
| 10 | Responsive | 4 | Phone navigation and a dedicated creation sheet are intentionally adapted; tablet retains two effective work areas and the wide gallery expands sensibly. |
| 11 | Everyone's computer | 3 | Chromium and WebKit layouts hold, including 320px reflow, but the latest High Contrast rerun still reports missing textarea/select boundaries; Firefox is unavailable and unverified. |
| 12 | Signature | 2 | A before/after comparison interaction is specified, but neither a result-state screenshot nor its filmstrip was available in this round; the rendered gallery alone does not demonstrate it. |
| 13 | Screenshot test | 3 | The shell is coherent and recognizable, but the small labels and entirely illustrative media prevent this from reading as a finished VFX demonstration. |
| 14 | Fidelity | 3 | Geometry, palette and controls are close to the references; typography density and the absence of real video imagery are the largest visible differences. |

Six of the thirteen base criteria reach 4. This is a useful first implementation, not a final visual approval. Signature score 2 represents missing rendered evidence, not a claim that the interaction is absent from the source.

### Five changes requested

1. **Raise functional text to a readable floor.** Make metadata, tabs, category labels and badges at least 12px; make descriptive prose 13px where space permits. Keep Inter, which is an intentional reference choice. Recheck the 390px filters, 320px reflow and settings dialog after the change.
2. **Make the creation-panel scroll boundary explicit.** At 1280/1440×900 the Resolution/FPS row is cut by the sticky Generate footer; on the phone sheet only the Duration/Aspect headings are visible. Compact the upload/prompt area where useful, keep the footer outside scrollable content, and expose a thin scroll indicator or equivalent clear overflow affordance. Every setting must remain reachable without disappearing underneath the action.
3. **Put media provenance beside the gallery.** Move or repeat a concise “Illustrative prompt presets” notice above the cards, since the existing disclaimer appears only after all ten cards. Use genuinely validated OpenFrame output posters when available, clearly distinguished from illustrations; do not substitute fabricated render evidence. Capture the real result comparison at multiple slider positions so the signature can be graded.
4. **Finish forced-colors control boundaries.** Give the prompt textarea and Duration, Aspect, Resolution and FPS selects a visible system-color border in forced-colors mode. The newer HC run fixed navigation controls but still names these five controls as failures; rerun that targeted matrix case.
5. **Remove generated-sounding picker copy.** Change “Search choose a model” to “Search models” and inspect the same shared picker for similarly composed placeholders. Keep clear model capability descriptions and the selected-state checkmark.

The scanner's Inter/default-font warning is intentionally accepted because fidelity is explicit. Its nested-container/radius warnings do not justify removing the requested sidebar/stage structure. Actual boundary failures take priority over those stylistic warnings.

### Verification required for round 2

Supply fresh first screens and affected component captures, the fixed HC result, and the comparison signature filmstrip. Failed mask-flow component captures must be explained or corrected before treating the editing flow as verified. API tests use explicit engine doubles and are not evidence of model quality; real GPU results are validated separately.

**Not done by the stop rule.**

Round-1 follow-up: all 30 component interactions now pass with no page errors and no render submissions (`interaction-results.json`). The earlier mask failures were test-selector mismatches, not product errors. The corrected desktop and phone mask dialogs are well proportioned. One mechanical feedback defect remains visible in `components/20-mask-paint.png`: the empty-mask validation error persists after a painted stroke; the frontend has been asked to clear it when the mask becomes valid.

## Round 2 — 29 October 2026

Inspected all four new first screens, both numbered full-page slices at 390 and 1440, `matrix-round2/sheet.png`, the clean matrix report, and the corrected painted-mask state. The 30 component checks pass, with no page errors and no accidental render submissions. These remain UI fixture checks, not inference evidence.

| # | Criterion | Score / 5 | Visible evidence |
|---|---|---:|---|
| 1 | Concept on the page | 4 | Creation, editing, model choice and owned-workflow export remain visible and coherent. |
| 2 | Reference specificity (user override) | 4 | The 320px dark control rail, separated stage and lime action retain the requested Higgsfield layout language. |
| 3 | Not a slop face | 4 | The interface stays focused on media creation and manipulation without unrelated dashboard decoration. |
| 4 | First screen | 3 | The task, primary action and illustration disclosure are now clear, but the first screen still shows no actual generated-video evidence. |
| 5 | Typography | 4 | Functional labels now use a 12px floor and descriptions are readable at 13px; the earlier 11px scan warning is gone at every tested width. |
| 6 | Colour | 4 | Lime consistently marks actions and selections; the compute pill is now neutral until connectivity is confirmed. |
| 7 | Richness | 3 | The illustrations are coherent and honestly identified, but photographic video media remains absent compared with the reference. |
| 8 | Structure and rhythm | 4 | Compact creation controls fit together, and the stage retains clear hierarchy and breathing room. |
| 9 | Craft | 4 | All four basic parameter fields are visible above Generate at 900px height, picker copy is corrected, and painting clears the stale empty-mask error. |
| 10 | Responsive | 4 | Phone controls and mask editing are deliberately arranged; the tablet split view and wide gallery remain usable. |
| 11 | Everyone's computer | 4 | Every available matrix case now has zero failures, including forced colors, scaling, WebKit, reduced motion and 320px reflow; Firefox remains explicitly unverified. |
| 12 | Signature | 2 | The mask interaction is now evidenced, but the specified result-comparison signature still has no rendered state or filmstrip to judge. |
| 13 | Screenshot test | 3 | The UI shell is polished; the entirely illustrative gallery still reads as a studio awaiting its actual video demonstration. |
| 14 | Fidelity | 3 | Layout, controls and text density are closer; the reference's real video imagery is still the largest visible difference. |

Nine of thirteen base criteria reach 4. No scan or available-matrix failures remain. All five round-1 implementation asks landed: readable text, visible basic controls, above-gallery disclosure, forced-colors boundaries and human picker copy. The provenance ask is partly complete: the disclosure is present, while authentic result imagery and comparison evidence are still pending. No redesign of the shell is requested.

### Five targeted remaining actions

1. **Use authentic result imagery when available.** Replace at least the first generation and first VFX poster with a frame from a validated OpenFrame run. Retain the illustrative notice for remaining illustrated presets and identify real examples accurately. Do not borrow reference footage or represent a UI fixture as model output.
2. **Capture the desktop comparison signature.** Show a real source/result pair at approximately 20%, 50% and 80% slider positions, plus playback/seek states, with source/result labels readable. This is evidence for an existing interaction, not a new feature request.
3. **Capture that comparison on the phone.** Verify the handle, playback controls, result download and export actions remain reachable at 390px without covering the media. Keep the original aspect ratio and synchronized frame time.
4. **Keep illustration strokes behind card captions.** In the Create Video and Vanish cards, curve/mask outlines cross the caption area. Add a sufficiently opaque lower scrim behind titles/descriptions, with the caption layer above the illustration. Keep the new readable text sizes; do not shrink them to solve this.
5. **Capture actual job outcomes with the final result.** Show the existing queued/running/result or truthful error states and the result's workflow/bundle actions. Clearly separate UI fixture checks from the successful inference evidence. This completes the requested component audit without inventing new controls.

A separate integration correction tightened source-duration preflight to a 1ms metadata tolerance; a 2s source at 8fps cannot supply a 17-frame request. The backend regression passes. This protects users from a delayed remote failure and must agree with frontend preflight.

**Not done by the stop rule.** The remaining major blocker is missing result/comparison evidence, not a request for another wholesale design iteration.

## Strict reference revision — pending rendered review

The user's later clarification requires component-level fidelity, beyond the earlier palette/layout rubric. Rounds 1–2 remain historical evidence and are not approval of the revised screen. The new primary evidence is the live public-page audit under `artifacts/reference/fidelity`, captured at 1440×1000 with matching mobile references. The next review compares actual typefaces, navigation height, sidebar control geometry, the initial three-step stage, anchored model/parameter popovers, edit controls, preset/asset pickers and history controls against those captures. No revised-screen pass is claimed before final screenshots.

Intentional content exceptions are OpenFrame identity, actual supported open-model names, no authentication/payment controls, and only working editing actions. The history filter also retains an optional Status row for the app's existing active/completed/failed filtering; it uses the reference row styling but is an added product control. Calendar dates are dynamic, not frozen to the reference capture date.

## Actual VFX baseline observation

The separate real H100 baseline in `artifacts/validation/ltx-vfx-single-baseline` is a single-stage LTX 2.3 inpaint render, 512×320, 49 frames at 24fps. It is not the final two-stage validation. The source contains 97 frames; this review uses only the aligned first 49 frames and does not compare mismatched times. The source and output have no audio stream, so this example cannot establish source-audio preservation.

The reviewer inspected source/result/mask at frames 0, 12, 24, 36 and 48 (`critic-aligned-frames.jpg`). The red vase and its long leftward cast shadow are removed in all five samples. Curtain folds and marble grain fill the edited region plausibly; no obvious red residue or hard boundary halo is visible in these samples. The unrelated right-hand table shadow and surrounding camera/scene movement remain. This is a useful actual removal example, not evidence of universal scene performance or moving-object tracking: this request uses a static mask.

Decoded RGB comparison across all 49 aligned frames gives an outside-mask mean absolute difference of 1.4329 on a 0–255 scale (99th percentile 4.0). This supports close exterior preservation while acknowledging lossy re-encoding; it is not pixel identity. Inside-mask adjacent-frame mean difference is 0.7845/255. These numerical observations and sampled frames show no obvious gross flicker, but they do not replace perceptual playback or prove absence of subtle temporal artifacts. Full method/values are in `critic-pixel-observation.json`. The final two-stage result and the app's comparison UI still require their own review.

### Two-stage first render — visual rejection

The initial 1024×640 two-stage run completed the pipeline but **does not pass visual review**. Its rounded pale-green region is visible at all five aligned times (frames 0, 12, 24, 36 and 48); see `artifacts/validation/ltx-vfx-two-stage/critic-aligned-frames.jpg` and the full-resolution `midframe.png`. The object/shadow are removed, but the mask-shaped colour discontinuity is a material defect absent from the single-stage baseline.

The executed graph sends green-filled guides to `image_b` of both Laplacian blends. The upstream blend correctly interprets white as generated `image_a`; no inversion was found. Its seven-level frequency blend uses Gaussian mask pyramids, so a green placeholder can affect low-frequency reconstruction even when the high-resolution selection is correct. The final original-plate composite then limits that shifted colour to the original mask, exposing its rounded boundary. `mask_low_res_dilation=5/6` is dilation radius after reducing the long side to 64 pixels, not a five-/six-level pyramid setting.

This is the leading source-backed diagnosis, pending inspection of cached intermediate images. The proposed correction is to use a target image already containing generated pixels inside the generation mask and original pixels outside it, removing the green placeholder from pyramid blending. Substituting the raw original alone could leak the removed object's colour back through the same low-frequency mechanism. Engine ownership remains with the engine agent; this review made no engine changes and launched no diffusion work.

## Strict reference review — first integrated capture

Reviewed matching desktop states at 1440×1000 under `artifacts/validation/frontend/fidelity`: Create base/model/duration/aspect/quality/FPS, preset picker, editing tools, edit workflow, Draw empty and reference upload. Compared them with the public snapshots under `artifacts/reference/fidelity`. HistoryToolbar states are excluded from independent assessment because this reviewer authored that helper; the parent reviews them separately. This is a component comparison, not a claim of pixel identity or completed interaction QA.

The base geometry is substantially closer than rounds 1–2. Model is exactly x25/y688/302×54, Duration x25/y750/147×54, Aspect x180/y750/147×54, Quality x25/y812/147×54, and Generate x25/y874/302×48 in both captured layouts. The 44px announcement, compact navigation, 320px creation rail, three-step help layout and right-anchored popovers now follow the measured source. The shorter model/option menus correctly contain only supported choices; their reduced height is not a layout bug. Reference-upload panel position and dimensions are close, with honest actual asset count instead of copied skeleton items.

Material corrections requested:

| Component | Observed difference | Requested correction |
|---|---|---|
| Duration | Browser-native thin outlined track and round lime thumb; source has a substantial dark 24px track, compact rectangular thumb/tick and small dot ticks. | Style the actual slider to the source geometry while retaining supported durations and keyboard behavior. |
| Editing-tools rail | Own left rail stops near y592; reference rail continues to y969. | Stretch this menu-state rail to stage height without adding inert menu items. |
| Editing-tools stage | Own inner bordered card continues to y902; reference ends at y770, leaving quiet stage space above the footer. | Restore the inner card's source-sized height; retain the working real before/after content. |
| Tutorial upload illustration | Missing inset dashed rectangle, with icon/title roughly 40px left of source composition. | Match the inset/offset arrangement using owned media. |
| Preset labels | Angular black slabs behind captions; reference uses a smooth lower image scrim. | Use an unobtrusive gradient with readable captions, without the polygon edges. |
| Draw empty | Own dialog x88/y69/1264×862 versus source x80/y60/1280×880; darker body/separate header, icon-only artwork, smaller/misplaced CTA. | Match the rounded uniform surface, owned-media preview around 425×250, subtle dot field, title/CTA placement and approximately 207×48 action. Keep only the working Draw to Edit choice. |

Tabs and values look slightly heavier in the rendered implementation, but source HTML uses `font-medium` too and the local font files correctly declare weights 400/500/600/700. This observation alone does not justify changing all medium text to regular; nested computed styles or font-specific rendering need checking before a typography change.

Content exceptions remain explicit: supported open models/effects, original branding/media, no paid/authentication controls, working provider integration, and no unsupported multi-reference upload area for an LTX profile. The source's mobile composer says “coming soon”; the working mobile composer is an intentional functional extension. The first supplied `mobile-base.png` shows Edit rather than the reference's Create state, so it is not a valid like-for-like mobile comparison. A fresh matching state was requested. No final strict-fidelity pass is assigned yet.

### Two-stage correction prototype

The clean-target blend run in `artifacts/validation/ltx-vfx-two-stage-fixed/midframe.png` removes the strong green cast but still shows a lighter neutral mask-shaped patch. Thus placeholder contamination was not the whole mechanism: remaining low-frequency brightness/colour differences between generated and original footage are exposed by exact exterior restoration.

The engine's `poisson-padded-prototype.png`, a CPU composite on that actual rendered frame, removes the visible patch while keeping the vase/shadow absent and natural-looking curtain/table transitions. The reviewer inspected both full-resolution images. This is a promising single-frame prototype, not yet a complete clip or deployed-pipeline pass. Temporal behaviour and boundary handling must be checked on the resulting clip. A new optional compositing setting must default off for older graph compatibility and be explicitly enabled in new object-removal graphs, rather than silently changing stored execution semantics.

### Corrected full-clip composite review

The actual updated SaveVideo node processed all 49 frames of the recorded H100 result with padded normal-Poisson matching. This is explicitly **CPU postprocessing of the recorded model output**, not a new diffusion run or proof of deployed end-to-end execution. The new `match_lighting` input is optional and defaults false; new object-removal graphs opt in, while replacement graphs and older graphs retain the prior behavior.

The reviewer independently decoded all 49 frames at 1024×640 and inspected every frame in `artifacts/validation/ltx-vfx-composite/critic-all-49-frames.jpg`. The persistent rounded patch is absent. No red vase remnant, retained left-edge object shadow or obvious abrupt discontinuity is visible in this contact sheet. The full-resolution single-frame prototype was inspected separately. Exterior decoded RGB difference averages 0.985/255 (worst per-frame exterior mean 1.079), including resampling and lossy encoding. Interior adjacent-frame change averages 0.916/255, maximum 1.576 at frame 4. These are observations, not universal quality metrics or a guarantee against subtle playback artifacts. Details are recorded in `critic-observations.json`.

**The demonstrated corrected static-mask clip passes this bounded visual review.** This does not establish moving-mask tracking quality, arbitrary scenes or the final deployed render path; those require their own evidence. The initial two-stage result remains rejected and must not be substituted for this corrected artifact.

### History controls — separate reviewer

The parent/root agent independently reviewed the HistoryToolbar component that this critic authored. Its concrete findings were sent directly to frontend: the View size slider still used a native thin green track/round thumb instead of the reference's 32px rounded gray track with 20/40/60/80 ticks; the extra Status row increased Filter height by roughly 36px and requires secondary placement or explicit functional-exception treatment; sparkle/fill icons differed from the available reference SVG shapes. Those findings belong to the parent reviewer, not this critic's independent assessment. Verification of frontend corrections is pending.

## Strict reference review — desktop correction pass

Reopened the current Create base/duration/FPS, preset picker, editing-tools and Draw-empty captures after frontend's corrections. All six material desktop requests above are addressed: custom track/rectangular thumb, full-height tool rail, 624px inner edit card, inset tutorial composition, smooth caption scrim and the photographic Draw dialog composition. The Draw action now measures 207×48 at x616.5/y707, within roughly one pixel of the source position. The new actual removal preview gives the editing stage real source/result evidence; it is distinguished from a submitted app job.

No further material desktop layout blocker was found in these inspected states. This is a bounded visual approval with the stated content exceptions, not a claim of literal pixel identity. Typography rendering, original media, actual model/menu counts, supported controls and the smaller working-only navigation necessarily differ. History remains under the separate parent review. App result interaction and final mobile Create comparison remain separate pending checks. The capture index lists 18 states and an empty error array; that capture result does not by itself establish every control's functional correctness.

## Actual app render — rejected input variant

App job `1d13a5c4703045b2b5886d13455fec19` completed on deployed Modal H100 through the two-stage LTX 2.3 path: 1024×640, 49 frames at 24fps, 32.094 seconds recorded Comfy execution time. API/backend completion is real, but **this output fails visual quality review**. Full-size frame 24 and the all-49-frame contact sheet show a translucent vase-shaped ghost, residual long shadow and stronger red edging in later frames. Exterior error remains low (mean 0.998/255), demonstrating why that metric alone cannot establish successful removal.

This job used a different input mask from the successful composite. Asset `dc128e91820e45fbacb208a02efa3cc5` is a tight irregular polygon reaching the top boundary; the previously validated mask is a broad rounded region with a shadow extension. The executed app graph correctly has `match_lighting:true`. Within a fixed vase ROI, a simple red-pixel heuristic finds an uncovered one-pixel red strip in 13 of 49 frames (24 pixels in the last frame); the validated rectangular mask has none under the same heuristic. Early frames show no red omission under this test but still have the ghost, so partial mask coverage does not prove the entire mechanism. Shape, margin and boundary differences remain relevant. Root/engine were asked to rerun the exact validated mask for a controlled comparison.

Evidence: `artifacts/validation/app-vfx/1d13a5c4703045b2b5886d13455fec19/critic-midframe.png`, `critic-all-49-frames.jpg`, `critic-mask-coverage.jpg`, and the two observation JSON files. The accepted earlier CPU-composite review remains valid for its own mask/result only. This failed app variant must not be presented as the clean removal showcase.

## Actual app controlled rerun — approved demonstration

App job `52dbb8bd844848e982f73c4016370808` reran the same source through deployed Modal H100 using the exact validated `mask-refined.png` (asset `35c497e851b54266b3108c75a7d3a6b7`, SHA-256 `30ed5138a05f5011424023abd83b979cc3354eef358857ac0f3e39802242fafe`). The result is 1024×640, 49 frames at 24fps, two-stage LTX 2.3 with the explicit removal compositing correction. The recorded Comfy time is 17.984 seconds for this warm run; this is not a general latency guarantee or cold-start benchmark.

The reviewer decoded every frame, inspected all 49 in a contact sheet and viewed the full-resolution midpoint. The vase and long object shadow are removed, with coherent curtain/table fill and no visible rounded colour patch, red rim or vase-shaped ghost. Outside-mask mean decoded RGB difference is 1.004/255 including encoding; inside-mask adjacent-frame change averages 0.853/255 with maximum 1.525. No obvious abrupt discontinuity appears in the contact sheet. This supports the demonstrated scene and mask, not universal performance, moving-mask tracking or a guarantee against subtle playback artifacts.

**This actual deployed-app result passes the bounded visual review and is the approved removal showcase.** The earlier `1d13...` app variant remains rejected. Evidence is under `artifacts/validation/app-vfx/52dbb8bd844848e982f73c4016370808`: `critic-midframe.png`, `critic-all-49-frames.jpg`, `critic-observations.json`, original result/mask clips and `job.json`. The separate app comparison-slider interaction still belongs to frontend verification.

Final completed-implementation backend verification: `.venv/bin/python -m unittest discover -s tests -p test_backend.py -v` passed **12 tests in 1.913s**; `.venv/bin/python -m unittest discover -s tests -p test_release.py -v` passed **2 tests in 0.010s**. Backend tests deliberately use an engine double and are not GPU evidence. Packaging tests use tiny temporary fixtures; they did not create the final source release archive. Reports are `artifacts/validation/backend-api.json` and `release-tests.json`.

## Replacement gallery candidate — not yet approved

App job `3c03d3ec6e1b4392b85b1429add2c15e` requests a matte black chess knight in the same source/mask. The result contains a recognizable black horse-head piece with curved neck, round base and leftward shadow. All 49 decoded frames were inspected; geometry and placement stay coherent, with no obvious abrupt change. The material appears somewhat glossy rather than matte.

The decisive defect is a persistent rounded light-colour patch in the surrounding background, clearly visible at full resolution and throughout the contact sheet. Therefore this is **semantic replacement success but not an approved polished gallery preview**. Replacement correctly leaves the removal-only `match_lighting` behavior off; enabling colour normalization globally could alter intended new-object colours. A bounded optional-compositing experiment on this particular result can test whether it fixes the background while preserving the black knight, but no such corrected result is approved here yet.

Evidence is in `artifacts/validation/app-replacement/3c03d3ec6e1b4392b85b1429add2c15e`: midpoint, all-49-frame sheet and observations. Exterior error mean 1.007/255 and interior adjacent-frame mean 0.974/255 do not override the visible seam. A reusable bounded frame-inspection helper now lives under `artifacts/validation/review_clip.py`; it writes small review artifacts and explicitly provides no automatic quality verdict.

## Wan watercolor restyle candidate — not approved for that claim

App job `3bdeb32246954d36b5f67c15be914df6` completed a real Wan VACE render, 512×320, 33 frames at 16 FPS. Full-clip frame inspection shows a coherent vase/table/curtain arrangement and stable stronger golden lighting. It does not show the requested visible watercolor paper, pigment washes or ink outlines: the vase and curtains still read as glossy rendered/photographic forms. A small tan rectangular glyph-like artifact also appears on the wall beside the vase neck. This is **not an approved watercolor demonstration**; at most it supports a modest warm-colour restyle result.

Evidence is in `artifacts/validation/app-restyle/3bdeb32246954d36b5f67c15be914df6` (midpoint, all-33-frame contact sheet, observations). Mean adjacent-frame RGB change 2.272/255, maximum 4.293/255 at frame 1, is descriptive rather than a style or artifact pass. `strength=0.85` is wired directly to Wan VACE conditioning strength, so its relation to the UI's transformation label needs care: stronger conditioning is not automatically stronger stylization. This observation was sent to the engine owner before proposing a changed parameter.

## Short Fast gallery imagery

The following real app generations were inspected at full midpoint resolution and across all 17 decoded frames each (512×768, 24 FPS, approximately 0.708 seconds). These are **illustrative generated images in motion**, not proof of an editing effect or sustained/seamless temporal performance.

| Candidate | Decision | Observed reason |
| --- | --- | --- |
| `gallery-cinematic/8d300f1f048347718d30dfda484867e5` | Approve illustrative gallery use | Attractive warm/cyan wet-street reflections, coherent framing and geometry, intentional soft focus. |
| `gallery-weather/971ee0e00a0c4bb2a932cddfb16b2d8c` | Approve illustrative gallery use | Coherent rainy-window droplets against a defocused lawn/light, no obvious abrupt structural discontinuity. |
| `gallery-product-reveal/ed5e0a1a01e34ccf9191af406b44b567` | Replace candidate for polished gallery | Coherent bottle/cap/smoke, but prominent garbled pseudo-brand lettering across the bottle dominates the product. A genuinely blank unbranded product would avoid that visible defect. |

Each directory contains a midpoint PNG, all-frame contact JPEG and descriptive observations. These approvals do not change the separate requirement to validate the corresponding actual model/task routes.

## Final Create mobile capture correction

The refreshed `frontend/fidelity/mobile-base.png` now correctly shows Create Video rather than persisted Remove Object state. Compared with the public `create-mobile-base.png`, the help heading, text width, three-column instructions, outer panel and navigation geometry closely match. Own brand, supported content, generated media and a working Create action are intentional differences. The stale-state capture blocker is resolved.

`mobile-composer.png` shows the usable mobile form. The public reference instead displays “Mobile access coming soon”; working mobile creation is an intentional functional extension, not a pixel-equivalence claim. This visual review approves the shown layout; scrolling, keyboard behavior and action execution rely on the frontend's separately recorded functional checks. History controls remain independently reviewed by the root agent, since this critic authored their initial helper.

## Additional real GPU route review

These are direct provider-route runs, not newly demonstrated app API submissions. Every decoded frame and each full-resolution midpoint was inspected. The route directories contain their original request/result/graph records plus bounded critic evidence.

| Route | Observed visual behavior | Supported claim / remaining issue |
| --- | --- | --- |
| LTX 2.3 image-to-video, 17 frames | Preserves the supplied red vase, marble table and curtain composition with subtle coherent movement. | Approve the short source-image animation demonstration. |
| LTX 2.3 weather/restyle, 49 frames | Coherent overcast-looking stream, but rocks and moss are substantially regenerated from the sunlit source; no convincing falling rain or unmistakable raindrop ripples. | Real restyle execution and lighting/scene change demonstrated. Faithful weather replacement and added rain are not established. |
| Wan image-to-video, 17 frames | Coherent red vase, but a different vase silhouette and a completely new window/plant/table scene. | **Not approved as faithful source-image animation.** Executed graph passes the image as VACE `reference_image`, the same conditioning mode as reference generation. Engine owner notified to correct or truthfully relabel this semantic mismatch. |
| Wan reference generation, 17 frames | Stable stylized studio scene with a tall, narrow red vase. | Reference-guided route executes; subject resemblance is loose. Exact product shape/identity preservation is not demonstrated. |

The weather source midpoint was extracted from the original `ltx-native-audio` output at the matching time and is retained alongside the weather result for direct comparison. The review helper now handles provider result records without fabricating an app job record; its scope field explicitly distinguishes these runs.

## Refined gallery candidates and native replacement

- Wan restyle app job `b4e93a0d70c04675b824cf79d2e6a12e`, source guidance 0.4: all 33 frames remain coherent. Compared with the earlier attempt, broad softened colour strokes make the warm painterly change visible. **Approved as a warm painterly restyle example**, not a precise demonstration of watercolor paper grain or ink outlines.
- Product app job `7cf9e3e5569f4b8fb243b836ddd69e14`: a clean, unbranded lamp avoids the previous pseudo-lettering. **Approved as illustrative product imagery.** Its 17-frame sequence is almost static and does not prove a product reveal or camera orbit.
- Native full-resolution single-stage replacement, provider job `1ecfe76fc44f40fabe7067c230993d61`: all 49 frames show a stable recognizable black knight; the large pale background rectangle is gone and black colour is retained without the rejected colour-correction prototypes. **Semantically passes replacement and is usable for gallery imagery.** At full resolution, a localized staircase edge on the lower side of the long shadow remains; engine owner is investigating mask/compositing aliasing before any flawless-boundary claim. This record is a direct provider render, not an app API submission.

Rejected Poisson/context-field variants did not enter production. Those variants either washed out the new black base, retained a patch or leaked reddish source-vase colour. The native single-stage result is the substantially better candidate.

## Approved removal bundle review

The full-media API bundle for approved job `52dbb8bd844848e982f73c4016370808` was read in bounded memory, without saving a duplicate ZIP. The portable graph exactly preserves the executed graph after only `source.filename`, `source.mask_filename` and `save.source_filename` relocations. `match_lighting:true` remains present. Source and mask bytes match their manifest SHA-256 values, all archive paths are relative, and UI workflow is included. Its static mask correctly excludes SAM2 model/package requirements. Exactly four declared LTX files match the actual loader nodes.

Official expected weight checksums were retrieved with the installed Hugging Face CLI at the pinned commits for base, distillation LoRA and Gemma encoder. The gated adapter's public CLI checksum is redacted, so its value comes from the existing exact-revision adapter integrity record, which previously matched official metadata and verified local bytes. **This is not a new verification of every downloaded model file.** No weight was downloaded or re-hashed in this check. Evidence: `approved-bundle-review.json`, `ltx-vfx-expected-checksums.json` and `ltx-adapter-integrity.json` under validation. Bundle README/API documentation explicitly distinguish expected weight metadata from actual input-media hashing.

## Final conditioning and tracking route checks

The corrected Wan first-frame route `afdb1994e86441cb83f2129c2387480e` now uses the uploaded image as control video with a known black opening-frame mask; reference images remain a separate capability. All 17 frames preserve the original red vase, curtain and marble-table composition with coherent gentle changes. **The source-animation semantics now pass for this demonstrated case.** The earlier reference-only route remains documented as the failure that prompted this correction.

SAM2-enabled LTX removal `78ba4b0f9a71487a90358d8923810f9b` also passes the 17-frame visual review. Every exported mask was overlaid on the exact original vase clip. Mask area varies from 109,383 to 118,398 pixels; consecutive changes range from 828 to 8,580 pixels, with the largest change at the final frame. Vase and shadow remain covered; the rendered removal stays clean without an obvious abrupt discontinuity. Exterior mean RGB difference is 0.996/255, including resize/encoding differences. This demonstrates the real tracking-to-render route on a small-motion clip, not a general fast-motion or occlusion guarantee. Evidence includes `critic-mask-all-17-frames.jpg` and `critic-mask-observations.json` in the route directory.

After expected-checksum metadata was added, the current source generated a bundle from the actual persisted approved removal job through read-only SQLite. Its four expected hashes/sizes match the pinned official metadata evidence, static-mask requirements still exclude SAM2, and the checksum disclaimer is present. The two affected media-roundtrip and stored-executed-graph regression tests passed (0.670 seconds). These are reruns of existing cases, not additional distinct tests. The live API must reload this source before the final bundle is saved.

## Final UI-submitted release demonstrations

The frontend's actual UI recording submitted replacement `fe826683f5cb45b3a48ad32782115365` and removal `9a44a1f19f0743569d5ba4c9adfd49b0`, reused the validated source/mask, displayed real progress, opened comparisons and downloaded real canvas/project exports. This resolves the earlier distinction between direct provider trials and final app execution. Both outputs are 1024×640, 49 frames at 24 FPS. Their full clips, original job records, stored API graphs, every-frame contact sheets and execution checks are retained in `app-replacement-final/<id>` and `app-removal-final/<id>` under validation.

**Removal is approved as the main demonstration.** All 49 decoded frames and the full-resolution midpoint show clean vase and object-shadow removal, natural curtain/table reconstruction, no obvious pale rectangle, red rim, ghost or abrupt temporal discontinuity. Its actual 44-node graph uses the two-stage route, inward feathering and explicit lighting matching; seed 44 and the exact validated mask SHA-256 were checked. Recorded Comfy time is 18.890 seconds for this warm run, not an end-to-end or general latency promise.

**Replacement is approved as a functional example with a localized limitation.** Its actual 23-node graph uses a full-resolution single conditioned pass, inward feathering and `match_lighting:false`, with seed 46 and the exact validated mask. The black knight remains coherent through all 49 frames, without the old large pale patch or washed-out base. Fine staircase aliasing remains along the lower edge of its long cast shadow; softer feathering did not eliminate it. Do not describe that boundary as flawless. The clean removal remains the stronger hero example.

The final removal full-media bundle was checked in bounded memory through the restarted live API: 152,074 bytes; source/mask hashes match bundled bytes; API and UI filenames are portable; the stored executed graph is retained; exactly four pinned LTX model requirements include expected upstream hashes; unnecessary SAM2 requirements are absent for the static mask. No duplicate ZIP was saved by the critic. See `critic-bundle-check.json` in the final removal directory.

Actual final comparison screenshots show matching framing, clear Original/Generated labels and the selected source interval. The settled-state recaptures in `frontend/settled` resolve the earlier native buffering-spinner captures and truncated prompt titles. The removal result and mobile export controls pass visual review. Separate real-result checks exercised playback/seek/speed synchronization, fullscreen, mobile controls, downloads and exact recipe reuse. The gallery review separately caught two mask-stream posters mistakenly selected from multi-output directories; the preview source selection was corrected to explicit `role=result`, and the poster files now show the real edits. Actual result playback used the correct output throughout. Replace uses the full edited gallery image so a fixed before/after split cannot obscure the new subject. The refreshed `frontend/settled/approved-gallery.png` was inspected after both corrections: the full black knight is recognizable, removal/restyle comparisons contain real result imagery, and provenance labels remain readable. The final gallery visual review passes.


## Final controlled replacement mask-margin check

The final UI job `942e8b6f52314b65a7ec736d2e3c28d2` uses a 12-pixel wider allowed edit region while reducing generation dilation from 16 to 4. The engine's binary-mask comparison records **zero differing generation-mask pixels**; only the allowed composite region expands by 23,016 pixels. Prompt, seed 46, 1024×640 dimensions, 49 frames, 24 FPS, static tracking and feather 6 remain unchanged. The actual stored 23-node graph confirms the single-stage conditioned path, inward feather and `match_lighting:false`. The uploaded mask bytes match SHA-256 `d908a2a0dd81ef7868b8562b5066babf890db32b925d4197951db667c4263ffe`.

All 49 frames, the full midpoint and a directly aligned shadow crop were inspected. **This is the preferred replacement showcase:** the black knight remains coherent, its base is complete, and the fuller shadow avoids the earlier narrow clipped-strip appearance. No new pale patch, colour washout or abrupt temporal discontinuity was observed. Fine staircase aliasing still follows the lower diagonal shadow edge, so the margin correction improves the appearance without establishing a flawless boundary. No further engine tuning was introduced. The clean removal remains the strongest main demonstration.

Evidence is in `artifacts/validation/app-replacement-margin/942e8b6f52314b65a7ec736d2e3c28d2`, including the actual result selected by its `role=result` asset, original job/graph, all-frame contact sheet, `critic-shadow-comparison.png` and execution checks. Recorded Comfy time is 91.515 seconds for this individual run, not a general latency promise. The descriptive exterior RGB difference is 1.009/255 and mean adjacent-frame interior change is 1.021/255; these numbers do not substitute for the visual judgment.

## Hosted Comfy Cloud verification scope

The static replacement app job `5bf5ddd741ed4103b51960fe884b98b3` executed on genuine hosted Cloud with local preparation/compositing. Its stable black object resembles a bishop or crown, rather than the requested horse-head knight; use it as execution proof, not prompt-faithful replacement showcase.

Tracked removal `c7c635d64f7a4f5db022755722f6f3c3` completed 49 frames at 576×1024/24fps (0–2.0417s), using exact local SAM2 mask initialization and native Cloud two-stage diffusion. The aligned midpoint shows the car removed and a clean reconstructed ledge/window. All49 frames were decoded for a contact sheet and metrics; this review does not claim full temporal playback scrutiny. The full bundle passed CRC, all3 prepared-input hashes, executed-graph equality and tracker/margin provenance checks. Source audio is present, but exact synchronization was not established.

The original 97-frame Cloud request remains a recorded execution-limit failure. Final generated-audio job `b1ddc70ea1b546b1879d18e4f91a1dfd` was cancelled at the user’s request during output download, with no completed result. Its audio path is implemented but not end-to-end verified. Further Cloud testing stopped as requested.
