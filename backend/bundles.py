"""Portable recipe archives, streamed without duplicating source media on disk."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile
from collections import deque
from pathlib import Path

from .media import public_asset
from .models import request_asset_ids


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


def portable_replay_record(job):
    """Separate unexecuted Local replay manifest; never mutate an execution receipt.

    The release caller must select approved public inputs/results. Pass the
    original recorded API graph separately to bundle_entries; it is relocated
    there without changing sampling. This is not a Cloud execution claim.
    """
    if not job.get("workflow") or job.get("kind") == "character-training":
        raise ValueError("A completed media workflow is required for a portable replay export")
    from engine.catalog import model_by_id
    profile = model_by_id(job["request"]["model_id"]) or {}
    if "local" not in profile.get("supported_providers", ["local"]):
        raise ValueError("The recorded profile does not implement Local replay")
    original_request = job["request"]
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    request = copy.deepcopy(original_request)
    request["provider"] = "local"
    metadata = {"execution": "unexecuted-local-replay", "replay_provider": "local",
        "validation_origin": "A separate original execution receipt is retained privately. This export has not been executed on its replay target.",
        "original_request_sha256": digest(original_request), "original_api_graph_sha256": digest(job["workflow"])}
    prompt = job.get("metadata", {}).get("video_prompt")
    if prompt:
        metadata["recorded_video_prompt"] = {key: prompt[key] for key in ("original", "model_prompt", "enhanced") if key in prompt}
    output_fields = {"id", "name", "kind", "role", "width", "height", "frames", "fps", "duration", "has_audio", "sha256", "size", "mime_type"}
    return {"id": job["id"], "status": "replay-not-executed", "request": request,
        "ui_workflow": copy.deepcopy(job.get("ui_workflow")), "metadata": metadata,
        "outputs": [{key: value for key, value in output.items() if key in output_fields} for output in job.get("outputs", [])]}


def bundle_entries(store, job, graph, project_root: Path, include_media: bool):
    from engine.models import MODEL_FILES, COMFY_COMMIT, LTX_NODES_COMMIT, SAM2_COMMIT, model_destination, required_model_files
    inputs = {}
    files = []
    filenames = {}
    for role, ident in request_asset_ids(job["request"]).items():
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
    slots = [("source", "filename", "source"), ("source", "image", "source"), ("source", "mask_filename", "mask"),
             ("image", "image", "source"), ("reference", "image", "reference"), ("reference", "source_filename", "source"),
             ("relight_sphere", "filename", "reference"),
             ("save", "source_filename", "source"), ("save_uncomposited", "source_filename", "source"),
             ("speech", "audio", "audio"), ("mask", "image", "mask")]
    slots.append(("save", "audio_filename", "audio"))
    slots.extend([("transition_inputs", "source_filename", "source"), ("transition_inputs", "end_filename", "end"),
                  ("save", "end_filename", "end")])
    slots.extend((f"reference_{index}", "image", f"reference_{index}") for index in range(10))
    for node_id, node in portable.items():
        if node.get("class_type") in {"OpenFrameVideoDepth", "OpenFrameSourceAudio", "OpenFrameCanvasVideo", "OpenFrameVideoEdit", "OpenFrameSemanticMatte"}:
            slots.append((node_id, "filename", "source"))
    for node_id, field, role in slots:
        node_inputs = portable.get(node_id, {}).get("inputs", {})
        if role in filenames and node_inputs.get(field):
            old = node_inputs[field]
            if isinstance(old, str):
                replacements[old] = filenames[role]
            node_inputs[field] = filenames[role]
    if job.get("kind") == "character-training":
        training_inputs = portable.get("train", {}).get("inputs", {})
        original = json.loads(training_inputs.get("dataset_json", "[]"))
        ordered = [filenames[f"dataset_{index}"] for index in range(len(job["request"].get("dataset_asset_ids", [])))]
        if len(original) != len(ordered):
            raise ValueError("Stored training graph dataset does not match the immutable training inputs")
        training_inputs["dataset_json"] = json.dumps(ordered)
        mask_ids = job["request"].get("loss_mask_asset_ids", [])
        original_masks = json.loads(training_inputs.get("loss_masks_json", "[]"))
        if len(original_masks) != len(mask_ids) or (mask_ids and len(mask_ids) != len(ordered)):
            raise ValueError("Stored training graph loss masks do not match its ordered dataset")
        if mask_ids:
            training_inputs["loss_masks_json"] = json.dumps([filenames[f"loss_mask_{index}"] for index in range(len(mask_ids))])
    manifest = {
        "version": "0.1.0", "job_id": job["id"], "status": job["status"],
        "request": job["request"], "inputs": inputs, "outputs": job.get("outputs", []),
        "metadata": job.get("metadata", {}), "includes_media": include_media,
        "graph_note": "workflow_api.json relocates input filenames only. workflow_executed_api.json retains the original graph when available.",
    }
    if job.get("app_context"):
        manifest["app_context"] = job["app_context"]
    task = job["request"]["task"]
    uses_official_recast = (job["request"]["model_id"] == "scail-2"
                           and job["request"].get("recast_composite_tracking") in {"official", "official-union"})
    from engine.catalog import model_by_id
    uses_sam2 = (task in {"inpaint", "character-replacement"} and not (model_by_id(job["request"]["model_id"]) or {}).get("native_mask_tracking") and inputs.get("mask", {}).get("kind") == "image"
                 and job["request"].get("mask_tracking", True)
                 and job["request"].get("mask_tracking_method", "sam2") == "sam2")
    model_files = [entry for entry in required_model_files(job["request"]["model_id"], job["request"])
                   if not (entry.get("role") == "prompt_expander" and "prompt_model" not in graph)]
    if uses_sam2:
        model_files.extend(MODEL_FILES["sam2"])
    model_files = [{**entry, "destination": "models/" + model_destination(entry).as_posix()} for entry in model_files]
    requirements = {"model_id": job["request"]["model_id"], "task": task, "model_files": model_files,
                    "comfyui_commit": COMFY_COMMIT, "ltx_nodes_commit": LTX_NODES_COMMIT,
                    "custom_node_pack": "custom_nodes/openframe",
                    "checksum_note": "expected_sha256 values, when present, are expected upstream file hashes at the pinned revisions. Export does not re-hash installed model files or certify their local bytes."}
    profile = model_by_id(job["request"]["model_id"]) or {}
    if profile.get("workflow_source"):
        requirements["workflow_source"] = copy.deepcopy(profile["workflow_source"])
    if job["request"]["model_id"] == "qwen-portrait-relight":
        requirements["portrait_relight_runtime"] = {
            "installation": "Follow custom_nodes/openframe/PORTRAIT-RELIGHT.md on the Local ComfyUI GPU host; hosted Cloud is unsupported",
            "alpha_compute": "CPU ViTMatte using ComfyUI Transformers; no separate Linux-only video runtime",
            "tested_transformers": "5.21.0; bounded float-alpha comparison to 4.57.1 is recorded, not bit-identical",
            "required_nodes": ["OpenFramePortraitAlphas", "SAM3_VideoTrack", "SCAIL2ColoredMask", "FluxKontextImageScale", "MaskComposite", "ImageCompositeMasked"],
            "licenses": "MIT workflow; Apache2 Qwen/ViTMatte; SAM License segmentation; weights not bundled",
        }
    if job["request"].get("vace_reference_mode") == "first-frame":
        source = profile.get("first_frame_conditioning_source")
        if not source:
            raise ValueError("The first-frame workflow has no declared upstream conditioning source")
        requirements["first_frame_conditioning_source"] = copy.deepcopy(source)
    if uses_official_recast:
        from engine.matte_models import SAM3_COMMIT, SAM3_REVISION, MATTING_TRANSFORMERS
        requirements["official_recast_tracking"] = {
            "repository": "https://github.com/facebookresearch/sam3.git", "revision": SAM3_COMMIT,
            "model_revision": SAM3_REVISION, "transformers": MATTING_TRANSFORMERS,
            "purpose": "Binary performer support for final compositing; native SCAIL conditioning is unchanged",
            "selection": "First-frame overlap with the native selected performer must reach IoU 0.5",
            "vitmatte_required": False,
            "installation": "Follow custom_nodes/openframe/RECAST-RUNTIME.md on the configured Linux/WSL2 CUDA ComfyUI host; no private worker account is required",
        }
        if job["request"].get("recast_composite_tracking") == "official-union":
            requirements["official_recast_tracking"].update(
                mode="official-union",
                selection="Each official source/generated pass must match the same native source performer at first-frame IoU >= 0.5; no unmatched fallback",
                support="Union of native-source, official-source and official-generated binary performer masks; selected margin/feather apply once after union",
            )
    if job["request"]["model_id"] in {"flux3-klein", "flux3-klein-int8", "flux3-klein-base"}:
        from engine.image_models import FLUX3_TEMPLATE_REVISION
        requirements["native_template_source"] = {"repository": "https://github.com/Comfy-Org/workflow_templates", "revision": FLUX3_TEMPLATE_REVISION}
        requirements["image_pipeline"] = {
            "checkpoint_variant": "base" if job["request"]["model_id"] == "flux3-klein-base" else "distilled", "sampler": "euler", "scheduler": "simple",
            "prompt_expansion": "native Comfy Qwen3.5 FLUX3 checkpoint" if "prompt_model" in graph else "user-provided caption",
            "caption_record": "manifest.json metadata.image_prompt; original request remains unchanged",
            "preservation": job["request"].get("image_preservation", "none"),
            "edit_focus": job["request"].get("image_edit_focus", "full"),
            "boxes_note": "Boxes guide composition, not hard pixels. Image preservation is explicit original-pixel compositing.",
            "license": "FLUX Kommunity License 1.0; see pinned upstream LICENSE.md and component notices",
        }
        if job["request"].get("image_edit_focus") == "masked-region":
            dependency = profile.get("region_focus_dependency")
            if not dependency:
                raise ValueError("The masked-region workflow has no declared external crop/stitch dependency")
            requirements.setdefault("additional_node_packages", []).append(copy.deepcopy(dependency))
    if job["request"].get("_character_adapter"):
        requirements["character_adapter"] = {**job["request"]["_character_adapter"], "included_in_bundle": False,
            "destination": "models/loras/" + job["request"]["_character_adapter"]["lora_name"],
            "source": "Owner-controlled model cache on the recorded training host. Registered adapter use is bound to that provider/host and verified by SHA256. Never substitute a distilled base."}
    if job.get("kind") == "character-training":
        from engine.training_models import BASE_REVISION, BASE_SHA256, DIFFUSERS_TRAINING_COMMIT
        requirements["character_training"] = {"trainer_repository": "https://github.com/huggingface/diffusers",
            "trainer_revision": DIFFUSERS_TRAINING_COMMIT, "base_revision": BASE_REVISION, "base_sha256": BASE_SHA256,
            "runtime": "Follow custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md on the configured Linux CUDA ComfyUI host. No private worker account is required; model weights stay on that host.",
            "private_adapter_included": False, "training_job_id": job["id"]}
    if job["request"]["model_id"] in {"ming-narration", "qwen-caption"}:
        from engine.narration_models import MING_COMMIT, ASR_COMMIT
        requirements["sequence_audio_runtime"] = {"compute": "configured Linux/WSL2 CUDA ComfyUI host", "hosted_cloud_supported": False,
            "ming_repository": "https://github.com/inclusionAI/Ming-3.0-tts", "ming_revision": MING_COMMIT,
            "asr_repository": "https://github.com/QwenLM/Qwen3-ASR", "asr_revision": ASR_COMMIT,
            "installation": "Follow custom_nodes/openframe/NARRATION-RUNTIME.md and retain the four bundled companion engine modules; do not replace ComfyUI's transformers installation.",
            "transcript_note": "Word times come from recognition and forced alignment of actual selected audio; text still requires review."}
    if uses_sam2:
        requirements["sam2_package"] = {"repository": "https://github.com/facebookresearch/sam2.git", "revision": SAM2_COMMIT}
    if job["request"]["model_id"] == "wan-animate":
        from engine.models import WAN_ANIMATE_PREPROCESS_COMMIT
        requirements["additional_node_packages"] = [{"repository": "https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git", "revision": WAN_ANIMATE_PREPROCESS_COMMIT,
                                                       "dependencies": ["onnxruntime>=1.20,<2", "matplotlib>=3.9,<4"]}]
    if job["request"]["model_id"] == "longcat-avatar-1.5":
        from engine.video_models import WAN_WRAPPER_COMMIT
        requirements["additional_node_packages"] = [{"repository": "https://github.com/kijai/ComfyUI-WanVideoWrapper.git", "revision": WAN_WRAPPER_COMMIT,
            "directory": "custom_nodes/ComfyUI-WanVideoWrapper", "install_requirements": True}]
    if job["request"]["model_id"] == "ldf-vfi":
        from engine.utility_models import TWEEN_COMMIT, LDF_SOURCE_COMMIT, LDF_SOURCE_SHA256
        requirements["additional_node_packages"] = [{"repository": "https://github.com/Ethanfel/ComfyUI-Tween.git", "revision": TWEEN_COMMIT,
            "directory": "custom_nodes/ComfyUI-Tween", "install_requirements": True}]
        requirements["ldf_source"] = {"repository": "https://github.com/onecat-ai/LDF-VFI", "revision": LDF_SOURCE_COMMIT,
                                      "expected_sha256": LDF_SOURCE_SHA256, "note": "Use the offline source guard in the bundled OpenFrameLoadLDF node; no runtime weight downloads."}
    from engine.depth_models import DEPTH_PACKAGES
    if job["request"]["model_id"] in DEPTH_PACKAGES:
        requirements["depth_source"] = DEPTH_PACKAGES[job["request"]["model_id"]]
        requirements["python_dependencies"] = ["einops>=0.7", "huggingface-hub>=0.23", "tqdm", "opencv-python", "Pillow", "numpy"]
        requirements["depth_runtime"] = "CUDA with the compatible ComfyUI Torch/torchvision environment. Do not install the upstream VDA's old Torch/xformers pins over ComfyUI."
    if job["request"]["model_id"] == "kokoro-82m":
        requirements["python_dependencies"] = ["kokoro==0.9.4", "misaki[en]==0.9.4", "spacy>=3.8,<3.9",
            "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]
        requirements["system_dependencies"] = ["espeak-ng"]
    if job["request"]["model_id"] == "flux-klein-editvid":
        from engine.editvid_models import EDITVID_DEPENDENCY
        requirements["additional_node_packages"] = [copy.deepcopy(EDITVID_DEPENDENCY)]
        requirements["license_restriction"] = "FLUX Non-Commercial License v2.1 applies to the 9B weights. Apache-2.0 code does not make these weights commercially unrestricted. No hosted Cloud route."
        requirements["installation"] = "Follow custom_nodes/openframe/EDITVID-RUNTIME.md on the configured ComfyUI GPU host. Do not substitute 4B, Base, FLUX3 or quantized weights."
    entries = [
        ("workflow_api.json", json.dumps(portable, indent=2).encode(), True),
        ("manifest.json", json.dumps(manifest, indent=2).encode(), True),
        ("MODEL-REQUIREMENTS.json", json.dumps(requirements, indent=2).encode(), True),
    ]
    if job.get("app_context"):
        with store.connection() as db:
            association = db.execute("SELECT record FROM app_job_links WHERE job_id=?", (job["id"],)).fetchone()
        if association:
            entries.append(("APP-CONTEXT.json", json.dumps(json.loads(association[0]), indent=2).encode(), True))
    cloud_graph = job.get("metadata", {}).get("cloud_workflow")
    if job.get("workflow"):
        entries.append(("workflow_executed_api.json", json.dumps(cloud_graph or job["workflow"], indent=2).encode(), True))
    if cloud_graph:
        # A hosted graph covers diffusion; preserve the original complete graph
        # for local replay and explicitly include its CPU processing boundary.
        native_video = job.get("metadata", {}).get("processing", {}).get("cloud_output") == "native-composite-video"
        manifest["graph_note"] = "workflow_api.json is the stored complete local replay recipe. workflow_executed_api.json is the actual hosted Cloud graph; CLOUD-PROCESSING.json documents its outputs and explicit local processing boundaries."
        entries = [(name, json.dumps(manifest, indent=2).encode() if name == "manifest.json" else data, compress) for name, data, compress in entries]
        cloud_portable = copy.deepcopy(cloud_graph)
        prepared = copy.deepcopy(job.get("metadata", {}).get("prepared_inputs", {}))
        cloud_names = {}
        cloud_ui_names = {}
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
            cloud_ui_names[item["filename"]] = filename
            item["comfy_filename"] = filename
            item["archive_path"] = "input/" + filename if include_media else None
        from engine.cloud import input_slots
        for node, field, role in input_slots(cloud_portable):
            if node in cloud_portable and role in cloud_names:
                cloud_portable[node]["inputs"][field] = cloud_names[role]
        entries.extend([
            ("workflow_cloud_api.json", json.dumps(cloud_portable, indent=2).encode(), True),
            ("CLOUD-PROCESSING.json", json.dumps({"processing": job["metadata"].get("processing"), "prepared_inputs": prepared}, indent=2).encode(), True),
        ])
        if job["metadata"].get("cloud_ui_workflow"):
            entries.append(("workflow_cloud_ui.json", json.dumps(_replace_strings(job["metadata"]["cloud_ui_workflow"], cloud_ui_names), indent=2).encode(), True))
        tracking = job.get("metadata", {}).get("tracking")
        if tracking:
            entries.append(("TRACKER-EXECUTION.json", json.dumps(tracking, indent=2).encode(), True))
    if job.get("ui_workflow"):
        ui = _replace_strings(job["ui_workflow"], replacements)
        entries.append(("workflow_ui.json", json.dumps(ui, indent=2).encode(), True))
    node_dir = project_root / "custom_nodes" / "openframe"
    if job["request"].get("recast_reference_cleanup"):
        entries.append(("custom_nodes/openframe/REFERENCE-CLEANUP.md", node_dir / "REFERENCE-CLEANUP.md", True))
    if job["request"]["model_id"] == "ltx-ripple":
        for name in ("PaintAPlate-LICENSE.txt", "LTX-Ripple-LICENSE-2_x.txt"):
            entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"]["model_id"] == "ltx-2.3-transition":
        name = "Comfy-workflow-templates-LICENSE.txt"
        entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"]["model_id"] == "ltx-2.3-relight":
        name = "sphere-light-MIT.txt"
        entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"]["model_id"] == "qwen-image-relight":
        name = "IC-Light-Apache-2.0.txt"
        entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"]["model_id"] == "flux-klein-editvid":
        entries.append(("custom_nodes/openframe/EDITVID-RUNTIME.md", node_dir / "EDITVID-RUNTIME.md", True))
        for name in ("EditVid-native-Apache-2.0.txt", "EditVid-upstream-Apache-2.0.txt", "FLUX2-Klein9B-Non-Commercial.txt"):
            entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"]["model_id"] == "qwen-portrait-relight":
        entries.append(("custom_nodes/openframe/PORTRAIT-RELIGHT.md", node_dir / "PORTRAIT-RELIGHT.md", True))
        for name in ("Comfy-workflow-templates-LICENSE.txt", "SAM3.1-LICENSE.txt"):
            entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if job["request"].get("inpaint_composite_mode") == "plate-fit":
        name = "PAINTAPLATE_LICENSE.txt"
        entries.append(("LICENSES/" + name, node_dir / name, True))
    if job["request"].get("image_edit_focus") == "masked-region":
        name = "Inpaint-CropAndStitch-GPL-3.0.txt"
        entries.append(("LICENSES/" + name, project_root / "docs/licenses" / name, True))
    if uses_official_recast or job["request"]["model_id"] == "sam3.1-vitmatte":
        entries.append(("custom_nodes/openframe/RECAST-RUNTIME.md", node_dir / "RECAST-RUNTIME.md", True))
    if job["request"]["model_id"] in {"ming-narration", "qwen-caption"}:
        entries.append(("custom_nodes/openframe/NARRATION-RUNTIME.md", node_dir / "NARRATION-RUNTIME.md", True))
        for name in ("__init__.py", "narration_models.py", "narration_workflows.py", "narration_runtime.py"):
            entries.append(("engine/" + name, project_root / "engine" / name, True))
    if job.get("kind") == "character-training":
        entries.append(("custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md", node_dir / "CHARACTER-TRAINING-RUNTIME.md", True))
        if job["request"].get("loss_mask_asset_ids"):
            entries.append(("LICENSES/Fizgig-LICENSE.txt", project_root / "docs/licenses/Fizgig-LICENSE.txt", True))
        for path in sorted((project_root / "engine").glob("*.py")):
            entries.append(("engine/" + path.name, path.read_bytes(), True))
    for path in [*sorted(node_dir.glob("*.py")), node_dir / "requirements.txt", node_dir / "CANNY_LICENSE.txt", node_dir / "PAINTAPLATE_LICENSE.txt"]:
        if path.is_file():
            entries.append(("custom_nodes/openframe/" + path.name, path, True))
    if requirements.get("depth_source"):
        entries.append(("setup_depth_source.py", project_root / "engine/depth_setup.py", True))
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
    preprocess_note = ""
    if job["request"]["model_id"] == "wan-animate":
        preprocess_note = (
            "This recipe uses native Wan Animate pose/face preprocessing. Install the node pack:\n"
            "git clone https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git custom_nodes/ComfyUI-WanAnimatePreprocess\n"
            f"git -C custom_nodes/ComfyUI-WanAnimatePreprocess checkout {WAN_ANIMATE_PREPROCESS_COMMIT}\n"
            "python -m pip install -r custom_nodes/ComfyUI-WanAnimatePreprocess/requirements.txt\n"
            "python -m pip install 'onnxruntime>=1.20,<2' 'matplotlib>=3.9,<4'\n"
        )
    speech_note = ""
    if job["request"]["model_id"] == "kokoro-82m":
        speech_note = (
            "This recipe generates speech on CPU. Install espeak-ng with your OS package manager.\n"
            "In ComfyUI's Python environment install the exact python_dependencies in MODEL-REQUIREMENTS.json,\n"
            "including the pinned English spaCy model wheel. Install every listed tts/kokoro model/voice file.\n"
            "The node does not fetch dependencies or weights at generation time.\n"
        )
    package_note = ""
    for package in requirements.get("additional_node_packages", []):
        if package.get("directory"):
            package_note += (f"git clone {package['repository']} {package['directory']}\n"
                             f"git -C {package['directory']} checkout {package['revision']}\n"
                             f"python -m pip install -r {package['directory']}/requirements.txt\n")
    if requirements.get("depth_source"):
        package = requirements["depth_source"]
        package_note += (f"Temporal depth source: {package['license']}\n"
                         f"git clone {package['repository']} {package['directory']}\n"
                         f"git -C {package['directory']} checkout {package['revision']}\n")
        if package.get("patch"):
            package_note += f"python setup_depth_source.py {package['directory']}\n"
        package_note += ("Install the depth python_dependencies in MODEL-REQUIREMENTS.json into ComfyUI's CUDA environment.\n"
                         "Do not install VDA's historical Torch/xformers requirement pins. Model files must already exist.\n"
                         "The preview is grayscale near-white; the separate FFV1 16-bit stream requires manifest metadata.depth\n"
                         "to decode its relative values. Zero means invalid. Neither profile reports metric distance.\n")
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
3. For LTX editing, install Lightricks/ComfyUI-LTXVideo at {LTX_NODES_COMMIT}
   and install that node pack's requirements in the same Python environment.
4. Download the weights listed in MODEL-REQUIREMENTS.json into the listed model categories.
   Each entry includes an upstream repository, exact revision, filename and destination relative
   to ComfyUI. Use destination: upstream subfolders such as voices/ are flattened. Weights are not bundled.
   When present, expected_sha256 and size_bytes describe the expected upstream file. Compare
   them against your downloaded file; creating this bundle does not verify installed weight bytes.
5. Restart ComfyUI. Submit workflow_api.json through its /prompt API, or load workflow_ui.json
   into the canvas when the bundle includes it. Missing UI export does not prevent API execution.
6. Use the input filenames recorded in manifest.json. They already match workflow_api.json.

{tracker_note}{preprocess_note}{speech_note}{package_note}{access_note}
manifest.json preserves the selected model, seed, parameters and input hashes.
The portable graph changes only input filenames. The original executed graph, when present,
is retained separately. No provider credentials are required by the exported local graph.
Output media is not duplicated into this recipe; download it from the job's output assets.
Equivalent output quality or bitwise equality across different GPUs/runtime versions is not guaranteed.
"""
    if cloud_graph:
        output_note = ("This native graph returns a composited H264 CRF17 video with selected audio and an optional raw video. If CLOUD-PROCESSING.json declares host_lighting_correction, host_plate_fit or host_bitrate_target, the app additionally creates its named finished result locally; the native composite is retained as a preview. The native graph alone does not perform that correction or the app's Standard/High bitrate encoding." if native_video else "This graph alone returns PNG frames, not the final composite; the app performs final compositing/audio encoding locally.")
        readme += "\nHOSTED CLOUD EXECUTION\nworkflow_api.json replays the complete stored pipeline on local ComfyUI with the bundled utilities.\nworkflow_executed_api.json records the actual Cloud graph. workflow_cloud_api.json relocates its prepared inputs for inspection/re-execution. " + output_note + "\nOriginal source/mask and prepared inputs are included when media was requested. CLOUD-PROCESSING.json describes the processing boundaries. No rented-GPU relay is used.\nCloud node/runtime versions are provider-managed; pinned local requirements describe replay, not an attestation of Cloud's runtime.\n"
    if job.get("kind") == "character-training":
        readme += "\nCHARACTER TRAINING\nThis is a training graph, not a generated-image recipe. Follow custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md for the pinned Diffusers environment on your configured Linux CUDA ComfyUI host. Copy the bundled engine package alongside ComfyUI or make its root importable as described there. No private worker account is required. Dataset filenames in train.dataset_json are relocated; recorded training configuration remains unchanged. Adapter and optimizer checkpoints stay on the selected training host and are not included. Running this graph again starts training; it is not an inference-only adapter preview or an automatic checkpoint resume. Registered adapter use remains bound to its original provider/host.\n"
    if requirements.get("character_adapter"):
        readme += "\nTRAINED ADAPTER\nThe exact private LoRA described in MODEL-REQUIREMENTS.json must be supplied by its owner at the recorded models/loras path on its registered training host. It is not downloaded or copied into this archive. Use only the matching undistilled base checkpoint; the native loader verifies its recorded SHA256.\n"
    if job["request"]["model_id"] in {"ming-narration", "qwen-caption"}:
        readme += "\nSEQUENCE NARRATION / CAPTIONS\nFollow custom_nodes/openframe/NARRATION-RUNTIME.md for the isolated Ming/Qwen runtimes on your configured Linux/WSL2 CUDA ComfyUI host. Keep the four bundled engine modules importable. No private worker account or execution flag is required; hosted Comfy Cloud does not provide this custom runtime. Weights stay on your configured ComfyUI model host. Normalized production synthesis is not the raw-text benchmark setting. Recognized text and actual word timing are recorded in manifest.json metadata.narration; captions may need human correction.\n"
    if job["request"]["model_id"] == "sam3.1-vitmatte":
        readme += "\nPROMPTED VIDEO MATTE\nFollow custom_nodes/openframe/RECAST-RUNTIME.md for the isolated SAM3.1/ViTMatte runtime on your configured Linux/WSL2 CUDA ComfyUI host. No private worker account is required. Obtain authorized access to the pinned SAM3.1 weights under its upstream license. Semantic tracking selects the concept; ViTMatte refines alpha per frame. Temporal alpha stability is not guaranteed merely by a completed run.\n"
    if job["request"].get("recast_reference_cleanup"):
        readme += "\nREFERENCE EDGE CLEANUP\nFollow custom_nodes/openframe/REFERENCE-CLEANUP.md. This graph refines only the appearance reference before SCAIL VAE conditioning, using pinned CPU ViTMatte and MIT PyMatting foreground recovery. Original CLIP input and native identity masks remain unchanged. Install the declared matting/vitmatte files and numba in the ComfyUI environment. It is independent of final composite tracking and does not guarantee exact hands, objects or identity.\n"
    if uses_official_recast:
        readme += "\nRECAST COMPOSITE SUPPORT\nThe official SAM3.1 runtime supplies binary performer support for final compositing only. Native SCAIL generation conditioning stays unchanged. Follow custom_nodes/openframe/RECAST-RUNTIME.md on your configured Linux/WSL2 CUDA ComfyUI host; no private worker account is required. Only the pinned SAM checkpoint is required for this support pass; ViTMatte weights are not required. Obtain authorized upstream model access. Tracking and held-object preservation still require visual review.\n"
        if job["request"].get("recast_composite_tracking") == "official-union":
            readme += "This explicit union mode combines native-source, official-source and official-generated performer support. Both official actors must separately match the same native-source actor at first-frame IoU >= 0.5. Margin and feather apply once after the union; this can include more original background in the editable region and does not guarantee perfect edges.\n"
    if job["request"]["model_id"] == "flux-klein-editvid":
        readme += "\nOPTIONAL EDITVID / NON-COMMERCIAL\nFollow custom_nodes/openframe/EDITVID-RUNTIME.md. This native-port workflow runs only on your configured Local ComfyUI host; it is not a hosted Cloud graph. The pinned 9B weights carry FLUX Non-Commercial License v2.1. Source and edit descriptions are separate conditioning inputs. The selected interval is decoded at native size, resampled to24fps and center-fit with native Lanczos. Review action, ghost trails and regenerated faces/details. Existing private short-clip evidence is not full-length or independently installed PC validation.\n"
    entries.insert(0, ("README.txt", readme.encode(), True))
    return entries + files
