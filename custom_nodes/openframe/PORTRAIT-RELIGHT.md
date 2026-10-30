# Qwen Portrait Relight on a Local ComfyUI host

This is the released Comfy Qwen Image Edit2509 Relight recipe plus an explicit source-background finish. It does not use a private worker service or a hosted Comfy Cloud route.

1. Use the ComfyUI commit recorded in `MODEL-REQUIREMENTS.json`. Its native Qwen, SAM3.1, `SCAIL2ColoredMask`, `FluxKontextImageScale`, `MaskComposite` and `ImageCompositeMasked` nodes are required. Keep the compatible Torch/torchvision/Transformers environment supplied by that ComfyUI installation.
2. Copy the bundled `custom_nodes/openframe` folder into ComfyUI and install its `requirements.txt` in **ComfyUI's** Python environment. The portrait alpha node uses CPU Transformers/ViTMatte directly; it does not require the separate Linux-only video-matting runtime. A suitable GPU is still needed for Qwen/SAM inference. Native Windows execution has not been independently exercised by this project.
3. Install every file listed in `MODEL-REQUIREMENTS.json` at its exact `destination`. This includes the Qwen2509FP8 generator, FP8-scaled encoder, VAE, Edit2509Lightning4V1.0 and Relight LoRAs, the native SAM3.1 checkpoint, and all three files under `models/matting/vitmatte`. No inference-time downloads or alternate-model substitutions occur. Check the listed upstream hashes; export declares expected hashes but does not certify files you install yourself.
4. Restart ComfyUI, import `workflow_ui.json` or the API workflow, and supply the opaque portrait under the source filename in `manifest.json`. One clearly visible person is supported. There is no additional lighting map, hand-painted mask or appearance reference in this profile.

The source is center-fit to the native FluxKontext resolution bucket. The final output preserves that conditioning canvas, not the original file dimensions. Native SAM independently selects the source and generated person; fixed12px trimaps and CPU ViTMatte refine soft alpha. The native graph multiplies these alphas and composites the generated foreground over the scaled source. Both the raw render and finished result are saved. Missing person detections fail explicitly.

Four Euler/simple steps, CFG1, denoise1, AuraFlow shift3 and the released LoRA order are fixed. Direction/color/softness remain generative instructions rather than calibrated physical lighting. Facial/hair details and fractional edges can change. Post-render brightness is an explicit encoded-RGB multiply/clamp **after** compositing; nonzero values also change the restored background and may clip highlights. It does not recompute shadows.

The native CPU alpha helper was compared on the retained portrait using Transformers5.21.0 against the original isolated4.57.1 proof: max float-alpha difference8.05e−7, mean3.06e−9; exact confident-interior1/exterior0. Some16-bit rounding differs, so this is not a bit-identical cross-version guarantee. Other package versions have not been independently accepted.

Licenses remain separate: MIT workflow template, Apache2 Qwen/ViTMatte components, and the SAM License for SAM materials. Read the included notices and each pinned model's terms. No model weights are redistributed in the recipe bundle.
