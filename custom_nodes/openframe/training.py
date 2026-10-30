"""Comfy output node for bounded training on a configured Linux CUDA host."""
import json
from pathlib import Path
import re
import folder_paths


class OpenFrameCharacterCaption:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"caption": ("STRING", {"multiline": True}), "trigger_token": ("STRING", {"default": "ofperson"})}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "apply"
    CATEGORY = "OpenFrame/Character"

    def apply(self, caption, trigger_token):
        if not re.fullmatch(r"[a-z][a-z0-9_]{3,31}", trigger_token):
            raise ValueError("Invalid character trigger token")
        if not re.search(r"\b" + re.escape(trigger_token) + r"\b", caption):
            caption = f"{trigger_token} person. {caption}"
        return (caption,)


class OpenFrameTrainCharacter:
    @classmethod
    def INPUT_TYPES(cls):
        try:
            import torch
            from engine.training_runtime import training_status
            ready, detail = training_status(folder_paths.models_dir)
            if ready and not torch.cuda.is_available():
                ready, detail = False, "Character training requires a CUDA-capable ComfyUI host."
        except ImportError:
            ready, detail = False, "Install the bundled OpenFrame engine package on the ComfyUI host; see CHARACTER-TRAINING-RUNTIME.md."
        return {"required": {"request_json": ("STRING", {"multiline": True,
            "openframe_training_available": ready, "openframe_training_detail": detail}),
            "dataset_json": ("STRING", {"multiline": True})},
            "optional": {"loss_masks_json": ("STRING", {"default": "[]", "multiline": True})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "train"
    CATEGORY = "OpenFrame/Character"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def train(self, request_json, dataset_json, loss_masks_json="[]"):
        import comfy.model_management as management
        from comfy.utils import ProgressBar
        from engine.training_runtime import run_training
        paths, root = [], Path(folder_paths.get_input_directory()).resolve()
        for filename in json.loads(dataset_json):
            candidate = (root / filename).resolve()
            if not candidate.is_relative_to(root) or not candidate.is_file():
                raise ValueError("Training photographs must be uploaded Comfy inputs")
            paths.append(str(candidate))
        mask_paths = []
        for filename in json.loads(loss_masks_json):
            candidate = (root / filename).resolve()
            if not candidate.is_relative_to(root) or not candidate.is_file():
                raise ValueError("Training loss masks must be uploaded Comfy inputs")
            mask_paths.append(str(candidate))
        management.unload_all_models()
        management.soft_empty_cache()
        progress = ProgressBar(1000)
        def report(value, stage):
            management.throw_exception_if_processing_interrupted()
            progress.update_absolute(round(value * 1000))
        def cancelled():
            management.throw_exception_if_processing_interrupted()
            return False
        result = run_training(json.loads(request_json), paths, report, cancelled, model_cache=folder_paths.models_dir, mask_paths=mask_paths)
        return {"ui": {"openframe_training": [result]}}


class OpenFrameRegisteredCharacterAdapter:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "lora_name": ("STRING",), "sha256": ("STRING",),
                             "strength_model": ("FLOAT", {"default": 1, "min": 0, "max": 2})}}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Character"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # Recheck registered bytes even if a cached filename is reused.

    def load(self, model, lora_name, sha256, strength_model):
        import hashlib
        from nodes import LoraLoaderModelOnly
        if not re.fullmatch(r"openframe/[a-zA-Z0-9-]{16,64}/character\.safetensors", lora_name) or not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ValueError("Use a registered character adapter and its recorded checksum.")
        path = folder_paths.get_full_path_or_raise("loras", lora_name)
        with open(path, "rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != sha256:
                raise ValueError("The registered character adapter bytes differ from the training receipt.")
        return LoraLoaderModelOnly().load_lora_model_only(model, lora_name, strength_model)


NODE_CLASS_MAPPINGS = {"OpenFrameCharacterCaption": OpenFrameCharacterCaption, "OpenFrameTrainCharacter": OpenFrameTrainCharacter,
                       "OpenFrameRegisteredCharacterAdapter": OpenFrameRegisteredCharacterAdapter}
NODE_DISPLAY_NAME_MAPPINGS = {"OpenFrameCharacterCaption": "OpenFrame · Character trigger", "OpenFrameTrainCharacter": "OpenFrame · Train FLUX3 character",
                              "OpenFrameRegisteredCharacterAdapter": "OpenFrame · Verify and load character adapter"}
