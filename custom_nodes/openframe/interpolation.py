"""Load the pinned LDF-VFI stack without implicit model-weight downloads."""
from pathlib import Path

import folder_paths
import comfy.model_management


class OpenFrameLoadLDF:
    @classmethod
    def INPUT_TYPES(cls):
        import nodes
        root = Path(folder_paths.models_dir) / "ldf-vfi"
        available = "LoadLDFVFIModel" in nodes.NODE_CLASS_MAPPINGS and all((root / name).is_file() for name in
            ("transformer/config.json", "transformer/diffusion_pytorch_model.safetensors", "Wan2.1_VAE_cond_v2.pth"))
        return {"required": {"tile_size": ("INT", {"default": 256, "min": 128, "max": 1024, "step": 8, "openframe_ldf_available": available}),
                             "tile_overlap": ("INT", {"default": 64, "min": 8, "max": 512, "step": 8})}}

    RETURN_TYPES = ("LDF_VFI_MODEL",)
    FUNCTION = "load"
    CATEGORY = "OpenFrame/Video"

    def load(self, tile_size, tile_overlap):
        import nodes
        loader = nodes.NODE_CLASS_MAPPINGS.get("LoadLDFVFIModel")
        if loader is None:
            raise ValueError("Install the pinned ComfyUI-Tween dependency before using FPS Boost")
        root = Path(folder_paths.models_dir) / "ldf-vfi"
        required = ("transformer/config.json", "transformer/diffusion_pytorch_model.safetensors", "Wan2.1_VAE_cond_v2.pth")
        if any(not (root / filename).is_file() for filename in required):
            raise ValueError("Provision the ldf-vfi profile on the selected GPU worker first. This node does not download model weights.")
        if comfy.model_management.get_torch_device().type != "cuda":
            raise ValueError("LDF-VFI requires an NVIDIA GPU on the configured ComfyUI host")
        comfy.model_management.unload_all_models()
        return loader().load_model("onecat-ai/LDF-VFI", tile_size, tile_overlap, 4, "slide_chunk_all_block_2x1x1")
