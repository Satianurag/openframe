# Prompt-selected video alpha

Status: source complete, runtime validation pending. No new model download, build or inference was performed during this implementation phase.

`sam3.1-vitmatte` / `semantic-matte` takes the original video and a description of the **foreground to keep**. The official SAM3.1 multiplex predictor detects and tracks the described concept. Its selected masks become deterministic trimaps: eroded foreground is known opaque, outside the dilated support is known transparent, and the boundary band is unknown. ViTMatte Base estimates soft alpha in that band. The saver combines alpha with original RGB; it does not generate replacement content or remove an object by inpainting. A transparent VP9 WebM and separate grayscale mask are returned. Video encoding can change decoded RGB through chroma conversion; this is not a bit-exact RGB container claim.

This follows the published [Matte Anything](https://github.com/hustvl/Matte-Anything) segmentation-to-trimap pattern with the newer temporal SAM3.1 selector. It is not a benchmarked joint model or a claim of current matting leadership. ViTMatte refines each frame independently, so fine-alpha flicker, background color spill and selection errors need actual full-clip review. All visible instances matching the concept can be selected; the limit is 16 simultaneous instances. An entirely empty selection fails clearly. Empty individual frames stay transparent and are recorded, rather than carrying an invented foreground forward.

The profile preserves native even source dimensions and FPS, supports 1–241 frames up to 1920×1088 in either orientation, and accepts a 1–200-character subject prompt. `trimap_radius` is 1–64 output pixels (default 12); `subject_confidence` is 0.1–0.9 (default 0.5). These controls respectively change the unknown boundary band and actual detector acceptance threshold. Source audio can be retained. No extra reference, painted mask or uploaded audio is consumed.

## Exact components and access

| Component | Pin / size | Terms |
|---|---|---|
| [SAM3.1 official checkpoint](https://huggingface.co/facebook/sam3.1) | `daa63191845a41281374e725f4c9e51c7a824460`; 3,502,755,717 bytes | Manual access approval; custom SAM License, not Apache |
| [SAM3 official source](https://github.com/facebookresearch/sam3/tree/f1647e8d0c1d280991f4d1b7d974c2704537fe66) | `f1647e8d0c1d280991f4d1b7d974c2704537fe66` | Retain the upstream SAM License |
| [HUST ViTMatte Base Composition-1k](https://huggingface.co/hustvl/vitmatte-base-composition-1k) | `bf486d01a7d9e3dbcc8400f7942835caf0eaf76e`; 386,836,309-byte checkpoint | HF weight card declares Apache-2.0; [original source](https://github.com/hustvl/ViTMatte) is MIT |
| [Transformers ViTMatte implementation](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/vitmatte) | 4.57.1 | Apache-2.0 |

Expected SHA-256 values and config sizes are in `engine/matte_models.py`. Provisioning is explicit on the configured Linux CUDA ComfyUI host; inference runs offline and never downloads missing weights. The runtime uses a separate environment for SAM3's NumPy 1.x requirement and ViTMatte's pinned Transformers implementation, without downgrading ComfyUI. RGB and alpha cross that subprocess boundary through anonymous RAM-backed files, without writing a temporary frame dataset. The source decoder and returned tensors still require bounded host memory. SAM tracking is unloaded before ViTMatte refinement. Cancellation terminates the subprocess; the operation has a one-hour budget.

The pinned SAM3.1 session dispatcher passes `offload_state_to_cpu=False` to a multiplex method whose signature lacks it. Our explicit compatibility wrapper removes only that unsupported keyword; supported arguments and checkpoint loading remain upstream behavior. The graph records this adaptation, model revisions, instance counts, empty frames and selected controls.

Newer alternatives were considered rather than assumed available: [VideoMaMa++](https://github.com/cvlab-kaist/VideoMaMa-PlusPlus) and [MatAnyone-E](https://github.com/Shuyun-Wang/MatAnyone-E) had not released runnable code/checkpoints at the 29 October 2026 review. [SAM2Matting](https://github.com/FudanCVL/SAM2Matting) has a released direct path but declares CC-BY-NC-SA research terms. No additional research-only stack was added. Automatic LTX AlphaGen remains a separate operation and cannot choose its object from text.
