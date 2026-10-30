"""Pinned DreamBooth execution used by the Comfy training output node."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .training_models import BASE_SHA256, BASE_REVISION, DIFFUSERS_TRAINING_COMMIT

TRAINER_ROOT = Path(os.environ.get("OPENFRAME_TRAINER_SOURCE", "/opt/openframe-diffusers")).expanduser()
TRAINER_PYTHON = Path(os.environ.get("OPENFRAME_TRAINING_PYTHON", "/opt/openframe-training/bin/python")).expanduser()
MAX_SECONDS = 21600


def training_status(models_dir):
    """Read-only prerequisites; package imports and GPU execution remain runtime checks."""
    import sys
    from .models import model_destination
    from .training_models import TRAINING_MODEL_FILES
    if sys.platform != "linux":
        return False, "Character training requires a configured Linux CUDA ComfyUI host."
    if not TRAINER_PYTHON.is_file() or not os.access(TRAINER_PYTHON, os.X_OK):
        return False, "Configure OPENFRAME_TRAINING_PYTHON; see CHARACTER-TRAINING-RUNTIME.md."
    if not (TRAINER_ROOT / "examples/dreambooth/train_dreambooth_lora_flux3_klein.py").is_file():
        return False, "Configure OPENFRAME_TRAINER_SOURCE to the pinned Diffusers checkout."
    if any(not (Path(models_dir) / model_destination(entry)).is_file()
           for entry in TRAINING_MODEL_FILES["flux3-character-training"]):
        return False, "Provision the pinned flux3-character-training files on the ComfyUI GPU host."
    return True, "Training interpreter, pinned-source path and model files are present; GPU execution is checked on submission."


def normalize_training_request(request):
    r = dict(request)
    if r.get("provider", "local") not in {"local"}:
        raise ValueError("Character training requires a configured Local ComfyUI host.")
    if not re.fullmatch(r"[a-zA-Z0-9-]{16,64}", str(r.get("job_id", ""))):
        raise ValueError("A persisted training job identifier is required.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{3,31}", str(r.get("trigger_token", ""))):
        raise ValueError("Use a unique 4–32 character lowercase trigger token, starting with a letter.")
    r["name"] = str(r.get("name", "")).strip()
    if not 1 <= len(r["name"]) <= 100:
        raise ValueError("Give the trained character a name of 1–100 characters.")
    for key, default in (("steps", 1200), ("resolution", 1024), ("rank", 32), ("seed", 42)):
        r[key] = int(r.get(key, default))
    r["learning_rate"] = float(r.get("learning_rate", .0001))
    if not 500 <= r["steps"] <= 3000 or r["resolution"] not in {512, 768, 1024} or r["rank"] not in {16, 32}:
        raise ValueError("Training uses 500–3000 steps, 512/768/1024 resolution and rank 16 or 32.")
    if not 1e-5 <= r["learning_rate"] <= 2e-4 or not 0 <= r["seed"] <= 2**32 - 1:
        raise ValueError("Training learning rate or seed is outside the supported range.")
    r.setdefault("provider", "local")
    return r


def load_native_transformer(model_root, dtype):
    """Official conversion in memory; never serialize a duplicate 11GB base."""
    import torch
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    from diffusers import Flux3Transformer2DModel
    from diffusers.loaders.single_file_utils import convert_flux3_transformer_checkpoint_to_diffusers
    root = Path(model_root)
    state = convert_flux3_transformer_checkpoint_to_diffusers(load_file(str(root / "native-transformer.safetensors")))
    with init_empty_weights():
        transformer = Flux3Transformer2DModel.from_config(json.loads((root / "transformer/config.json").read_text()))
    transformer.load_state_dict(state, strict=True, assign=True)
    return transformer.to(dtype=dtype)


def _patched_trainer(source):
    logging_argument = "log_with=args.report_to,"
    if source.count(logging_argument) != 1:
        raise RuntimeError("Pinned trainer's logging contract changed.")
    source = source.replace(logging_argument, 'log_with=None if args.report_to == "none" else args.report_to,')
    source = source.replace('check_min_version("0.40.0.dev0")', '''check_min_version("0.40.0.dev0")
from importlib.metadata import version as _of_version
print("OPENFRAME_RUNTIME:" + json.dumps({name: _of_version(name) for name in ("torch", "diffusers", "transformers", "accelerate", "peft", "bitsandbytes")}), flush=True)''')
    old = '''    transformer = Flux3Transformer2DModel.from_pretrained(
        args.pretrained_model_name_or_path,
        subfolder="transformer",
        revision=args.revision,
        variant=args.variant,
        quantization_config=quantization_config,
        torch_dtype=weight_dtype,
    )'''
    if source.count(old) != 1:
        raise RuntimeError("Pinned trainer's base-loading contract changed; refusing an unreviewed adaptation.")
    source = source.replace(old, '''    from engine.training_runtime import load_native_transformer
    transformer = load_native_transformer(args.pretrained_model_name_or_path, weight_dtype)''')
    marker = "                global_step += 1\n"
    if source.count(marker) != 1:
        raise RuntimeError("Pinned trainer's progress contract changed.")
    source = source.replace(marker, marker + '''                if global_step % 25 == 0 or global_step == args.max_train_steps:
                    print("OPENFRAME_TRAINING:" + json.dumps({"step": global_step, "total": args.max_train_steps}), flush=True)
''')
    marker = "                        accelerator.save_state(save_path)\n"
    if source.count(marker) != 1:
        raise RuntimeError("Pinned trainer's checkpoint contract changed.")
    return source.replace(marker, marker + '''                        print("OPENFRAME_CHECKPOINT:" + json.dumps({"step": global_step}), flush=True)
''')


def _native_adapter(source, destination, request):
    from safetensors.torch import load_file, save_file
    state, converted = load_file(str(source)), {}
    for key, value in state.items():
        if not key.startswith("transformer.") or not key.endswith((".lora_A.weight", ".lora_B.weight")) or value.ndim != 2:
            raise ValueError(f"Unsupported trained adapter tensor: {key}")
        name = key.removeprefix("transformer.")
        if name.startswith("mode_blocks."):
            name = "content_mode_blocks." + name.removeprefix("mode_blocks.")
        name = name.replace("single_transformer_blocks.", "single_blocks.")
        for old, new in ((".attn.to_q.", ".q_proj."), (".attn.to_k.", ".k_proj."), (".attn.to_v.", ".v_proj."), (".attn.to_out.0.", ".attn_out."), (".ff.linear_in.", ".mlp_in."), (".ff.linear_out.", ".mlp_out.")):
            name = name.replace(old, new)
        name = "diffusion_model." + name
        if name in converted:
            raise ValueError("Adapter key conversion produced a duplicate tensor.")
        converted[name] = value.contiguous()
    if not converted or len(converted) % 2:
        raise ValueError("Trainer did not save complete LoRA A/B tensor pairs.")
    for key, value in converted.items():
        if key.endswith(".lora_A.weight"):
            other = converted.get(key.replace(".lora_A.weight", ".lora_B.weight"))
            if other is None or value.shape[0] != request["rank"] or other.shape[1] != request["rank"]:
                raise ValueError("Trained LoRA rank/pair mismatch.")
    save_file(converted, str(destination), metadata={"format": "pt", "base_model_sha256": BASE_SHA256,
        "trainer_commit": DIFFUSERS_TRAINING_COMMIT, "trigger_token": request["trigger_token"], "rank": str(request["rank"]), "alpha": str(request["rank"])})
    with destination.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest(), len(converted)


def run_training(request, paths, on_progress, is_cancelled, model_cache=None, mask_paths=None):
    from collections import deque
    import shutil
    import queue
    import subprocess
    import threading
    from PIL import Image
    r = normalize_training_request(request)
    root = Path(model_cache or os.environ.get("OPENFRAME_MODEL_CACHE", ""))
    ready, detail = training_status(root)
    if not ready:
        raise RuntimeError(detail)
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("The character-training ComfyUI host requires CUDA; CPU and native macOS training are not supported.")
    if not 20 <= len(paths) <= 50:
        raise ValueError("Character training requires 20–50 distinct photographs.")
    if shutil.disk_usage(root).free < 5 * 1024**3:
        raise RuntimeError("Training needs at least5GiB free for bounded adapter checkpoints and outputs.")
    model_root = root / "training/flux3-base"
    for name, target in (("tokenizer", model_root / "text_encoder"), ("native-transformer.safetensors", root / "diffusion_models/flux3-image-klein-base-bf16.safetensors")):
        if not target.exists():
            raise ValueError("Provision the flux3-character-training profile before training.")
        link = model_root / name
        if not link.exists():
            link.symlink_to(target)
    output = root / "loras/openframe" / r["job_id"]
    if (output / "character.safetensors").exists():
        raise ValueError("This training job already has a finished adapter; recover its recorded result instead of training twice.")
    output.mkdir(parents=True, exist_ok=True)
    with (model_root / "native-transformer.safetensors").open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != BASE_SHA256:
            raise ValueError("The training base checkpoint does not match the pinned native weights.")
    dataset = output / "dataset"
    dataset.mkdir(exist_ok=True)
    mask_paths = mask_paths or []
    if (mask_paths and len(mask_paths) != len(paths)) or (r.get("loss_mask_asset_ids") and not mask_paths):
        raise ValueError("Masked training requires exactly one aligned loss mask per photograph.")
    records, seen, total_pixels = [], set(), 0
    mask_records, mask_files = [], {}
    for index, filename in enumerate(paths):
        path = Path(filename).resolve()
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest in seen:
            raise ValueError("The training dataset contains duplicate image bytes.")
        seen.add(digest)
        with Image.open(path) as picture:
            if picture.format not in {"JPEG", "PNG", "WEBP"} or getattr(picture, "n_frames", 1) != 1:
                raise ValueError("Training photos must be single PNG, JPEG or WebP images.")
            width, height = picture.size
            if min(width, height) < 256 or width * height > 40_000_000:
                raise ValueError("Training photographs need a 256px minimum side and at most 40 megapixels.")
            picture.verify()
        if mask_paths:
            with Image.open(path) as orientation_image:
                if orientation_image.getexif().get(274, 1) != 1:
                    raise ValueError("Masked training photographs must be upright; materialize EXIF orientation before drawing masks.")
        total_pixels += width * height
        if total_pixels > 500_000_000:
            raise ValueError("The complete training dataset is limited to 500 megapixels.")
        link = dataset / f"{index:03d}{path.suffix.lower()}"
        if not link.exists():
            link.symlink_to(path)
        records.append({"index": index, "sha256": digest, "width": width, "height": height, "size_bytes": path.stat().st_size})
        if mask_paths:
            from .training_masks import validate_loss_mask
            mask_path = Path(mask_paths[index]).resolve()
            coverage = validate_loss_mask(mask_path, (width, height))
            with mask_path.open("rb") as handle:
                mask_sha = hashlib.file_digest(handle, "sha256").hexdigest()
            mask_files[link.name] = str(mask_path)
            mask_records.append({"index": index, "sha256": mask_sha, "paired_image_sha256": digest,
                                 "width": width, "height": height, "coverage": coverage})
    source_path = TRAINER_ROOT / "examples/dreambooth/train_dreambooth_lora_flux3_klein.py"
    original = source_path.read_text()
    if hashlib.sha256(original.encode()).hexdigest() != "89cc2ff1af1909c1652deefdee7a60e589c3d4e7169d22ab7e05e3ca0c49be72":
        raise RuntimeError("The installed trainer does not match its pinned source checksum.")
    patched = _patched_trainer(original)
    if mask_paths:
        from .training_masks import patch_masked_trainer
        patched = patch_masked_trainer(patched)
    script = output / "train_pinned.py"
    script.write_text(patched)
    checkpoint_dir = output / "checkpoints"
    command = [str(TRAINER_PYTHON), str(script), "--pretrained_model_name_or_path", str(model_root),
        "--instance_data_dir", str(dataset), "--instance_prompt", f"A photograph of {r['trigger_token']} person.",
        "--output_dir", str(checkpoint_dir), "--resolution", str(r["resolution"]), "--use_aspect_ratio_buckets",
        "--train_batch_size", "1", "--gradient_accumulation_steps", "1", "--gradient_checkpointing", "--mixed_precision", "bf16",
        "--rank", str(r["rank"]), "--lora_alpha", str(r["rank"]), "--learning_rate", str(r["learning_rate"]),
        "--max_train_steps", str(r["steps"]), "--seed", str(r["seed"]), "--lr_scheduler", "constant", "--lr_warmup_steps", "0",
        "--caption_dropout", "0.1", "--offload", "--cache_latents", "--use_8bit_adam", "--checkpointing_steps", "500",
        "--checkpoints_total_limit", "2", "--report_to", "none", "--skip_final_inference"]
    environment = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", WANDB_DISABLED="true", TOKENIZERS_PARALLELISM="false", PYTHONUNBUFFERED="1")
    if mask_paths:
        mask_manifest = output / "loss-mask-inputs.json"
        mask_manifest.write_text(json.dumps(mask_files, indent=2))
        environment["OPENFRAME_TRAINING_MASKS"] = str(mask_manifest)
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment, bufsize=1)
    lines, tail, stop_reader = queue.Queue(maxsize=256), deque(maxlen=100), threading.Event()
    runtime_versions = {}
    mask_transforms = []
    def enqueue(value):
        while not stop_reader.is_set():
            try:
                lines.put(value, timeout=.5)
                return
            except queue.Full:
                pass
    def read_output():
        try:
            for line in process.stdout:
                enqueue(line[-4000:])
                if stop_reader.is_set():
                    break
        finally:
            enqueue(None)
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    state = {"progress": .02, "stage": "Preparing training models and photographs", "checkpoint_step": 0}
    def report():
        (output / "progress.json").write_text(json.dumps(state))
        on_progress(state["progress"], state["stage"])
    report()
    try:
        while True:
            if is_cancelled():
                raise RuntimeError("Character training cancelled; completed checkpoints remain remote.")
            if time.monotonic() - started > MAX_SECONDS - 120:
                raise TimeoutError("Character training exceeded its six-hour execution budget.")
            try:
                line = lines.get(timeout=.5)
            except queue.Empty:
                continue
            if line is None:
                break
            tail.append(line)
            if "OPENFRAME_LOSS_MASK:" in line:
                mask_transforms.append(json.loads(line.split("OPENFRAME_LOSS_MASK:", 1)[1]))
            elif "OPENFRAME_RUNTIME:" in line:
                runtime_versions = json.loads(line.split("OPENFRAME_RUNTIME:", 1)[1])
            elif "OPENFRAME_TRAINING:" in line:
                value = json.loads(line.split("OPENFRAME_TRAINING:", 1)[1])
                state.update(progress=.05 + .9 * value["step"] / r["steps"], stage=f"Training character · {value['step']}/{r['steps']} steps")
                report()
            elif "OPENFRAME_CHECKPOINT:" in line:
                state["checkpoint_step"] = json.loads(line.split("OPENFRAME_CHECKPOINT:", 1)[1])["step"]
                report()
        if process.wait(timeout=30):
            raise RuntimeError("Pinned character trainer failed: " + "".join(tail)[-4000:])
    finally:
        stop_reader.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=10)
        process.stdout.close()
        reader.join(timeout=2)
        (output / "trainer-tail.log").write_text("".join(tail)[-100_000:])
    destination = output / "character.safetensors"
    sha, tensor_count = _native_adapter(checkpoint_dir / "pytorch_lora_weights.safetensors", destination, r)
    result = {"adapter": {"id": r["job_id"], "name": r["name"], "model_id": "flux3-klein-base", "base_model_sha256": BASE_SHA256,
        "base_model_revision": BASE_REVISION, "lora_name": f"openframe/{r['job_id']}/character.safetensors", "sha256": sha,
        "size_bytes": destination.stat().st_size, "trigger_token": r["trigger_token"], "rank": r["rank"], "steps": r["steps"], "format": "ComfyUI native FLUX3 LoRA"},
        "metadata": {"job_id": r["job_id"], "seconds": time.monotonic() - started, "dataset": records,
        "trainer_commit": DIFFUSERS_TRAINING_COMMIT, "trainer_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "adapted_trainer_sha256": hashlib.sha256(patched.encode()).hexdigest(), "tensor_count": tensor_count,
        "request": r, "runtime_versions": runtime_versions, "precision": "BF16 base; rank=alpha LoRA; 8-bit Adam", "flow_shift": 6.93,
        "checkpoint_every_steps": 500, "checkpoint_limit": 2, "budget_seconds": MAX_SECONDS,
        "conversion": "Reverse official Diffusers FLUX3 native-LoRA key mapping; no tensor quantization", "validation_rendered": False,
        "license": "FLUX Kommunity License 1.0; commercial fine-tuning is not covered merely by its commercial-output exception"}}
    if mask_paths:
        from .training_masks import FIZGIG_COMMIT, OUTSIDE_WEIGHT
        if len(mask_transforms) != len(paths):
            raise RuntimeError("The trainer did not record every paired transformed loss mask.")
        result["metadata"]["masked_loss"] = {"source": "shootthesound/Fizgig", "source_commit": FIZGIG_COMMIT,
            "license": "Apache-2.0", "helper_sha256": hashlib.sha256(Path(__file__).with_name("training_masks.py").read_bytes()).hexdigest(), "outside_weight": OUTSIDE_WEIGHT, "normalization": "per-image spatial mean1",
            "target": "unchanged flow velocity", "mask_sampling": "same CPU crop/flip RNG; area-resized token grid",
            "masks": mask_records, "transforms": mask_transforms}
    (output / "result.json").write_text(json.dumps(result, indent=2))
    on_progress(1, "Character adapter saved")
    return result
