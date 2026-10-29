# Competition package

## Positioning
OpenFrame turns a video and a painted mask into a reproducible ComfyUI VFX job. Users choose an LTX profile and compute location, inspect the original/result, then take the exact workflow and settings with them. Other model families are separate selectable profiles. The user-facing interface makes ComfyUI accessible; the workflow remains inspectable and reusable.

## Prepared demonstration (70.40 seconds)
The captioned `openframe-demo.mp4` is 1920×1080 at 24 fps, with actual generated stereo audio in the native-audio segment. It uses the real application recording and reviewed generated results. The waiting interval is explicitly accelerated; short result clips are explicitly replayed.

- 0:00–0:18: removal result, model/compute controls and painted mask.
- 0:18–0:30: actual Generate action and accelerated GPU wait.
- 0:30–0:42: complete removal and replacement comparisons, including the corrected smooth shadow boundary.
- 0:42–0:50: actual exported 44-node, 71-link ComfyUI removal graph.
- 0:50–1:04: supported model/effect gallery and LTX native audio/video.
- 1:04–1:10: actual hosted Comfy Cloud result and explicit local preparation/compositing boundary.

The separate `openframe-source.zip` includes application/custom-node code, MIT license, dependency attribution, lockfiles and local setup. `openframe-examples.zip` includes portable removal/replacement/Wan-restyle graphs, inputs, expected results and provenance, plus a direct-engine native-audio example and hosted Cloud execution proof on our own generated source. The separately downloaded Higgsfield test footage is private validation material and is not included. Model weights and credentials are excluded. Standalone `openframe-vfx-before-after.mp4` and `openframe-replacement-before-after.mp4` provide uncluttered comparisons.

Release files are produced in `artifacts/release/`; validation recordings and research references remain outside the source archive. Public repository/deployment URLs must be added when publishing; no placeholder URL is presented as live.

Use only footage generated for the project or source media with documented permission. Public Higgsfield reference screenshots are design research, not claimed OpenFrame output. Avoid identities or marks without permission.

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
- A cloud compute option reduces the hardware barrier and exposes an honest connection path to Comfy services.
- Custom node code and dependency instructions can be reused independently of the UI.
- All model performance claims require measured evidence; cloud revenue impact is a product hypothesis, not an observed result.

## Eligibility evidence
The VFX bonus requires LTX to be the core video model. Demonstrate the actual LTX VFX graph and generated result. General generation under a different model is not evidence for that bonus. Keeping additional providers optional allows a fully open-weight path where all selected stages meet the relevant category's rules.

Official rules reviewed 2026-10-29: https://comfy.org/open-source-higgsfield/
