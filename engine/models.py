"""Pinned upstream revisions. Weights are downloaded by the operator, never bundled."""
from pathlib import Path

COMFY_COMMIT = "79cf64c21a1dba50749945ba9fe2e3a692f45438"
LTX_NODES_COMMIT = "220e1d45aa0469f518e982102fca4dca92a61862"
SAM2_COMMIT = "2b90b9f5ceec907a1c18123530e92e794ad901a4"

MODEL_FILES = {
    "sam2": [
        {"repo": "facebook/sam2.1-hiera-small", "revision": "ee5bba1d82bb8749febdf90f45e84b687142ba03", "file": "sam2.1_hiera_small.pt", "category": "sam2"},
    ],
    "ltx-0.9.8": [
        {"repo": "Lightricks/LTX-Video", "revision": "8984fa25007f376c1a299016d0957a37a2f797bb", "file": "ltxv-2b-0.9.8-distilled.safetensors", "category": "checkpoints"},
        {"repo": "comfyanonymous/flux_text_encoders", "revision": "6af2a98e3f615bdfa612fbd85da93d1ed5f69ef5", "file": "t5xxl_fp8_e4m3fn_scaled.safetensors", "category": "text_encoders"},
    ],
    "ltx-2.3": [
        {"repo": "Lightricks/LTX-2.3", "revision": "c1521179de480464f366a98a9d9b2acc4cc097b9", "file": "ltx-2.3-22b-dev.safetensors", "category": "checkpoints", "expected_sha256": "7ab7225325bc403448ea84b6db2269811a880e5118cd2ee2b6282a93d585016f", "size_bytes": 46149344974, "metadata_source": "https://huggingface.co/Lightricks/LTX-2.3/blob/c1521179de480464f366a98a9d9b2acc4cc097b9/ltx-2.3-22b-dev.safetensors"},
        {"repo": "Lightricks/LTX-2.3", "revision": "c1521179de480464f366a98a9d9b2acc4cc097b9", "file": "ltx-2.3-22b-distilled-lora-384-1.1.safetensors", "category": "loras", "expected_sha256": "f5d4953f3386197a4b4f5abdb17616ff256171e8075c111d6e7d2dfa6e823b3a", "size_bytes": 7605507256, "metadata_source": "https://huggingface.co/Lightricks/LTX-2.3/blob/c1521179de480464f366a98a9d9b2acc4cc097b9/ltx-2.3-22b-distilled-lora-384-1.1.safetensors"},
        {"repo": "Comfy-Org/ltx-2", "revision": "ccde4ba417d7900669fd56dd292a883cee11ff37", "file": "split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", "category": "text_encoders", "expected_sha256": "60216ce97c01c3a8753c2dfd0a89fc76e16fbe446d1a32ef8f1b528ac8bae466", "size_bytes": 13205434827, "metadata_source": "https://huggingface.co/Comfy-Org/ltx-2/blob/ccde4ba417d7900669fd56dd292a883cee11ff37/split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors"},
        {"repo": "Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting", "revision": "8becd61405133263d9e580be41a92e8f827b01ed", "file": "ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors", "category": "loras", "tasks": ["inpaint"], "requires_access": True, "expected_sha256": "73dd0841c0d4f0eb26fb1f017781b841b2752021944ac5ecefe57917f6dae6b5", "size_bytes": 1308778338, "metadata_source": "https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting/blob/8becd61405133263d9e580be41a92e8f827b01ed/ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors"},
    ],
    "wan-vace": [
        {"repo": "Comfy-Org/Wan_2.1_ComfyUI_repackaged", "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d", "file": "split_files/diffusion_models/wan2.1_vace_1.3B_fp16.safetensors", "category": "diffusion_models"},
        {"repo": "Comfy-Org/Wan_2.1_ComfyUI_repackaged", "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d", "file": "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "category": "text_encoders"},
        {"repo": "Comfy-Org/Wan_2.1_ComfyUI_repackaged", "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d", "file": "split_files/vae/wan_2.1_vae.safetensors", "category": "vae"},
    ],
}


def download_model(model_id: str, comfy_dir: Path, cache_dir: Path | None = None, progress=None, task: str | None = None):
    from huggingface_hub import hf_hub_download
    if model_id not in MODEL_FILES:
        raise ValueError(f"Unsupported model profile: {model_id}")
    paths = []
    entries = [entry for entry in MODEL_FILES[model_id] if task is None or not entry.get("tasks") or task in entry["tasks"]]
    for i, entry in enumerate(entries):
        dest = Path(comfy_dir) / "models" / entry["category"] / Path(entry["file"]).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            if progress:
                progress(i / len(entries), f"Downloading {dest.name}")
            downloaded = Path(hf_hub_download(repo_id=entry["repo"], filename=entry["file"], revision=entry["revision"], cache_dir=str(cache_dir) if cache_dir else None)).resolve()
            if dest.is_symlink():
                dest.unlink()
            dest.symlink_to(downloaded)
        paths.append(str(dest))
    return paths
