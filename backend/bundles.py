"""Portable recipe archives, streamed without duplicating source media on disk."""
from __future__ import annotations

import copy
import io
import json
import zipfile
from collections import deque
from pathlib import Path

from .media import public_asset


class ChunkWriter(io.RawIOBase):
    def __init__(self):
        super().__init__()
        self.pending = deque()
        self.position = 0

    def writable(self):
        return True

    def seekable(self):
        return False

    def tell(self):
        return self.position

    def write(self, data):
        if data:
            self.pending.append(bytes(data))
            self.position += len(data)
        return len(data)

    def drain(self):
        while self.pending:
            yield self.pending.popleft()


def stream_zip(entries):
    sink = ChunkWriter()
    with zipfile.ZipFile(sink, "w", allowZip64=True) as archive:
        for name, content, compress in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            if isinstance(content, Path):
                info.file_size = content.stat().st_size
                with archive.open(info, "w", force_zip64=True) as member, content.open("rb") as source:
                    yield from sink.drain()
                    while chunk := source.read(1024 * 1024):
                        member.write(chunk)
                        yield from sink.drain()
                yield from sink.drain()
            else:
                archive.writestr(info, content)
                yield from sink.drain()
    yield from sink.drain()


def _replace_strings(value, replacements):
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_strings(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_strings(item, replacements) for key, item in value.items()}
    return value


def bundle_entries(store, job, graph, project_root: Path, include_media: bool):
    from engine.models import MODEL_FILES, COMFY_COMMIT, LTX_NODES_COMMIT, SAM2_COMMIT
    inputs = {}
    files = []
    filenames = {}
    for role in ("source", "mask", "reference"):
        ident = job["request"].get(role + "_asset_id")
        if not ident:
            continue
        asset = store.get("assets", ident)
        if not asset:
            raise ValueError(f"The {role} asset is no longer available")
        path = Path(asset["path"]).resolve()
        if not path.is_relative_to(store.root) or not path.is_file():
            raise ValueError(f"The {role} media file is no longer available")
        filename = f"openframe/{job['id']}/{role}{path.suffix.lower()}"
        inputs[role] = {**public_asset(asset), "comfy_filename": filename,
                        "archive_path": "input/" + filename if include_media else None}
        filenames[role] = filename
        if include_media:
            files.append(("input/" + filename, path, False))
    portable = copy.deepcopy(graph)
    replacements = {}
    slots = [("source", "filename", "source"), ("source", "mask_filename", "mask"),
             ("image", "image", "source"), ("reference", "image", "reference"),
             ("save", "source_filename", "source")]
    for node_id, field, role in slots:
        node_inputs = portable.get(node_id, {}).get("inputs", {})
        if role in filenames and node_inputs.get(field):
            old = node_inputs[field]
            if isinstance(old, str):
                replacements[old] = filenames[role]
            node_inputs[field] = filenames[role]
    manifest = {
        "version": "0.1.0", "job_id": job["id"], "status": job["status"],
        "request": job["request"], "inputs": inputs, "outputs": job.get("outputs", []),
        "metadata": job.get("metadata", {}), "includes_media": include_media,
        "graph_note": "workflow_api.json relocates input filenames only. workflow_executed_api.json retains the original graph when available.",
    }
    task = job["request"]["task"]
    uses_sam2 = (task == "inpaint" and inputs.get("mask", {}).get("kind") == "image"
                 and job["request"].get("mask_tracking", True)
                 and job["request"].get("mask_tracking_method", "sam2") == "sam2")
    model_files = [entry for entry in MODEL_FILES[job["request"]["model_id"]]
                   if not entry.get("tasks") or task in entry["tasks"]]
    if uses_sam2:
        model_files.extend(MODEL_FILES["sam2"])
    requirements = {"model_id": job["request"]["model_id"], "task": task, "model_files": model_files,
                    "comfyui_commit": COMFY_COMMIT, "ltx_nodes_commit": LTX_NODES_COMMIT,
                    "custom_node_pack": "custom_nodes/openframe",
                    "checksum_note": "expected_sha256 values, when present, are expected upstream file hashes at the pinned revisions. Export does not re-hash installed model files or certify their local bytes."}
    if uses_sam2:
        requirements["sam2_package"] = {"repository": "https://github.com/facebookresearch/sam2.git", "revision": SAM2_COMMIT}
    entries = [
        ("workflow_api.json", json.dumps(portable, indent=2).encode(), True),
        ("manifest.json", json.dumps(manifest, indent=2).encode(), True),
        ("MODEL-REQUIREMENTS.json", json.dumps(requirements, indent=2).encode(), True),
    ]
    cloud_graph = job.get("metadata", {}).get("cloud_workflow")
    if job.get("workflow"):
        entries.append(("workflow_executed_api.json", json.dumps(cloud_graph or job["workflow"], indent=2).encode(), True))
    if cloud_graph:
        # A hosted graph covers diffusion; preserve the original complete graph
        # for local replay and explicitly include its CPU processing boundary.
        manifest["graph_note"] = "workflow_api.json is the stored complete local replay recipe. workflow_executed_api.json is the actual hosted Cloud diffusion graph; CLOUD-PROCESSING.json documents local preprocessing/compositing."
        entries = [(name, json.dumps(manifest, indent=2).encode() if name == "manifest.json" else data, compress) for name, data, compress in entries]
        cloud_portable = copy.deepcopy(cloud_graph)
        prepared = copy.deepcopy(job.get("metadata", {}).get("prepared_inputs", {}))
        cloud_names = {}
        for role, item in prepared.items():
            relative = item.get("relative_path")
            if relative:
                path = (store.root / "renders" / job["id"] / relative).resolve()
                if not path.is_relative_to(store.root / "renders" / job["id"]) or not path.is_file():
                    raise ValueError("Prepared Cloud input is no longer available")
                filename = f"openframe/{job['id']}/cloud-{Path(item['filename']).name}"
                if include_media:
                    files.append(("input/" + filename, path, False))
            else:
                filename = filenames[role]
            cloud_names[role] = filename
            item["comfy_filename"] = filename
            item["archive_path"] = "input/" + filename if include_media else None
        for node, field, role in (("cloud_source_file", "file", "source"), ("cloud_mask_file", "file", "generation_mask"), ("image", "image", "source"), ("reference", "image", "reference")):
            if node in cloud_portable and role in cloud_names:
                cloud_portable[node]["inputs"][field] = cloud_names[role]
        entries.extend([
            ("workflow_cloud_api.json", json.dumps(cloud_portable, indent=2).encode(), True),
            ("CLOUD-PROCESSING.json", json.dumps({"processing": job["metadata"].get("processing"), "prepared_inputs": prepared}, indent=2).encode(), True),
        ])
        tracking = job.get("metadata", {}).get("tracking")
        if tracking:
            entries.append(("TRACKER-EXECUTION.json", json.dumps(tracking, indent=2).encode(), True))
    if job.get("ui_workflow"):
        ui = _replace_strings(job["ui_workflow"], replacements)
        entries.append(("workflow_ui.json", json.dumps(ui, indent=2).encode(), True))
    node_dir = project_root / "custom_nodes" / "openframe"
    for name in ("__init__.py", "nodes.py", "media.py", "requirements.txt"):
        path = node_dir / name
        if path.is_file():
            entries.append(("custom_nodes/openframe/" + name, path, True))
    media_note = (
        "Original input media is included. Copy the CONTENTS of input/ into ComfyUI/input/.\n"
        if include_media else
        "Input media is not included. Supply the originals matching the manifest SHA-256 values.\nPlace each under ComfyUI/input/ using its manifest comfy_filename.\n"
    )
    tracker_note = (
        "This recipe uses SAM2 tracking. In ComfyUI's Python environment also run:\n"
        f"SAM2_BUILD_CUDA=0 python -m pip install git+https://github.com/facebookresearch/sam2.git@{SAM2_COMMIT}\n"
        "The tracker checkpoint is included in MODEL-REQUIREMENTS.json under category sam2.\n"
        if uses_sam2 else ""
    )
    gated_repositories = sorted({entry["repo"] for entry in model_files if entry.get("requires_access")})
    access_note = (
        "Before downloading restricted weights, obtain access for your own account at:\n"
        + "\n".join(f"https://huggingface.co/{repo}" for repo in gated_repositories)
        + "\nAuthenticate in the download environment; no access token is included in this bundle.\n"
        if gated_repositories else ""
    )
    readme = f"""OpenFrame portable ComfyUI recipe

{media_note}
1. Use ComfyUI revision {COMFY_COMMIT} or a verified compatible version.
2. Ensure ffmpeg and ffprobe are on PATH. Copy custom_nodes/openframe into your ComfyUI
   custom_nodes directory and install its requirements in ComfyUI's Python environment.
3. For LTX 2.3 editing, install Lightricks/ComfyUI-LTXVideo at {LTX_NODES_COMMIT}
   and install that node pack's requirements in the same Python environment.
4. Download the weights listed in MODEL-REQUIREMENTS.json into the listed model categories.
   Each entry includes an upstream repository, exact revision and filename. Weights are not bundled.
   When present, expected_sha256 and size_bytes describe the expected upstream file. Compare
   them against your downloaded file; creating this bundle does not verify installed weight bytes.
5. Restart ComfyUI. Submit workflow_api.json through its /prompt API, or load workflow_ui.json
   into the canvas when the bundle includes it. Missing UI export does not prevent API execution.
6. Use the input filenames recorded in manifest.json. They already match workflow_api.json.

{tracker_note}{access_note}
manifest.json preserves the selected model, seed, parameters and input hashes.
The portable graph changes only input filenames. The original executed graph, when present,
is retained separately. No provider credentials are required by the exported local graph.
Output media is not duplicated into this recipe; download it from the job's output assets.
Equivalent output quality or bitwise equality across different GPUs/runtime versions is not guaranteed.
"""
    if cloud_graph:
        readme += "\nHOSTED CLOUD HYBRID EXECUTION\nworkflow_api.json replays the complete stored pipeline on local ComfyUI with the bundled utilities.\nworkflow_executed_api.json records the actual Cloud diffusion graph. workflow_cloud_api.json relocates its prepared inputs for inspection/re-execution; this graph alone returns PNG frames, not the final composite.\nThe original source/mask and prepared Cloud inputs are included when media was requested. CLOUD-PROCESSING.json records local mask preparation, plate compositing and audio/encoding. Run the full recipe locally or reuse its request through OpenFrame's Cloud provider to obtain the final video.\nCloud node/runtime versions are provider-managed; pinned local runtime requirements describe the replay environment, not an attestation of Cloud's runtime.\n"
    entries.insert(0, ("README.txt", readme.encode(), True))
    return entries + files
