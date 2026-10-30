# Focused image, video and VFX app reference

This revision extends the original video studio with separate image and video applications. The user chose Higgsfield as the explicit visual reference and removed Canvas and unrelated utility apps from the requested product. Alternative design directions are out of scope. The focused desktop screens and reference captures are implemented. Current desktop evidence is recorded in DESKTOP-VALIDATION.md; the earlier video-studio validation in DIRECTION.md does not verify these new screens. The user explicitly excluded further mobile work on 29 October 2026.

## Evidence

Signed-in reference pages were inspected in the Codex browser on 2026-10-29. Screenshot, accessibility snapshot and rendered body HTML are stored together under the retained review record. These raw captures are local research material and are excluded from release packaging. Login state is used only through the browser; no session cookies or account tokens are exported.

| Page | Captured components | Evidence prefix |
| --- | --- | --- |
| [Image generation](https://higgsfield.ai/ai/image?model=soul-v2) | Empty state, floating composer, model list, ratio menu, asset picker | `codex-image-*`, `codex-soul-default` |
| [Soul presets](https://higgsfield.ai/soul) | Named style links and18 rendered public gallery examples with exact prompt associations | `codex-soul-presets` |
| [Characters](https://higgsfield.ai/character) | Character landing and upload instructions | `codex-character-default`, `codex-character-upload` |
| [Genjutsu](https://higgsfield.ai/ai/video?model=genjutsu) | Motion transfer, object swap, source drawer, model menu, style workspace, custom reference and selected style | `codex-genjutsu-*` |
| [Popcorn](https://higgsfield.ai/popcorn) | Auto, manual scene inputs, Instadump dialog, output count and ratio menus | `codex-popcorn-*` |
| [Apps](https://higgsfield.ai/apps) | Catalog hierarchy and public app cards | `codex-apps-default` |
| [Background remover](https://higgsfield.ai/apps/image-background-remover) | Upload form and example comparison | `codex-app-background-remover` |
| Influencer, Marketing, Katana, Cinema | Earlier interaction-state and rendered HTML captures, including nested selectors | `firefox-influencer-*`, `firefox-marketing-*`, `firefox-katana-*`, `firefox-cinema-*` |

Reference screens have different layouts. Do not turn every application into the same generic form or a combined canvas. Image generation uses a centered visual hero and floating composer. Characters use a large upload surface and saved reference gallery. Genjutsu and Influencer use a narrow control panel and a larger media workspace. Popcorn keeps separately editable numbered scenes inside its composer. Mini-apps have individual launch forms reached from a category catalog.

## Measured styling

- Existing studio fonts: self-hosted Inter UI and Space Grotesk700, with local license files. Genjutsu's “Turn one video into many” heading computed as Space Grotesk700,30px font size,34px line height and−1.2px letter spacing.
- At the1063px reference viewport, Genjutsu's workspace begins at x361 and spans669px. Its hero wrapper is456.375px tall, with a448px text column. The captured narrow workspace places media above copy; the DOM uses a wider container breakpoint to switch to a row.
- Soul composer rendered classes specify background#27292C,20px corner radius and15px prompt text. Its extracted wordmark is a standalone sanitized SVG; local reference media remains optional.
- Overall reference treatment: near-black work area, charcoal raised controls, small neutral borders, subdued secondary labels, lime generation action. Rounded upload areas and media cards vary in radius; avoid flattening every surface into one generic card style.
- Exact page-specific image and video URLs, title associations, preset prompts and observed layout classes are recorded in `docs/reference-*.json`. Values inferred from screenshots are not interchangeable with computed CSS measurements.

## Functional adaptations

OpenFrame uses its own navigation, saved projects and compute controls. It names the actual open model used by each action. Public reference examples are distinguished from generated OpenFrame outputs. Commercial model names, credit counts and subscription claims do not imply corresponding backend support.

Character sets use up to four reference images with FLUX.2 Klein conditioning. They do not train an identity model. A consistent-identity outcome is not guaranteed. Motion transfer uses Wan Animate; supported masked edits use LTX2.3 or Wan VACE; image matting uses BiRefNet. Duration, resolution and reference counts follow the selected backend profile rather than Higgsfield's advertised limits.

Source examples can be cached with `scripts/fetch_reference_assets.py`; downloads are bounded and reuse the existing hash cache. The generated local media manifest and raw reference captures are not release assets. The repo retains observed public URLs so the research can be reproduced deliberately.

## Validation boundary

All focused implementation must be finished before product testing, builds, inference or extensive UI QA. Then verify routing, separate document state, upload flows, supported model settings, submitted job payloads, progress, retry/cancel, downloads and workflow export. Compare relevant screenshots at matching viewport sizes. Cloud wiring can be inspected, but live Comfy Cloud rendering is excluded by the user's instruction. Report actual measured discrepancies and runtime limitations; do not claim the entire commercial product has been recreated or that untested paths work.
