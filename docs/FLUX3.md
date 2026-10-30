# Native FLUX3 Image Klein implementation

Source implementation dated 29 October 2026. Quality-profile generation,
reference editing and protected-pixel checks have live application evidence in
the retained review record. This does not validate every precision profile
or input combination.
Public execution uses a configured Local ComfyUI host with the exact native
nodes and model files. That CUDA host can be separate from the lightweight UI/API
computer. These profiles are not advertised through hosted Comfy Cloud. Recorded
private GPU proofs remain evidence of their actual execution environment, not an
independent PC installation proof.

## Two explicit precision profiles

| Profile | Generator / encoder | Prompt expansion | Sampling |
| --- | --- | --- | --- |
| `flux3-klein` — Quality | Distilled BF16 / Qwen3VL 4B BF16 | Native Qwen3.5 9B FLUX3 INT8 ConvRot | Euler, simple, 16 steps, CFG 1 |
| `flux3-klein-int8` — Compact | Distilled INT8 ConvRot / Qwen3VL 4B INT8 ConvRot | Native Qwen3.5 9B FLUX3 W4A8 | Same default sampler and steps |

“Quality” names the higher-precision configuration; it is not a measured victory
over the compact profile. Both use the official distilled checkpoint, not the
separately published base/fine-tuning checkpoint. Negative prompts and CFG values
other than 1 are rejected. The existing `flux-klein-4b` remains a separate, fast
Apache-2.0 baseline and its recorded workflows are not rewritten.

The implementation follows the official native [text-to-image template](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/image_flux3_klein_distilled_t2i.json)
and [edit template](https://github.com/Comfy-Org/workflow_templates/blob/14220b8bd3e86baa852959f17039613191e66656/templates/image_flux3_klein_distilled_image_edit.json).
The pinned ComfyUI source already contains the required native FLUX3 and Qwen3.5
implementations. Native loaders, encoders, reference latents, diffusion and VAE
decoding remain ComfyUI operations. OpenFrame's helpers prepare captions, masks
and padded image canvases, then save an optionally composited PNG.

## Inputs and bounded controls

Both profiles accept `create-image` and `edit-image`, batches of 1–4, and output
dimensions 256–4096 in multiples of 16. Catalogue resolution presets expose
768, 1024, 1536, 2048 and 4096; these are request bounds, not a promise that every
4K/multi-reference batch fits a particular GPU or preserves equal quality.

Up to ten total reference images are ordered as source first (for image edits),
then `reference_asset_id`, then `reference_asset_ids`. The source counts toward
the limit. Every reference is independently scaled without changing its aspect
ratio. `image_reference_megapixels` defaults to 1, accepts 0.25–4 per image, and
the aggregate budget cannot exceed 16 megapixels. References guide generation;
they do not guarantee exact identity, lettering, logo or product preservation.

`image_prompt_mode: "expand"` requires the selected native prompt-upsample
checkpoint. It receives the ordered images, short request and layout constraints;
there is no silent raw-prompt fallback. Its system instruction is an OpenFrame
adaptation, not a claim to reproduce the exact public leaderboard configuration.
`"caption"` skips this dependency and requires an explicit scene/edit caption of
at least 80 characters. Job metadata retains the original request, expanded
caption, exact final model prompt, system instruction and generation parameters.

`image_layout` contains at most 32 elements. Each has a unique lower-case `id`
and `description`. Coordinates are integer `[top,left,bottom,right]` in 0–1000,
with positive area. A generation element has `bbox`. An edit element has
`source_reference`, `source_bbox` and `target_bbox`; a null target removes the
selected element. A new element has a target and no source. The helper appends
the exact [official bounding-box JSON format](https://docs.bfl.ai/flux_3/flux3_image_bounding_boxes)
after caption expansion so the language model cannot silently alter coordinates.
These boxes guide layout; they are not hard edit masks.

## Exact source-pixel protection

For `edit-image`, attach a source-size grayscale mask and select:

- `image_preservation: "outside-mask"`: white is editable; protect the exterior.
- `image_preservation: "inside-mask"`: white is protected; edit the exterior.
- `"none"`: ordinary generative editing; no pixel-protection guarantee.

New preservation graphs VAE-encode the original-size source and constrain native
sampling with its editable mask, rather than regenerating a full random canvas
and pasting the original over a differently positioned object. The source is
padded only to the 16-pixel model grid, never resized for this step. The decoded
output is cropped back to the original dimensions. Explicit final compositing
still provides pixel protection; reference conditioning and a lossy VAE alone
cannot. `mask_feather` is applied inward on the editable side. Fully
protected decoded 8-bit RGB pixels and source alpha are copied into the PNG;
this does not preserve a JPEG's compressed bytes or guarantee a convincing seam.
For a product cutout, a white product mask plus `inside-mask` protects the product
while a new environment is generated around it. Review shadows and boundaries.
For a tight product mask and a substantially different background, use
`mask_feather: 0`: an inward feather on the surrounding editable area also
retains an old-background strip, which can create a halo. In the controlled lamp
example, describing only the new background removed duplicated generated
object edges, and changing feather 6 to 0 removed that halo while keeping all
102,794 protected pixels exact. A binary mask can still have fine raster-edge
aliasing. These are explicit recipe choices, not automatic prompt rewrites or a
general guarantee of seamless compositing; see the retained comparisons in
[desktop validation](DESKTOP-VALIDATION.md).

The new mask loader reads PNG mask values directly. This avoids a confirmed
pinned native image/video-decoder case where an 8-bit grayscale mask's white 255
became 0.996108949, allowing a small unwanted blend into protected pixels. Both
8-bit and 16-bit grayscale intensities are normalized without thresholding. Stored
graphs retain their recorded loader and sampling behavior.

For `expand-image`, the full-resolution padded source is VAE-encoded as the
sampler's starting latent. `SetLatentNoiseMask` permits denoising only outside
the original rectangle; batches repeat that anchored latent explicitly. The
native [KSampler inpaint wrapper](https://github.com/Comfy-Org/ComfyUI/blob/79cf64c21a1dba50749945ba9fe2e3a692f45438/comfy/samplers.py#L630)
restores the known source latent during each denoiser call using the model's
noise scaling. Reference conditioning remains present. Final original RGB and
alpha compositing is unchanged, with zero feather. This replaces the earlier
full-canvas random-latent approach, whose exact final copy exposed mismatched
window, book and desk geometry at the joins. The revised graph still requires
visual review; latent anchoring is not a guarantee of seamless extension.

New Expand graphs also enable an outside-only harmonic RGB correction after
decoding. It fits a smooth colour offset to the original boundary, propagates
that offset through the generated area, and returns to zero at the far added
canvas edges. The original RGBA is restored exactly. No image is warped or
blurred; only the correction field is smoothed. Transparent boundary colours
are weighted by source opacity. Work is bounded to 4096 pixels per side and a
fixed multiresolution iteration budget, processing each image in a batch in turn.
Stored graphs retain their earlier behaviour because the saver option defaults
to off. This treatment resolves the broad tonal joins in the controlled reading
room preview; the small window-sill geometry kink remains. It is not a repair for
incorrect generated geometry, and new scenes still require visual review.

## Weights, license and exports

All component filenames, immutable revisions, expected hashes and byte sizes are
recorded in `engine/image_models.py`, from the official [native HF package](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/tree/feef60b0aaf63a4773ace96636ebbcf43b881312).
The package's VAE is installed as `flux3-package-vae.safetensors`: although its
upstream basename resembles the older Klein VAE, the pinned bytes differ. This
alias avoids overwriting an older workflow's dependency. Expected upstream hashes
identify intended artifacts and are distinct from independent full-file byte
verification. Provisioning and observed output evidence are recorded separately.

FLUX3 uses the [FLUX Kommunity License 1.0](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy/blob/feef60b0aaf63a4773ace96636ebbcf43b881312/LICENSE.md).
It is conditional open weights, not Apache-2.0: qualifying commercial output
generation below US$5M annualized revenue is treated differently from other
commercial uses. Read the pinned terms and component notices. The gated package
requires operator authorization before model preparation; credentials are not
written into recipes or bundles. Weights remain on the configured ComfyUI host.

Job bundles retain the executed graph and caption provenance, relocate only media
filenames, include helper-node source, and list the exact compatible component
destinations. Caption-only graphs omit the unused prompt-expander requirement.
Hosted Comfy Cloud is not advertised for these profiles; select the configured
Local ComfyUI deployment. No proprietary model is substituted.
