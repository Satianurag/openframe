# Paint region workflow

The original Paint the reviewed job changed the small book cover blue but did not deliver the requested yellow floral detail or broad brushstrokes. White daisies were explicitly requested, so their white color alone is not a failure. Protected pixels passed the original integrity check. This is an edit-detail problem, not evidence that preservation failed.

The optional `image_edit_focus=masked-region` path reuses [ComfyUI-Inpaint-CropAndStitch](https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch/tree/6005efc02f7745649118edd89cdd084c2b9bd3ae), specifically `InpaintCropImproved` and `InpaintStitchImproved`. The external plugin is GPL-3.0, pinned and installed separately; its implementation is not copied into the MIT node pack. Selected exports declare the dependency, install instructions and license. The upstream `example_workflows/inpaint_flux.json` uses FLUX.1 plus Alimama ControlNet; we reuse its model-independent crop/stitch nodes around our existing FLUX3 workflow, not its model stack.

Fixed settings are context factor1.2,1024×1024 sampling, bicubic enlargement and bilinear reduction. Original pre-resize, outpainting, hole filling, mask growth and stitch pre-blending are off; padding is16 and processing uses the upstream compatible CPU path. These are not new user tuning controls. The baseline's actual native crop is321×321 at(0,569), enlarged to1024×1024 for inference.

The cropped source conditions both FLUX3's reference and masked starting latent. Decoded output is stitched into the original canvas before the unchanged final original-RGBA compositor uses the original mask and feather setting. The original asset remains the recorded source. Existing full-frame requests build the identical prior graph. Region mode is restricted to distilled FLUX3 Quality/Compact, one source, outside-mask preservation and no additional references or spatial layout; incompatible inputs reject explicitly.

The controlled candidate retains the original prompt, seed271890,16steps,CFG1, native768×1024 output and feather6. Only region focus changes. No new model weights are required.

## Verification scope

Graph and API checks pass, including unchanged full-frame graphs and rejected incompatible requests. The deployed native CPU proof confirms the pinned plugin, original input hashes,1024² crop, batch2 stitch back to768×1024, unchanged source tensor and zero differences across736,792 strictly zero-mask RGBA pixels in each output. Additional pixels protected by inward feathering are outside that count. These outputs are constant-color contract fixtures, not generated examples; temporary images were removed.

Two initial probe harness errors—an absolute-path rejection and an API-versus-worker-ID path mismatch—are retained in the evidence logs. They required no production changes. Native proof and graph/API receipts are under the retained review record and the retained review record. Actual generated floral detail remains pending the separately reviewed UI submission.
