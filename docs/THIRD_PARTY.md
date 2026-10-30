# Third-party components and research

OpenFrame application code is MIT licensed. Models, runtime software and separately installed node packs retain their own licenses. Model weights are downloaded into the selected inference environment, not shipped in the application repository.

- ComfyUI: https://github.com/Comfy-Org/ComfyUI — inference runtime; GPL-3.0.
- Official workflow examples: https://github.com/Comfy-Org/workflow_templates — source/reference for native model graphs.
- LTX model/node documentation: https://github.com/Lightricks/ComfyUI-LTXVideo and https://github.com/Lightricks/LTX-2.
- Wan VACE: https://github.com/ali-vilab/VACE — alternative video conditioning model family.
- Wan Animate and S2V: https://github.com/Wan-Video/Wan2.2 — purpose-trained character/motion and speech-to-video models, Apache-2.0. Animate's auxiliary YOLO detector retains its separate AGPL-3.0 terms; do not infer auxiliary licensing from the generator.
- FLUX.2 Klein 4B: https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8 — Apache-2.0; selected FLUX.2 autoencoder also Apache-2.0.
- FLUX3 Image Klein native package: https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy — FLUX Kommunity License 1.0, conditional open weights rather than Apache-2.0. See [component revisions and licensing scope](FLUX3.md). The application's prompt-expansion instruction is an original adaptation; this is not an exact leaderboard prompt reproduction.
- BiRefNet: https://github.com/ZhengPeng7/BiRefNet — foreground alpha extraction, MIT.
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M — public English speech voices, Apache-2.0.
- Qwen2.5 7B Instruct: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct — editable shot proposals, Apache-2.0.
- SAM2: https://github.com/facebookresearch/sam2 — optional temporal mask propagation; Apache-2.0.
- Inter and Barlow Condensed fonts: SIL Open Font License; packaged locally for the interface.
- Comfy Developer Platform/SDK: https://docs.comfy.org/development/api-development/sdks — remote execution interface.
- Higgsfield public interface: https://higgsfield.ai — requested visual reference. OpenFrame is an independent project and does not claim affiliation.

The shipped model manifest and Local runtime guides identify exact checkpoints and runtime revisions. Any additional vendored source must preserve its original license/attribution. Reference screenshots belong to research artifacts and are excluded from ordinary source packaging.

- Katana Canny preprocessing: `custom_nodes/openframe/restyle.py` adapts only the detector, resize/padding and tensor conversion from [Fannovel16/comfyui_controlnet_aux at a587a4c](https://github.com/Fannovel16/comfyui_controlnet_aux/tree/a587a4c1594524c1d2de5cd1a86cd868ff448e1c), Apache-2.0. The retained license is `custom_nodes/openframe/CANNY_LICENSE.txt` and accompanies portable node bundles. The LTX Union-Control adapter retains its separate LTX Community License.
