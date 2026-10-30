"""Namespace-only adaptation of an already checked-out pinned VDA source tree.

Run in the remote build or an explicitly prepared ComfyUI deployment. No model
download, dependency installation or inference occurs in this helper.
"""
from pathlib import Path
import sys


def prepare(source):
    root = Path(source)
    module = root / "video_depth_anything" / "video_depth.py"
    source_helper = root / "utils" / "util.py"
    target = root / "video_depth_anything" / "util" / "openframe_alignment.py"
    original = "from utils.util import compute_scale_and_shift, get_interpolate_frames"
    replacement = "from .util.openframe_alignment import compute_scale_and_shift, get_interpolate_frames"
    text = module.read_text()
    if text.count(original) == 1:
        module.write_text(text.replace(original, replacement))
    elif replacement not in text:
        raise ValueError("The pinned VDA source layout changed; refusing an unverified import patch.")
    content = source_helper.read_bytes()
    if not target.exists() or target.read_bytes() != content:
        target.write_bytes(content)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python setup_depth_source.py /path/to/Video-Depth-Anything")
    prepare(sys.argv[1])
