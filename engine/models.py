"""Pinned upstream revisions. Weights are downloaded by the operator, never bundled."""
from pathlib import Path
from .image_models import FLUX3_MODEL_FILES
from .video_models import video_model_files, WAN_WRAPPER_COMMIT
from .utility_models import UTILITY_MODEL_FILES, TWEEN_COMMIT
from .depth_models import DEPTH_MODEL_FILES
from .analysis_models import ANALYSIS_MODEL_FILES
from .training_models import TRAINING_MODEL_FILES
from .layer_models import LAYER_MODEL_FILES
from .image_relight_models import IMAGE_RELIGHT_MODEL_FILES
from .portrait_relight_models import PORTRAIT_RELIGHT_FILES
from .narration_models import NARRATION_MODEL_FILES
from .matte_models import MATTE_MODEL_FILES
from .vace14_models import VACE14_MODEL_FILE
from .recast_models import recast_model_files
from .ripple_models import ripple_model_files
from .smoke_models import SMOKE_MODEL_FILES
from .relight_models import relight_model_files
from .editvid_models import EDITVID_MODEL_FILES

COMFY_COMMIT = "79cf64c21a1dba50749945ba9fe2e3a692f45438"
LTX_NODES_COMMIT = "220e1d45aa0469f518e982102fca4dca92a61862"
SAM2_COMMIT = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
WAN_ANIMATE_PREPROCESS_COMMIT = "0e0b6a2a555625acf4d4aefb780e27d06937132f"

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

MODEL_FILES["wan-vace-14b"] = [
    VACE14_MODEL_FILE,
    *[dict(entry) for entry in MODEL_FILES["wan-vace"] if entry["category"] in {"text_encoders", "vae"}],
]

# Exact metadata, read from the upstream repositories before provisioning.
# VAE licensing is file-specific: FLUX.2's autoencoder is Apache-2.0 even
# though the repository also contains non-commercial diffusion weights.
MODEL_FILES["flux-klein-4b"] = [
    {"repo": "black-forest-labs/FLUX.2-klein-4b-fp8", "revision": "5b4408e59397a4a37ccb46afe426d8ed86379441", "file": "flux-2-klein-4b-fp8.safetensors", "category": "diffusion_models", "size_bytes": 4070624520, "expected_sha256": "97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6", "license": "Apache-2.0"},
    {"repo": "Comfy-Org/z_image_turbo", "revision": "6fc90a3b1b653e935a0d175e260736de25b84df5", "file": "split_files/text_encoders/qwen_3_4b.safetensors", "category": "text_encoders", "size_bytes": 8044982048, "expected_sha256": "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a", "license": "Apache-2.0"},
    {"repo": "Comfy-Org/flux2-dev", "revision": "9630c1b4b6e690497ae0c19bb6b1b35d4ebedcb7", "file": "split_files/vae/flux2-vae.safetensors", "category": "vae", "size_bytes": 336213556, "expected_sha256": "d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5", "license": "Apache-2.0 (autoencoder)", "metadata_source": "https://github.com/black-forest-labs/flux2#flux2-dev"},
]
MODEL_FILES["wan-animate"] = [
    {"repo": "Kijai/WanVideo_comfy_fp8_scaled", "revision": "033a4e487f60220b3d6e469599a6aebc46e13cee", "file": "Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", "category": "diffusion_models", "size_bytes": 18401760586, "expected_sha256": "2936b31473a967e7a429a6646bba60e7862d0938e178b58b2a140f391dd5b8e6", "license": "Apache-2.0", "source_note": "Community FP8 conversion used by the official ComfyUI template."},
    *[dict(entry) for entry in MODEL_FILES["wan-vace"] if entry["category"] in {"text_encoders", "vae"}],
    {"repo": "Comfy-Org/Wan_2.1_ComfyUI_repackaged", "revision": "123acf1cc74bccbb9bfff8ac1ee72edc08c2341d", "file": "split_files/clip_vision/clip_vision_h.safetensors", "category": "clip_vision", "size_bytes": 1264219396, "expected_sha256": "64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161"},
    {"repo": "Kijai/WanVideo_comfy", "revision": "8260d429d19fd7a72304cad059160b95d843913f", "file": "Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", "category": "loras", "size_bytes": 738005744, "expected_sha256": "85c4a61c30e0497aa44b91d93a893b624708461a56fe5485183b28fa07e2dfb3", "source_note": "Upstream LightX2V adapter repack, used by the official ComfyUI template."},
    {"repo": "Kijai/WanVideo_comfy", "revision": "8260d429d19fd7a72304cad059160b95d843913f", "file": "LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors", "category": "loras", "tasks": ["character-replacement"], "size_bytes": 1436672440, "expected_sha256": "fc646c74c73f4b251f5fd9bc440ef21b03b27305f499966c68b2b3aa31498561", "source_note": "Wan Animate relight adapter repack; upstream component terms apply."},
    {"repo": "Wan-AI/Wan2.2-Animate-14B", "revision": "cb93a225fbaf1ca100f54e79da8f994995b689b3", "file": "process_checkpoint/det/yolov10m.onnx", "category": "detection", "size_bytes": 61659339, "expected_sha256": "89b526498a6d55f869a6ab52e3a2eb20ad45b3711c1f7de3dd9ca0b399dfd6d7", "source_note": "Official Wan preprocessing checkpoint; detector component licensing must be retained separately from the generative model."},
    {"repo": "Kijai/vitpose_comfy", "revision": "ae68f4e542151cebec0995b8469c70b07b8c3df4", "file": "onnx/vitpose_h_wholebody_model.onnx", "category": "detection", "materialize": True, "size_bytes": 420252, "expected_sha256": "f21466cd6c93d0066782ad5923c14a4e6569133def212dc2895c73596c2e553b"},
    {"repo": "Kijai/vitpose_comfy", "revision": "ae68f4e542151cebec0995b8469c70b07b8c3df4", "file": "onnx/vitpose_h_wholebody_data.bin", "category": "detection", "materialize": True, "size_bytes": 2548958740, "expected_sha256": "f6a9e7cb3a87ed65a098b096029e70150408acfafc3d695019a66b289d7719e1"},
]
MODEL_FILES["birefnet"] = [
    {"repo": "Comfy-Org/BiRefNet", "revision": "884af709e9b795d89dafbf97f29c8d6a2386f5c6", "file": "background_removal/birefnet.safetensors", "category": "background_removal", "size_bytes": 444473596, "expected_sha256": "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154", "license": "MIT"},
]
MODEL_FILES["wan-s2v"] = [
    {"repo": "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "revision": "ee6f4a40737a995bf5818954cfce6d59443b0f04", "file": "split_files/diffusion_models/wan2.2_s2v_14B_bf16.safetensors", "category": "diffusion_models", "size_bytes": 32591643778, "expected_sha256": "a61c103c1e0118123a222af1b8bbd0bc5d6b6bda70e6b182c653c4a16908692e", "license": "Apache-2.0", "source_note": "Official Comfy-Org repack of Wan-AI's purpose-trained S2V model; full BF16, without mismatched lightning adapters."},
    {"repo": "Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "revision": "ee6f4a40737a995bf5818954cfce6d59443b0f04", "file": "split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors", "category": "audio_encoders", "size_bytes": 630997322, "expected_sha256": "f0017a43ea57ef6b3d4866be607844bbd8cada6d30966f7d70044ed0d63d3f9e", "license": "Apache-2.0"},
    *[dict(entry) for entry in MODEL_FILES["wan-vace"] if entry["category"] in {"text_encoders", "vae"}],
]
MODEL_FILES["kokoro-82m"] = [
    {"repo": "hexgrad/Kokoro-82M", "revision": "f3ff3571791e39611d31c381e3a41a3af07b4987", "file": file, "category": "tts/kokoro", "size_bytes": size, **({"expected_sha256": sha} if sha else {}), "license": "Apache-2.0"}
    for file, size, sha in [
        ("config.json", 2351, None),
        ("kokoro-v1_0.pth", 327212226, "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"),
        ("voices/af_heart.pt", 523425, "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff"),
        ("voices/am_michael.pt", 523435, "9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37"),
        ("voices/bf_emma.pt", 523420, "d0a423deabf4a52b4f49318c51742c54e21bb89bbbe9a12141e7758ddb5da701"),
        ("voices/bm_george.pt", 523430, "f1bc812213dc59774769e5c80004b13eeb79bd78130b11b2d7f934542dab811b"),
    ]
]
MODEL_FILES["qwen-planner"] = [
    {"repo": "Qwen/Qwen2.5-1.5B-Instruct", "revision": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306", "file": file, "category": "planning/qwen2.5-1.5b-instruct", "size_bytes": size, **({"expected_sha256": sha} if sha else {}), "license": "Apache-2.0"}
    for file, size, sha in [
        ("config.json", 660, None), ("generation_config.json", 242, None),
        ("merges.txt", 1671839, None), ("tokenizer.json", 7031645, None),
        ("tokenizer_config.json", 7305, None), ("vocab.json", 2776833, None),
        ("model.safetensors", 3087467144, "dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee"),
    ]
]


MODEL_FILES["qwen-planner-7b"] = [{'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'config.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 663, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'generation_config.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 243, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'merges.txt', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 1671839, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'model-00001-of-00004.safetensors', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 3945441440, 'license': 'Apache-2.0', 'expected_sha256': 'a1333e6293854747c481288ea83b348226af178dd565c49b6f9495ba1966aba7'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'model-00002-of-00004.safetensors', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 3864726352, 'license': 'Apache-2.0', 'expected_sha256': 'f5d25a2772cb825164a2a2c0fb6d51a87e282abf21e4dd75bc5cfb3cd0ea6185'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'model-00003-of-00004.safetensors', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 3864726424, 'license': 'Apache-2.0', 'expected_sha256': '8efdec4c1bc12317ae1a38dc42b595ce777738a64deea3fcb8a0a91381bcdfd5'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'model-00004-of-00004.safetensors', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 3556377672, 'license': 'Apache-2.0', 'expected_sha256': '1a72d403cdf0c1ec3cb7f289f17b394a01e64394c2e9b3c0f94dbce3faf879bd'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'model.safetensors.index.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 27752, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'tokenizer.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 7031645, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'tokenizer_config.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 7305, 'license': 'Apache-2.0'}, {'repo': 'Qwen/Qwen2.5-7B-Instruct', 'revision': 'a09a35458c702b33eeacc393d103063234e8bc28', 'file': 'vocab.json', 'category': 'planning/qwen2.5-7b-instruct', 'size_bytes': 2776833, 'license': 'Apache-2.0'}]


MODEL_FILES.update(FLUX3_MODEL_FILES)
MODEL_FILES.update(video_model_files(MODEL_FILES))
MODEL_FILES.update(recast_model_files(MODEL_FILES))
MODEL_FILES["ltx-ripple"] = ripple_model_files(MODEL_FILES["ltx-2.5"])
MODEL_FILES.update(UTILITY_MODEL_FILES)
MODEL_FILES.update(DEPTH_MODEL_FILES)
MODEL_FILES.update(ANALYSIS_MODEL_FILES)
MODEL_FILES.update(TRAINING_MODEL_FILES)
MODEL_FILES.update(LAYER_MODEL_FILES)
MODEL_FILES.update(IMAGE_RELIGHT_MODEL_FILES)
MODEL_FILES["qwen-portrait-relight"] = PORTRAIT_RELIGHT_FILES
MODEL_FILES.update(EDITVID_MODEL_FILES)
MODEL_FILES.update(NARRATION_MODEL_FILES)
MODEL_FILES.update(MATTE_MODEL_FILES)
MODEL_FILES.update(SMOKE_MODEL_FILES)
MODEL_FILES["ltx-2.3-relight"] = relight_model_files(MODEL_FILES["ltx-2.3"])


def required_model_files(model_id, request=None):
    """Exact operation dependencies; omitted request returns the full install profile."""
    entries = MODEL_FILES[model_id]
    if request is None:
        return list(entries)
    defaults = {"enhance_prompt": request.get("task") != "inpaint", "video_refinement": "two-stage", "upscale_mode": "pixel-2x", "image_prompt_mode": "expand"}
    values = {**defaults, **request}
    if model_id == "scail-2" and values.get("recast_composite_tracking") == "official-union":
        # Both support recipes use the identical official SAM checkpoint.
        values["recast_composite_tracking"] = "official"
    if model_id == "ltx-2.5" and values.get("task") == "restyle":
        values["video_refinement"] = "two-stage" if values.get("restyle_method") == "canny" else "single"
    if values["enhance_prompt"] is None:
        values["enhance_prompt"] = defaults["enhance_prompt"]
    return [entry for entry in entries
            if (not entry.get("tasks") or values.get("task") in entry["tasks"])
            and (not entry.get("feature") or values.get(entry["feature"], True))
            and all(values.get(key) == value for key, value in entry.get("when", {}).items())]


def model_destination(entry):
    """Relative model path; explicit aliases preserve old graph dependencies."""
    relative = Path(entry["category"]) / entry.get("destination_name", Path(entry["file"]).name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Model destinations must remain within the models directory")
    return relative


def _materialize_sibling_file(destination: Path):
    """ORT external data must resolve inside the model's own directory."""
    import os
    import shutil
    import uuid
    if not destination.is_symlink():
        return
    source = destination.resolve(strict=True)
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".partial")
    try:
        try:
            os.link(source, temporary)
        except OSError:
            # Some mounted volumes cannot hard-link. One persistent copy is
            # then necessary; retain the valid shared download cache.
            if shutil.disk_usage(destination.parent).free < source.stat().st_size + 1024**3:
                raise RuntimeError(f"Insufficient space to materialize ONNX external data: {destination.name}")
            shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def download_model(model_id: str, comfy_dir: Path, cache_dir: Path | None = None, progress=None, task: str | None = None, request: dict | None = None):
    from huggingface_hub import hf_hub_download
    if model_id not in MODEL_FILES:
        raise ValueError(f"Unsupported model profile: {model_id}")
    paths = []
    entries = required_model_files(model_id, request) if request is not None else [entry for entry in MODEL_FILES[model_id] if task is None or not entry.get("tasks") or task in entry["tasks"]]
    for i, entry in enumerate(entries):
        dest = Path(comfy_dir) / "models" / model_destination(entry)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            reusable = Path(comfy_dir) / "models" / entry.get("reuse_model", "__no_reusable_model__")
            if reusable.is_file() and entry.get("expected_sha256"):
                import hashlib
                with reusable.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                if digest == entry["expected_sha256"]:
                    if dest.is_symlink():
                        dest.unlink()
                    dest.symlink_to(reusable.resolve())
                    paths.append(str(dest))
                    continue
            if progress:
                progress(i / len(entries), f"Downloading {dest.name}")
            downloaded = Path(hf_hub_download(repo_id=entry["repo"], filename=entry["file"], revision=entry["revision"], cache_dir=str(cache_dir) if cache_dir else None)).resolve()
            if dest.is_symlink():
                dest.unlink()
            dest.symlink_to(downloaded)
        if entry.get("materialize") and dest.is_symlink():
            if progress:
                progress(i / len(entries), f"Preparing colocated ONNX data: {dest.name}")
            _materialize_sibling_file(dest)
        paths.append(str(dest))
    return paths
