# Validation scope

OpenFrame distinguishes source/contract checks, real model execution, visual review, desktop interaction and native ComfyUI import/export. A successful job is not automatically a quality pass. The summaries below describe bounded reviewed cases, not every possible source, prompt, model or provider.

## LTX VFX

- **Removal:** owned vase cases were reviewed across49 frames at1024×640/24fps using matched LTX2.3 and LTX2.5 IC-LoRA paths. Removal and boundary/lighting correction passed the scoped review. Filling an occluded area is generated reconstruction, not recovery of hidden ground truth.
- **Replacement:** the owned chess-piece case passed49-frame shadow/boundary review after continuous-contour compositing. The later97-frame edited-start-image/plate-fit case retained a stable replacement and removed a visible lighting patch. Fine boundary/detail differences remain; this is not arbitrary geometry or identity preservation.
- **Generated edit audio:** LTX2.5 produced non-silent stereo48kHz audio from a silent source. Final and raw decoded audio match. The2.010-second audio versus2.041667-second video follows the native audio-latent lattice; signal checks do not establish perceptual sound quality.
- **Exterior Relight:** the49-frame stream example retained coherent rock/stream layout with changed shading and cast shadows, without a visible conditioning sphere or obvious flash. Fine texture/water detail regenerated. Its512×320 source was center-fit to1280×704; no exact pixel or calibrated lighting-angle claim is made.
- **Weather:** the released Water recipe produced visible rain/wet surfaces over49 frames while retaining overall vehicle silhouette and foreground arm motion. Fine details and parking lines drift. Earlier latent/Canny-only failures remain failures.
- **Exports:** API graphs, native canvas graphs and input-inclusive bundles were checked against recorded execution. Real native GUI import/export preserved explicit values/links for representative LTX removal, replacement, native audio, plate-fit and Relight graphs. Missing local weights remained visible; GUI import is not local model execution.

## Direct Comfy Cloud

Actual hosted LTX2.3 generation and49-frame masked editing completed using CLI OAuth. That adapter returns intermediate frames; the app performs source/mask preparation, final compositing, audio and encoding. A reviewed replacement had a bishop/crown-like silhouette instead of the requested horse-head knight: runtime passed, precise shape adherence did not. A longer97-frame request hit the hosted execution-time limit; a separately requested49-frame case completed. These observations are not a universal service limit.

The current LTX2.5 Cloud adapter is **inpaint-only**. Native hosted nodes can return a final composite video; preparation/tracking and selected lighting/plate-fit/encoding finishes remain explicitly app-assisted. Catalogue/schema/CPU/export checks passed. A new live LTX2.5 hosted run and account-specific API-key execution have not been demonstrated. Unsupported tasks and unavailable exact models fail explicitly.

## Application and transport

Durable queues, asset protection, cancellation/retry, immutable recipe reuse, source intervals, exports and sequence recovery have targeted integration checks. Completed sequence video/speech outputs survive narration, audio or caption corrections where applicable. Popcorn ordered results/handoff, Ads narration/captions/assembly, Billboard image-to-video dependency and visual-planner proposal review have scoped desktop evidence.

Configured Local HTTP/node transports were exercised on controlled Linux CUDA evaluation hosts. This is not certification of a clean installation on every independent PC, native Windows/Linux browser combination or Mac model-inference performance. Hosted Cloud is a separate provider with its own model catalogue and limits. No alternative provider is silently substituted.

## Quality limits outside the core

Katana's optional EditVid recipe retained the reviewed two-person choreography over241frames/24fps (10.041667seconds), with face/hand trails and regenerated detail. It is Local-only and requires non-commercial9B weights. Earlier LTX choreography failures were not promoted to passes.

Characters training/registry/native adapter loading execute, but trained-only likeness failed. One reference-assisted case improved likeness while copying reference framing/background and missing the requested waist-up composition. Recast and Influencer have explicit reference-cleanup/composite-support options; remaining halo, lighting and fine-detail limits prevent a universal realism claim.

These summaries preserve the distinctions between engineering readiness and visual acceptance. User datasets, model weights, private evaluation clips and raw execution records are not distributed. Public examples use separately selected owned media. See [LTX bounty audit](LTX-BOUNTY-AUDIT.md), [app capability inventory](APPS-CAPABILITY-AUDIT.md) and the profile-specific guides for additional constraints.
