"""Install OpenFrame nodes and a selected model into an existing ComfyUI checkout."""
import argparse
from pathlib import Path
import shutil
import subprocess
from .models import MODEL_FILES, LTX_NODES_COMMIT, SAM2_COMMIT, download_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-dir", type=Path, required=True)
    parser.add_argument("--model", choices=MODEL_FILES, default="ltx-0.9.8")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--base-only", action="store_true", help="Skip task-specific inpainting adapters; provision generation weights only")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
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
    if args.model == "ltx-2.3":
        node_dir = root / "custom_nodes/ComfyUI-LTXVideo"
        if not node_dir.exists():
            subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/Lightricks/ComfyUI-LTXVideo.git", str(node_dir)], check=True)
            subprocess.run(["git", "-C", str(node_dir), "checkout", LTX_NODES_COMMIT], check=True)
        else:
            revision = subprocess.check_output(["git", "-C", str(node_dir), "rev-parse", "HEAD"], text=True).strip()
            if revision != LTX_NODES_COMMIT:
                print(f"Existing LTX node revision is {revision}; this release was developed against {LTX_NODES_COMMIT}. Existing files were preserved.")
    if not args.no_download:
        free = shutil.disk_usage(root).free
        expected = {"ltx-0.9.8": 11, "ltx-2.3": 85, "wan-vace": 12, "sam2": 1}[args.model] * 1024**3
        if free < expected:
            print(f"Available space: {free / 1024**3:.1f} GiB. This profile can require about {expected / 1024**3:.0f} GiB including cache. Reuse an existing cache or free space before downloading.")
            raise SystemExit(1)
        download_model(args.model, root, args.cache_dir, lambda _, message: print(message, flush=True), task="text-to-video" if args.base_only else None)
    print("Nodes installed. In ComfyUI's Python environment run:")
    print(f"python -m pip install -r {target / 'requirements.txt'}")
    if args.model == "ltx-2.3":
        print(f"python -m pip install -r {root / 'custom_nodes/ComfyUI-LTXVideo/requirements.txt'}")
    print(f"For SAM2 tracking: SAM2_BUILD_CUDA=0 python -m pip install git+https://github.com/facebookresearch/sam2.git@{SAM2_COMMIT}")
    print("Provision tracker weights separately with: python -m engine.setup --comfy-dir <path> --model sam2")
    print("Restart ComfyUI, then select Local ComfyUI in OpenFrame and check connection.")

if __name__ == "__main__":
    main()
