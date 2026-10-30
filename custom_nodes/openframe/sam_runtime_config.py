"""Portable configuration for the pinned, isolated official SAM3.1 runtime."""
import os
from pathlib import Path
import sys

SAM3_COMMIT = "f1647e8d0c1d280991f4d1b7d974c2704537fe66"
SAM3_REVISION = "daa63191845a41281374e725f4c9e51c7a824460"
VITMATTE_REVISION = "bf486d01a7d9e3dbcc8400f7942835caf0eaf76e"
MATTING_TRANSFORMERS = "4.57.1"


def runtime_python():
    # The fallback preserves deployed graphs; public users configure their own
    # isolated interpreter on the ComfyUI host, never on the lightweight web UI.
    return Path(os.environ.get("OPENFRAME_SAM3_PYTHON") or "/opt/openframe-matting/bin/python").expanduser()


def official_support_status(models_dir):
    if sys.platform != "linux" or not hasattr(os, "memfd_create"):
        return False, "Official support requires a Linux CUDA ComfyUI host; native Windows/macOS is not supported by this isolated runtime."
    if not runtime_python().is_file():
        return False, "Configure OPENFRAME_SAM3_PYTHON with the provisioned isolated interpreter; see RECAST-RUNTIME.md."
    if not (Path(models_dir) / "matting/sam3.1/sam3.1_multiplex.pt").is_file():
        return False, "Provision the pinned official SAM3.1 checkpoint in models/matting/sam3.1; inference never downloads it."
    return True, "Runtime path and checkpoint present; CUDA and pinned package imports are checked when the isolated predictor starts."
