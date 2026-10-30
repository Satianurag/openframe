# Optional Local EditVid for Katana

This is an optional source-inverted video stylization profile, not an LTX replacement or hosted Comfy Cloud workflow. The independent native port and original EditVid code are Apache-2.0; **the required FLUX.2 Klein 9B weights use FLUX Non-Commercial License v2.1**. Read and accept the pinned model license on Hugging Face before downloading. Apache code does not grant commercially unrestricted use of these weights. Weights are not bundled.

Use a configured CUDA ComfyUI host. Keep heavy weights and execution on that host, not the desktop UI laptop. Minimum consumer-GPU VRAM and an independent end-user PC installation have not been verified; no16GB compatibility claim is made.

## Pinned dependencies

- ComfyUI: `79cf64c21a1dba50749945ba9fe2e3a692f45438`.
- Native port: [CanFromEarth/ComfyUI_FLUX-Klein-EditVid](https://github.com/CanFromEarth/ComfyUI_FLUX-Klein-EditVid), revision `a58b02dd71e0a7d1f9e04276aeedeb9e1220bfcc`, Apache-2.0. Reuses `examples/editvid_native.json`; its tiled correspondence/attention adaptation is not claimed numerically identical to the official Diffusers implementation.
- Original method/code: [PLAN-Lab/EditVid](https://github.com/PLAN-Lab/EditVid), revision `ba40bed5b4bf63acb913e6be1fdc462df695e99e`, Apache-2.0.
- Transformer: `black-forest-labs/FLUX.2-klein-9B@92196c8e11f7b6cf2b7493e037d8c5345c559216`, `flux-2-klein-9b.safetensors` → `models/diffusion_models/`.
- Encoder: `Comfy-Org/Flux-2-Klein-9B@1138ce884c8e977cdacacbe779784fec4426bb3f`, `split_files/text_encoders/qwen_3_8b.safetensors` → `models/text_encoders/`.
- VAE: same Comfy repository/revision, `split_files/vae/flux2-vae.safetensors` → `models/vae/flux3-package-vae.safetensors`. That alias reuses the exact SHA-verified336,211,292-byte VAE already used elsewhere. No different VAE is substituted.

Total declared weights:34,874,913,636bytes; missing transformer+encoder:34,538,702,344bytes when the exact VAE is cached. See MODEL-REQUIREMENTS.json for sizes and hashes. Reuse matching cached files. The sampler checks the4096-hidden,8-dual-block,128-latent-channel distilled9B architecture. **4B, Base, FLUX3 and quantized alternatives are not supported by this profile.**

With the OpenFrame source installed in the host environment, `python -m engine.setup --comfy-dir /path/to/ComfyUI --model flux-klein-editvid --no-download` installs the node pack and pins the external port without weights. Review existing-checkout revision warnings; no existing checkout is reset. Once license access and available disk space are confirmed, rerun without `--no-download` to obtain missing pinned weights on that host. For a standalone bundle, install the pinned native port into `custom_nodes/ComfyUI_FLUX-Klein-EditVid`, copy the bundled `custom_nodes/openframe`, and place matching model files in their manifest destinations. Restart ComfyUI and check the Local provider from Settings. No private-worker SDK/account is needed.

## Recipe and bounds

Select EditVid in Katana; supply a video, an accurate original-scene description for inversion, and the desired style in Instructions. Separate image references, edited first-frame guides, masks and generated audio are not consumed. Source or silent audio is explicit. Four native steps, chunk4, anchor0.6, correspondence threshold0.4, cycle radius1.5 and token retention0.5 are fixed to the released preset.

The input node streams the requested interval into one native-resolution IMAGE batch without temporary media copies, looping or end padding. Native ImageScale then center-fits with Lanczos; aspect changes can crop the source and must be reviewed. Source SHA, trim, frame count and native dimensions are recorded. The output saver muxes the same selected source-audio interval, or silence.

Support is bounded to9–241frames at24fps, dimensions256–1024 on a16pixel grid and at most589,824 output pixels; native source≤2,097,152pixels. Rotated-container metadata must be normalized explicitly before use. Upstream chunking has no49-frame architectural ceiling: prior-chunk K/V and first-chunk anchors persist; per-chunk inversion trajectories are released and final latents accumulate on CPU. At241frames/1920×1080, the required input float batch is about6.0GB (decimal), plus weights/caches and output tensors; streaming prevents a second whole RGB decode buffer. This resource bound has one full-length private evaluation below; it is not a guarantee for arbitrary clips or lower-memory hardware.

The49-frame/2.042s fighters evaluation materially retained both performers, source timing and occlusion, with painterly shading. Fast hand/face trails, changed accessories and regenerated fine detail remained. A separately authorized full241-frame/10.041667s evaluation on H100 with64GiB host memory completed in804.45seconds. Every frame was reviewed: source performer order, grapple/throw/roll, rise/kicks and final fall remain aligned with the source, with the same fast-motion trails and regenerated detail limits. All241 decoded frames were distinct; source-audio correlation was0.999941 at zero lag. This is private hardware evidence using the native Local Comfy HTTP graph, not an independently installed public PC validation. Do not advertise identity-exact or artifact-free output.
