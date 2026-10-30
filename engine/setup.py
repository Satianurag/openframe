"""Install OpenFrame nodes and a selected model into an existing ComfyUI checkout."""
import argparse
from pathlib import Path
import shutil
import subprocess
from .models import MODEL_FILES, LTX_NODES_COMMIT, SAM2_COMMIT, WAN_ANIMATE_PREPROCESS_COMMIT, WAN_WRAPPER_COMMIT, TWEEN_COMMIT, download_model, model_destination, required_model_files
from .editvid_models import EDITVID_COMMIT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-dir", type=Path, required=True)
    parser.add_argument("--model", choices=MODEL_FILES, default="ltx-0.9.8")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--base-only", action="store_true", help="Skip task-specific inpainting adapters; provision generation weights only")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--recast-composite-tracking", choices=["native", "official", "official-union"], default="native",
                        help="SCAIL-2 only: include the official final-support checkpoint; runtime setup remains explicit")
    parser.add_argument("--recast-reference-cleanup", action="store_true", help="SCAIL-2 only: include CPU ViTMatte reference-edge weights")
    args = parser.parse_args()
    if args.recast_composite_tracking != "native" and args.model != "scail-2":
        parser.error("Official composite tracking applies only to --model scail-2")
    if args.recast_reference_cleanup and args.model != "scail-2":
        parser.error("Reference cleanup applies only to --model scail-2")
    request = {"task": "character-replacement", "recast_composite_tracking": args.recast_composite_tracking,
               "recast_reference_cleanup": args.recast_reference_cleanup} if args.model == "scail-2" else None
    root = args.comfy_dir.expanduser().resolve()
    if not (root / "main.py").is_file():
        parser.error("--comfy-dir must point to an existing ComfyUI installation.")
    source = Path(__file__).resolve().parents[1] / "custom_nodes/openframe"
    target = root / "custom_nodes/openframe"
    target.mkdir(parents=True, exist_ok=True)
    for file in source.glob("*"):
        if file.is_file():
            destination = target / file.name
            if not destination.exists() or destination.read_bytes() != file.read_bytes():
                shutil.copy2(file, destination)
    dependencies = {
        "ltx-2.3": ("ComfyUI-LTXVideo", LTX_NODES_COMMIT, "Lightricks/ComfyUI-LTXVideo"),
        "ltx-2.5": ("ComfyUI-LTXVideo", LTX_NODES_COMMIT, "Lightricks/ComfyUI-LTXVideo"),
        "wan-animate": ("ComfyUI-WanAnimatePreprocess", WAN_ANIMATE_PREPROCESS_COMMIT, "kijai/ComfyUI-WanAnimatePreprocess"),
        "longcat-avatar-1.5": ("ComfyUI-WanVideoWrapper", WAN_WRAPPER_COMMIT, "kijai/ComfyUI-WanVideoWrapper"),
        "ldf-vfi": ("ComfyUI-Tween", TWEEN_COMMIT, "Ethanfel/ComfyUI-Tween"),
        "flux-klein-editvid": ("ComfyUI_FLUX-Klein-EditVid", EDITVID_COMMIT, "CanFromEarth/ComfyUI_FLUX-Klein-EditVid"),
    }
    if args.model in dependencies:
        node_name, node_commit, node_repo = dependencies[args.model]
        node_dir = root / "custom_nodes" / node_name
        if not node_dir.exists():
            subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", f"https://github.com/{node_repo}.git", str(node_dir)], check=True)
            subprocess.run(["git", "-C", str(node_dir), "checkout", node_commit], check=True)
        else:
            revision = subprocess.check_output(["git", "-C", str(node_dir), "rev-parse", "HEAD"], text=True).strip()
            if revision != node_commit:
                print(f"Existing {node_name} revision is {revision}; this release was developed against {node_commit}. Existing files were preserved.")
                if args.model == "flux-klein-editvid":
                    raise SystemExit("EditVid requires its exact declared native port. Review the existing checkout before continuing; it was not modified.")
    if not args.no_download:
        free = shutil.disk_usage(root).free
        missing = [entry for entry in required_model_files(args.model, request) if not (root / "models" / model_destination(entry)).exists() and (not args.base_only or not entry.get("tasks") or "text-to-video" in entry["tasks"])]
        expected = sum(entry.get("size_bytes", 0) for entry in missing)
        if any(not entry.get("size_bytes") for entry in missing):
            expected = max(expected, {"ltx-0.9.8": 11, "ltx-2.3": 85, "wan-vace": 12, "sam2": 1}.get(args.model, 1) * 1024**3)
        expected += 1024**3 if missing else 0
        if free < expected:
            print(f"Available space: {free / 1024**3:.1f} GiB. This profile can require about {expected / 1024**3:.0f} GiB including cache. Reuse an existing cache or free space before downloading.")
            raise SystemExit(1)
        download_model(args.model, root, args.cache_dir, lambda _, message: print(message, flush=True), task="text-to-video" if args.base_only else None, request=request)
    print("Nodes installed. In ComfyUI's Python environment run:")
    print(f"python -m pip install -r {target / 'requirements.txt'}")
    if args.model == "scail-2":
        print("Native SCAIL-2 requires the pinned compatible ComfyUI core; no extra diffusion wrapper is needed.")
        if args.recast_reference_cleanup:
            print(f"Reference cleanup runs in the ComfyUI Python environment on CPU. Follow {target / 'REFERENCE-CLEANUP.md'}.")
        if args.recast_composite_tracking != "native":
            print(f"Official final support also needs an isolated Linux CUDA runtime. Follow {target / 'RECAST-RUNTIME.md'} and configure OPENFRAME_SAM3_PYTHON on the ComfyUI host.")
    if args.model == "sam3.1-vitmatte":
        print(f"Configure the shared Linux CUDA isolated runtime using {target / 'RECAST-RUNTIME.md'}. ViTMatte is used only for semantic soft-alpha output, not Recast support.")
    if args.model in {"ltx-2.3", "ltx-2.5"}:
        print(f"python -m pip install -r {root / 'custom_nodes/ComfyUI-LTXVideo/requirements.txt'}")
    if args.model in {"longcat-avatar-1.5", "ldf-vfi"}:
        print(f"python -m pip install -r {root / 'custom_nodes' / dependencies[args.model][0] / 'requirements.txt'}")
        print("Use the pinned ComfyUI runtime. Model weights must already be provisioned; runtime inference does not download them.")
    if args.model == "qwen3.8-planner":
        print(f"Configure the isolated Linux CUDA visual planner using {target / 'PLANNER-RUNTIME.md'}. This command does not install its runtime; no CPU or smaller-model fallback is used.")
    if args.model == "flux3-character-training":
        print(f"Configure the isolated Linux CUDA trainer using {target / 'CHARACTER-TRAINING-RUNTIME.md'}. This command does not install the training runtime.")
    if args.model == "wan-animate":
        print("python -m pip install 'onnxruntime>=1.20,<2' 'matplotlib>=3.9,<4'")
        print("Wan pose/face preprocessing runs on CPU; no ONNX GPU runtime is required.")
    if args.model == "kokoro-82m":
        print("python -m pip install 'kokoro==0.9.4' 'misaki[en]==0.9.4' 'spacy>=3.8,<3.9' https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl")
        print("Install espeak-ng with your OS package manager (Homebrew: brew install espeak-ng; Debian: apt install espeak-ng).")
    if args.model in {"qwen-planner", "qwen-planner-7b"}:
        print("For local planning, install torch and transformers in the OpenFrame backend Python environment.")
        if args.model == "qwen-planner-7b":
            print(f"Set OPENFRAME_PLANNER_MODEL_DIR={root / 'models' / MODEL_FILES[args.model][0]['category']} when starting OpenFrame.")
        else:
            print("This is the retained legacy 1.5B profile. The app planner requires --model qwen-planner-7b.")
    print(f"For SAM2 tracking: SAM2_BUILD_CUDA=0 python -m pip install git+https://github.com/facebookresearch/sam2.git@{SAM2_COMMIT}")
    print("Provision tracker weights separately with: python -m engine.setup --comfy-dir <path> --model sam2")
    print("Restart ComfyUI, then select Local ComfyUI in OpenFrame and check connection.")

if __name__ == "__main__":
    main()
