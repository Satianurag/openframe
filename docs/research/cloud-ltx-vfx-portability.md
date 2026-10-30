# LTX VFX: direct hosted Cloud boundary

Reviewed against the authenticated, read-only hosted catalogue on 2026-10-30. No Cloud render was submitted for this adaptation.

## Released sources reused

- [Lightricks two-stage LTX2.5 inpaint workflow](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/220e1d45aa0469f518e982102fca4dca92a61862/example_workflows/2.5/LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json): the canonical sampling graph, inpaint IC-LoRA, refinement, and optional edited-start-image conditioning remain the source of truth. Translation changes media utilities, not checkpoint/sampler selection.
- [ReAngle](https://github.com/Tekholms-LW/ReAngle/tree/d13a284274d13f8d915b147c41e9c07196da2bb5), Apache-2.0: an actual direct `cloud.comfy.org` integration using native LTX2.5 nodes. Its code performs source preparation locally, returns video chunks, then joins them and muxes audio locally. It is useful transport evidence, not an already-complete hosted VFX compositor. Its model substitution and chunk crossfades were not copied into OpenFrame.
- [PaintAPlate seam-field math](https://github.com/AInVFX/ainvfx-paintaplate/blob/31adafa85819b616c4f157dc88e6a96f5b9cfd9a/mathops.py), Apache-2.0: the explicit replacement plate-fit option reuses the attributed bounded color field. It runs locally after Cloud rendering; it is not presented as a hosted node.

The real hosted catalogue contains 3,858 nodes and the exact default LTX2.5 profile filenames, including its inpaint adapter. It contains native `LTXICLoRALoaderModelOnly`, `LTXVInpaintPreprocess`, `ImageCompositeMasked`, `CreateVideo`, `SaveVideo`, `LoadVideo`, audio and text-output nodes. OpenFrame utilities and a matching seamless-clone correction are absent. The exact LTX2.3 Relight adapter is also absent; Relight is not advertised as a Cloud operation. Filenames and schemas do not attest the provider's installed byte hashes or runtime revision.

## Implemented adapter

`engine/cloud_ltx25.py` supports **inpaint only**. The app prepares the selected source interval, generation mask, floating composite support, source waveform and optional edited full starting frame. Inputs use lossless RGB video/PNG/WAV. Native Cloud nodes execute the recorded sampling graph and produce a composited H264 CRF17 video, selected source/generated/silent audio, optional raw decoded video, and exact model-prompt text.

Static and optical-flow preparation need no local model runtime. Optional SAM2 still uses the explicitly configured local ComfyUI tracker initialized with the painted mask. This is not self-contained hosted SAM2. Prepared native composite masks are 8-bit, with at most 0.5/255 rounding error and unchanged exterior zeros.

Removal's recorded seamless-clone correction, explicit replacement plate fitting, and Standard/High bitrate targets require app finishing. The hosted graph additionally returns pre-composite PNGs and native audio; the app creates a separately named final result and retains the native video as a preview. Plate fitting consumes generated RGB and the original source/floating mask, followed by exactly one alpha composite. It never processes the already-composited preview. PNG generation is 8-bit, a disclosed difference from the local float pipeline. Native SaveVideo exposes CRF rather than the app's bitrate targets; those targets use the existing shared local encoder without a guessed CRF conversion.

Bundles contain the canonical local replay recipe, actual hosted API graph, a native Cloud canvas, prepared inputs and `CLOUD-PROCESSING.json`. Running only the native Cloud graph returns its native video, not any declared app-finished result. No rented-GPU relay or private worker is needed for this path.

## Evidence and limits

The bounded checks cover 17 graph/API cases against the real catalogue; exact CPU preparation/padding and alpha bounds for static and edited-first-frame inputs; actual native CPU source/generated/silent video encodes; portable API/UI input relocation, hashes and archive CRC; and eight existing Cloud transport regressions. The native CPU generated-audio case uses an already recorded waveform and does not perform inference. Additional plate-fit/Relight guards and public replay manifests have focused checks.

Private receipts are under the retained review record. They are intentionally excluded from public source archives. **There is no new live LTX2.5 Cloud execution, quality, timing, cost or cancellation pass.** Earlier LTX2.3 CLI-OAuth successes and workload timeout remain separately recorded. API-key SDK execution has no account-specific live verification claim. Provider time limits are not silently worked around by truncation, model substitution or another GPU service.
