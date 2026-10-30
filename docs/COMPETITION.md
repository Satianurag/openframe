# Competition package

**Delivery status — 30 October 2026:** current public source, owned-media examples and the57-second demo are prepared separately from historical snapshots. The release manifest identifies exact payloads and hashes. User datasets, credentials, weights and evaluation-only footage are excluded.

Current scoped runtime/quality evidence is in [DESKTOP-VALIDATION.md](DESKTOP-VALIDATION.md) and [LTX-BOUNTY-AUDIT.md](LTX-BOUNTY-AUDIT.md). Final native GUI roundtrips and generated-edit audio integrity have passed as described below. This does not establish pixel-perfect editing, every Higgsfield feature, or every model/provider combination.

## Positioning

OpenFrame makes LTX video editing accessible through source selection, painted masks, explicit model controls, result comparison and portable ComfyUI workflows. The application connects to a user's Local ComfyUI or supported Comfy Cloud operations.

Hosted support is task-specific: LTX2.3 editing uses app-side preparation/compositing around hosted diffusion, while the new LTX2.5 Cloud adapter supports inpaint and emits native video with declared app-side preparation/finishing. The new 2.5 adapter has source/schema/CPU/bundle evidence, **not a live Cloud render claim**. Dedicated Water and exterior Relight remain Local profiles in the public configuration. Unsupported combinations fail explicitly.

## Final demonstration — 57.021333 seconds

`openframe-demo.mp4` is rendered at 1920×1080, 24 fps with 1368 video frames, H.264 video and stereo AAC audio; file size is 26,240,305 bytes. The video timeline is 57 seconds; measured container duration is 57.021333 seconds. Full decode and visual review of all eight sections passed. The native graph section uses the actual unobstructed Fit View; it demonstrates GUI import/export, not inference on this machine.

| Timeline | Actual content |
|---|---|
| 0:00–0:08 | LTX2.5 removal on owned footage |
| 0:08–0:14 | Public Local ComfyUI / Comfy Cloud selector |
| 0:14–0:22 | Owned LTX2.3 replacement example |
| 0:22–0:30 | Exterior Relight result |
| 0:30–0:36 | Applied lighting-sphere controls |
| 0:36–0:44 | Actual native 28-node Relight ComfyUI canvas |
| 0:44–0:50 | LTX native audio/video example |
| 0:50–0:57 | Cloud capability scope and portable exports |

The demo uses owned actual outputs and real UI/canvas captures. Replayed short clips must remain labelled. The selector demonstrates connection/capability controls, not a new successful Cloud render. The older demo's timestamps and 70.40-second duration do not describe this replacement.

## Verified evidence and limitations

- **Native GUI portability:** plate-fit and Relight canvases were imported and exported through the real ComfyUI GUI. All 52/28 nodes, 200/109 explicit inputs and 82/36 links match the executed API graphs after ID normalization. Added widget values equal declared native defaults. No local inference or model downloads were used for this check.
- **Generated editing audio:** the reviewed LTX2.5 case produced 49 frames and non-silent stereo 48 kHz audio from a silent source; final/raw decoded audio matches. The 2.010-second audio and 2.041667-second video reflect the causal audio-latent lattice. Integrity passed; perceptual sound quality is not established by that check.
- **Exterior Relight:** the 49-frame owned stream case retained coherent rock/stream layout with changed shading and cast shadows, without a sphere imprint or obvious temporal flash. Fine texture/water detail regenerated; the 512×320 source was center-fit and upsampled to 1280×704. This is not calibrated-angle, material or pixel-identity proof.
- **Replacement finishing:** the 97-frame private plate-fit case kept the cuboid through the daylight-to-tunnel transition and improved integration; a faint sill mismatch and possible fine-detail drift remain. Its private source/result footage is excluded from the public showcase. The public demo uses separately owned replacement material.
- **Weather:** a 49-frame private Water comparison retained the overall McLaren silhouette and arm motion with visible rain/wet surfaces; small-detail and parking-line drift remain. This is scoped evidence, not an exact-preservation guarantee or public footage clearance.

## Versioned delivery

The coordinated build targets `openframe-source.zip`, `openframe-examples.zip` and `openframe-demo.mp4`. The source archive includes application/custom-node code, its license, dependency attribution, lockfiles and Local/Cloud setup. The examples archive contains selected owned input/output media, portable workflows, model/dependency manifests and provenance; its final manifest determines the actual included cases. Refreshed historical derived canvases retain their unchanged API graphs/media.

Validation recordings and research references remain outside the source archive. Use only project-owned footage or source media with documented permission; public Higgsfield screenshots are design research, not claimed OpenFrame outputs. Private downloaded Higgsfield footage, local credentials and weights are excluded. Public repository/deployment URLs must be added when publishing; no placeholder URL is presented as live.

## Submission assets

- Application source, OSS license and local setup instructions.
- Exported runnable ComfyUI workflow, model/dependency manifest and a reproducible example.
- Actual input/output clip and <=2 minute explanation/demo.
- Optional runnable deployment link.
- Social post linking the demo and tagging #OpenSourceHiggsfield.
- User completes registration/submission and approves any public posting. This build does not submit forms or post on the user's behalf.

## Comfy ecosystem contribution

- Editable workflow export lets users extend jobs in ComfyUI.
- Saved recipes and explicit model settings make examples shareable.
- Task-scoped Comfy Cloud support offers a direct connection path with its preparation/finishing boundary disclosed.
- Custom node code and dependency instructions can be reused independently of the UI.
- All model performance claims require measured evidence; cloud revenue impact is a product hypothesis, not an observed result.

## Eligibility evidence

The VFX bonus requires LTX to be the core video model. Demonstrate the actual LTX VFX graph and generated result. General generation under a different model is not evidence for that bonus. Show the exact LTX profile, workflow dependencies and applicable weight licenses; optional non-LTX utilities are not evidence for the LTX bonus.

Official rules reviewed 2026-10-29: https://comfy.org/open-source-higgsfield/
