# Recast: native SCAIL-2 validation

Actual desktop submission the reviewed case shows a **substantial banknote-performance improvement with an unresolved
compositing flicker**. The woman and blue blazer replace
the performer while printed, layered currency and the original sequence of grips,
forward hand sweep, lift and face occlusion remain recognizable. All 65 frames
were compared with the source, raw model output and final tracked support.
This resolves the conspicuous folding-fan substitution in the rejected Wan
Recast the reviewed case for this case; it is not a general guarantee
of exact human-object interaction.

## Actual route and provenance

- Desktop document: `/apps/recast?document=recorded-run`.
- Original source the reviewed case, same blue-blazer reference
  the reviewed case, source start 0, seed 315022.
- Native full-quality SCAIL-2 FP16 + DPO 1, Euler/simple, 40 steps, CFG 5, shift 5;
  no Lightx acceleration. Full driving RGB and identity-colored native SAM3.1
  masks condition the model. Automatic single-human selection replaces the old
  broad painted upper-body mask.
- Output: 576 × 1024, 65 frames at 16 FPS, 4.0625 seconds of video. One window;
  multi-window extension was not exercised by this job.
- NVIDIA H100 80 GB; recorded remote execution 765.136 seconds. This is observed
  latency for this request, not a throughput promise.
- Core `79cf64c21a1dba50749945ba9fe2e3a692f45438`; official template
  `14220b8bd3e86baa852959f17039613191e66656`. The exact 25-node executed graph and
  six pinned model requirements are retained in the receipt and bundle.
- Model/conditioning, mask strategy and literal banknote caption all changed
  from the old case. This is a practical pipeline repair comparison, not a
  one-variable model benchmark. The [reuse plan](research/recast-reuse-plan.md)
  records the upstream files, revisions, terms and rejected alternatives.

## What the review establishes

The raw decode already keeps currency instead of substituting a fan, and follows
the principal source wrist/bundle trajectories. The final original-plate composite
preserves much of the money because the automatic human mask excludes it. Both
factors contribute; the result does not establish that generative conditioning
alone preserves every printed note.

There is a visible local limitation: at frames 23–24 the tracked support omits the
forward hand, then includes it again at frame 25. The final output briefly uses
the warmer original hand and switches back to generated skin/detail. The person
track never becomes wholly empty, but this is **partial mask inconsistency**, not
perfect temporal segmentation. Fine finger anatomy, printed bill detail, facial
microexpressions and the original watch are not exact. The final allowed region
also clips parts of the wider generated blazer silhouette. No further generation was applied to hide these observations. Bounded tracking/compositing diagnoses are recorded below; this original receipt
and media remain unchanged.

The narrow diagonal brown/gray shape at the right edge of the frame-32 comparison
is a picture frame on the original bedside cabinet, confirmed in the source; it
is not a detached generated finger. The larger grips remain connected, with the
fine-anatomy limitations above.

## Media, masks and exports

- All three outputs decode to 65 frames: final result, final blend mask and
  explicitly labeled silent `uncomposited` diagnostic. The latter is encoded RGB
  before overlap color matching/plate compositing, not a lossless tensor dump.
- Native source-mask area: 128,607–225,552 pixels, no all-empty frames. The exported
  mask includes the separate 12-pixel edit margin and 6-pixel feather; it must not
  be mistaken for the raw SAM segmentation.
- Decoded protected-exterior mean absolute RGB error: 1.432/255; worst-frame mean
  1.778/255. Encoding contributes to these differences; this is not a perceptual
  score or a claim of lossless video preservation.
- Preserved source audio: aligned waveform correlation 0.989413 over 63,885
  compared samples at 16 kHz; timestamp-adjusted residual lag −0.741 ms. The
  nonzero original AAC start and output container padding are recorded separately.
- Local output SHA-256 values match the registered assets. The 2,627,554-byte
  full-media bundle passes ZIP CRC, source/reference input hashes and portable
  raw-output source-slot checks. API and UI graphs are retained. Expected model
  hashes are manifest requirements, distinct from these local media checks.
- Root also verified actual desktop playback to completion and visible final,
  mask and explicitly labeled raw links. First UI attempt `reviewed case` failed the
  old unconditional host mask requirement before inference; its evidence remains.
  The targeted optional-mask fix preserves required masks for legacy Wan and
  passed eight actual runner-preflight cases with the provider mocked.


contains `integrity.json`, five all-frame comparison pages, native interaction
crops, `hand-mask-22-25.jpg`, `projection-background-32.jpg` and both graph formats.
The original and generated identity media remain private validation material and
are excluded from public release assets. No additional inference is implied by
this receipt.

## Mask-flicker diagnosis (no additional diffusion)

The saved raw hand remains stable during the two-frame skin/detail switch. A
bounded CPU optical-flow support prototype was rejected: motion-consistency gates
left isolated mask islands and mottled skin. It is not production code.

A separate H100 tracking-only probe reused the pinned native checkpoint and the
existing remote source. Forward tracking reproduced the original mask areas
exactly. A reverse-frame pass, seeded by the actual last unexpanded forward mask,
also omitted the hand at frames 23–24 and began omitting it earlier at 20–22. All
65 masks were inspected. This is rejected as a repair. Total measured execution
was 10.94 seconds, including 4.36-second forward and 2.37-second reverse tracking;
it is not an extra SCAIL generation. No weights were downloaded.

The pinned [native SAM3.1 tracker](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy/ldm/sam3/tracker.py#L1580)
already contains high-confidence detection-based reconditioning, but its detection
guard stops detection once the configured object limit is occupied. An isolated
in-memory probe removed only that skip condition, retaining the existing score
(0.8), overlap (0.5), and new-identity limits. It retained exactly one track but
still omitted the hand at 23–24. This candidate is also rejected; no production
core file or deployment was changed. Tracking took 6.37 seconds, total execution
9.66 seconds. Evidence and exact function hashes are in `reconditioning-probe/`.

The [official SAM3 predictor](https://github.com/facebookresearch/sam3/blob/f1647e8d0c1d280991f4d1b7d974c2704537fe66/sam3/model/sam3_base_predictor.py)
provides corrective prompts and bidirectional propagation. Those controls are
not exposed by the pinned native `SAM3_VideoTrack` wrapper. Their existence does
not establish that either rejected automatic probe is equivalent to interactive
correction, or that this clip is now fixed.

### Official predictor support candidate

An existing, earlier semantic-matte app result on this source retained the hand at
the affected times. That motivated a same-source 65-frame/16-FPS binary-mask probe
using the already installed official SAM3.1 predictor at
`f1647e8d0c1d280991f4d1b7d974c2704537fe66` and cached
`facebook/sam3.1` checkpoint `daa63191845a41281374e725f4c9e51c7a824460`.
It used the existing app's `person` prompt and 0.5 output threshold. No ViTMatte,
new model download, or diffusion ran. This compares practical implementations;
it does not isolate checkpoint precision, predictor code and text vocabulary.

The official binary masks retain the hand at frames 23–24. All 65 source/mask and
saved-raw composites were reviewed: the local skin/detail switch is removed, no
new background mask islands were observed, and the banknote exclusion remains.
Decoded source RGB hashes match across the remote probe and local compositor.
The same margin 12, smooth-inward feather 6 and unchanged source/raw images were
used; every pixel outside the new alpha is exact before encoding. Existing
fine-anatomy and generated-garment boundary limitations remain.

Measured mask-only execution was 26.57 seconds on H100. The proposed correction
uses official predictor masks **only for final compositing support**; native
SCAIL conditioning remains unchanged. This is a candidate verified against the
saved encoded raw diagnostic, not yet a deployed end-to-end rerun. Evidence:
`official-mask-probe/{receipt.json,composite-proof.json,hand-comparison-21-26.jpg,
recomposited-existing-clip.mp4,all-frame-comparison-1.jpg…5.jpg}`. The preview is
silent and the original registered job/media are untouched.

### Explicit Influencer scene choice

The Influencer motion editor now distinguishes existing character animation from
`Keep source scene — performer replacement`. The latter explicitly selects
SCAIL-2 / `character-replacement`, with native automatic selection or a first-frame
mask override and original plate/audio. It does not rename native replacement
as reference-scene animation. Saved explicit model choices are retained. Actual
UI request-builder checks cover automatic/manual selection, legacy mask rejection
and legacy animation; a real API workflow export returned 200. No Influencer
render is implied by this source/contract check.

### Integrated support contract (pending full app rerun)

`recast_composite_tracking=official` now selects the existing isolated official
SAM runtime in binary-only mode, solely for final compositing. Its first-frame
instance must overlap the native selected performer with IoU at least 0.5; the
matched ID persists even if instance order changes. Unrelated matches fail; a
missing selected ID is never replaced by a bystander. The demonstrated source's
first-frame IoU is 0.973706. Recorded metadata includes the selected ID, overlap,
source/model revision, empty-frame list and the actual final mask semantics.

Missing/null values and old graphs remain native. Fresh automatic Recast and
Influencer source-scene selections opt into official support explicitly. Manual
mask overrides use native support; incompatible explicit API requests fail.
The first implementation was evaluation-only, added just the already cached official checkpoint,
and did not require ViTMatte weights. The same bounded memory-file transport,
GPU unload, cancellation and subprocess timeout are reused.

The 26-node official graph differs from the original 25-node graph only in the
added final-support node and saver-mask link. All native conditioning and sampling
inputs match the recorded baseline. CPU request/graph/instance-selection checks
and TypeScript compilation passed; see `official-support-contract.json`. A full
actual app rerun is still required after coordinated deployment.

## Public runtime completion and remaining validation

The resumed source work removes the private-worker requirement from official
Recast support without changing the predictor, first-frame matching, mask
conditioning or composite algorithm. A provisioned Linux CUDA ComfyUI host can
select its isolated interpreter with `OPENFRAME_SAM3_PYTHON`. The self-contained
node pack now carries its runtime constants and
`custom_nodes/openframe/RECAST-RUNTIME.md`; it no longer needs the private
deployment module or the application's engine package on the child Python path.
Native Windows/macOS official-predictor execution is not claimed. The same
configuration supports the existing semantic SAM3.1→ViTMatte app, which retains
its independent per-frame soft-alpha refinement.

Node capability metadata reports the configured runtime/checkpoint/CUDA-host
prerequisites. The app checks these before uploading or submitting a Local
official-support job. Fresh public Recast/Influencer selections use native support
unless checked official support is available; saved explicit selections remain
visible and produce a clear prerequisite error rather than silently changing
tracking. Manual-mask overrides still use native tracking. Model setup defaults
to the six native SCAIL requirements; the optional official support checkpoint
is requested explicitly. No runtime installs or model downloads were performed
for this portability change.

The official-support rerun was interrupted when project priority moved to LTX
VFX, so the full end-to-end repair remains unverified. All older banknote and
generated-explorer inputs/results are retained as **historical evidence only**.
The user's current requirement is fresh, relevant source/reference inputs from
current Higgsfield pages. Do not resubmit the old comparison requests or describe
them as the new showcase. Root will supply the fresh media and review their
source/reference provenance before any new GPU submission.

After the combined implementation freeze, validate in this order:

1. Bounded source/contract/export checks for Local capability failure, manual-mask
   rejection, exact legacy native graph preservation and official support's
   unchanged sampling/conditioning; check public bundles have the runtime guide
   and no private worker requirement.
2. One Recast UI job on a fresh performer/hand-object interaction source and a
   distinct fresh appearance reference. Preserve its original action, inspect
   every source/raw/final/mask frame and audio alignment, and distinguish source
   prop preservation from generated detail.
3. One AI Influencer `Keep source scene — performer replacement` UI job on fresh
   relevant assets, with explicit SCAIL/official support, actual saved scene
   choice and reuse. Animation in the reference scene remains a separate mode.

The fresh cases use inspected, current Higgsfield inputs. Recast pairs the
seated performer in the burning room with the
pale-shirt/tie full-body reference:1024×576,65frames at16fps,trim0,seed315030.
Influencer pairs the pale-shirt boxing video with a distinct moustached character
in a black leather coat:576×1024,69frames at24fps,trim3,seed315032. Its visible
3-second control aligns to69 model frames (2.875seconds). Both use40steps/CFG5
and explicit official final support, with native SCAIL conditioning unchanged.
The source boxing clip has no audio; that case cannot establish audio preservation.

Current native CPU ComfyUI schema/export inspection passes both26-node/42-link
graphs, the3-node semantic-matte graph and the1-node unexecuted Local training
template. It does not establish GPU execution: the CPU viewer truthfully reports
the Linux CUDA/companion runtime prerequisites unavailable. See
the retained review record; exact
drafts and provenance are in `recast-fresh`, `influencer-fresh` and
`semantic-matte-fresh` under the same validation folder. The additional matte
case uses the boxing source at native1080×1920,49frames/24fps,trim3 and the short
concept `person`; its completed all-frame alpha/hand-edge result is recorded below.

### Fresh Recast execution: support correction still required

Job the reviewed case completed the prepared65-frame request in
792.2seconds of recorded execution. All65 source/raw/final/support frames were
reviewed. The camera push, head turns and seated/clasped-hand action remain
recognizable; the replacement clothing is stable and the original fire, room and
chair remain. Source audio correlation is0.999953 at zero measured lag. Media
hashes, portable inputs and the full bundle CRC pass.

This is **not a clean visual pass**: on the final frame, official semantic support
loses the visible lower body and the compositor restores original black trousers
and red lettering over the correctly generated brown trousers. Nonzero support
falls from159,813 pixels at frame63 to122,266 at frame64, despite a consistent
object ID and no completely empty frame. The original result is retained. A
bounded native/official mask-only comparison and CPU recomposition are authorized;
no diffusion retry is planned. Evidence: `recast-fresh/actual/integrity.json` and
`late-boundary.jpg`. This clip has no held banknotes and does not revalidate that
historical interaction case.

### Fresh Influencer, semantic matte and retained-output correction

Influencer the reviewed job completed 69 frames in 826.9 seconds. All source/raw/final frames were inspected. Connected punches, retractions and guard timing follow the driving performance; the distinct black coat, green trousers and moustached appearance remain coherent. The original composite nevertheless **fails coverage**: source-only support cuts off the wider generated coat and rear shoe. Raw generation contains those parts. A thin white outline, flatter lighting and altered proportions are also visible in raw generation; support correction cannot be claimed to repair them. The source and result are silent. Portable input hashes, raw export slot and bundle CRC pass.

Semantic-matte the reviewed job is a **qualified 49-frame pass** on the fresh boxing source: native 1080×1920 at24fps, trim3, concept `person`, threshold0.5 and trimap radius12. Actual libvpx RGBA decoding confirms zero, full and fractional alpha across all49 frames. Head, hands, arms, trousers and rear shoe remain; courtyard, bench and cast shadow are removed without a large unrelated foreground blob or identity switch. Fine hair/shirt edge fringe remains. This is private GPU execution of the existing pipeline, not proof of an independently installed public Local host.

Approved mask-only probes reproduced Recast's loss: native source support at frames63/64 remains136,896/138,968 pixels while the official source predictor falls136,884→100,649. Matched generated-performer SAM passes meet first-frame source-actor IoU0.682 for Recast and0.730 for Influencer, with fixed object IDs and no empty frames. No diffusion or new model downloads occurred.

CPU recomposition unions native source, official source and matched generated-person supports before applying the existing margin12/feather6 once. All65 Recast and69 Influencer corrected frames were reviewed: the final trouser leak and clipped coat/shoe are repaired; no new large background blob or identity switch was observed. Every alpha-zero source pixel is exact before video encoding. Recast copies the retained result's audio packets. These are explicitly derived from already encoded raw generation, with an additional video encoding; original result/request/executed graph remain unchanged. Fine generated hands/face, the Influencer outline and original-shadow alignment limitations remain. The fresh Recast case contains no banknotes and does not establish a new held-object result.

The additive `official-union` production mode is source-complete. Saved `native` / `official` graphs are exactly preserved; only the new mode connects the decoded/overlap-matched generation to the support node. Both official passes select the same native first-frame actor with IoU≥0.5, failing on unmatched identity. Manual masks remain native-only. The union uses the same cached SAM checkpoint, no ViTMatte. Local availability is checked against both runtime prerequisites and the node's new optional input; no unavailable mode is silently substituted. Source checks cover single/multi-chunk acyclicity, exact old graphs, model requirements and the actual node against recorded failing masks. The deployed correction graph has now executed on both retained outputs. This component evidence is not a new end-to-end diffusion run; its separate receipt must not replace the original executed graph.

, the source/generated support probe folders, `recast-fresh/union-source-contract.json`, `recast-fresh/union-recorded-mask-regression.json`, and `semantic-matte-fresh/actual/integrity.json`.


### Actual deployed support correction — 30 October 2026

The deployed eight-node correction graph completed in 102.13 seconds for Recast and 80.92 seconds for Influencer. It ran the pinned native and official SAM trackers, matched source/generated identities, then composited the retained raw render. It did not execute a diffusion sampler or download weights. Both API and UI correction graphs, model requirements, actual tracker metadata and output hashes are retained under `.openframe/renders/<original-job>/postprocess/official-union/`.

All 65 Recast and 69 Influencer corrected frames were reviewed against the source and support masks. The final Recast trouser leak and Influencer coat/rear-shoe clipping are resolved. Recast's decoded audio is sample-identical to the original result; Influencer correctly remains silent. Existing source, raw and original result hashes and original job records are unchanged. The corrections include an additional lossy video encoding from retained raw media. Exact alpha-zero preservation is a pre-encoding compositor property, not a claim of pixel-identical H.264 backgrounds.

The result is a **support-coverage correction pass**, with generative limitations retained. Influencer's conspicuous white rim, flatter lighting, altered proportions and possible mismatch to the retained original cast shadow remain visible; it is not a polished photorealism pass. Fine Recast hand/face detail remains imperfect. The fresh seated case contains no banknotes, so it establishes no new held-object guarantee.

Separate registered derived videos are the reviewed case (Recast) and the reviewed case (Influencer), with masks the reviewed case and the reviewed case. Each new asset carries explicit `postprocess_repair` metadata linking the original inputs, raw generation, original result, corrective graph and hashes. These are not fabricated render jobs. The original app history remains unchanged and its original graph does not claim to have produced the corrected asset.

 Actual videos and both correction graph formats were verified through the normal workspace asset path. Private cloud execution does not establish a separately installed public Local CUDA host; the public runtime guide and capability checks remain distinct evidence.
