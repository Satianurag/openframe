# Third-party components and research

OpenFrame application code is MIT licensed. Models, runtime software and separately installed node packs retain their own licenses. Model weights are downloaded into the selected inference environment, not shipped in the application repository.

- ComfyUI: https://github.com/Comfy-Org/ComfyUI — inference runtime; GPL-3.0.
- Official workflow examples: https://github.com/Comfy-Org/workflow_templates — source/reference for native model graphs.
- LTX model/node documentation: https://github.com/Lightricks/ComfyUI-LTXVideo and https://github.com/Lightricks/LTX-2.
- Wan VACE: https://github.com/ali-vilab/VACE — alternative video conditioning model family.
- SAM2: https://github.com/facebookresearch/sam2 — optional temporal mask propagation; Apache-2.0.
- Inter and Barlow Condensed fonts: SIL Open Font License; packaged locally for the interface.
- Modal: https://modal.com/docs — GPU execution and persistent model cache.
- Comfy Developer Platform/SDK: https://docs.comfy.org/development/api-development/sdks — remote execution interface.
- Higgsfield public interface: https://higgsfield.ai — requested visual reference. OpenFrame is an independent project and does not claim affiliation.

The shipped model manifest and deployment source identify exact checkpoints and runtime revisions. Any additional vendored source must preserve its original license/attribution. Reference screenshots belong to research artifacts and are excluded from ordinary source packaging.
