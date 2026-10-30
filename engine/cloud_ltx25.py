"""Native hosted LTX 2.5 inpaint, with explicit CPU input/lighting boundaries.

The sampling recipe is the canonical released IC-LoRA graph. Only OpenFrame
media utilities are translated. No alternate model or remote GPU relay is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


INPUT_SLOTS = (
    ("cloud_source_file", "file", "source"),
    ("cloud_mask_file", "file", "generation_mask"),
    ("cloud_alpha_file", "file", "composite_mask"),
    ("source_audio", "audio", "source_audio"),
    ("reference", "image", "reference"),
    ("cloud_reference_padded", "image", "reference_padded"),
)
OUTPUT_NODES = ("save", "save_uncomposited", "save_frames", "save_audio", "save_prompt")


def validate_graph(graph, catalogue):
    """Validate the actual hosted schemas, including selected dynamic widgets."""
    from .cloud import _validate
    from .export import _canvas_inputs
    _validate(graph, catalogue)
    for name, spec in graph.items():
        schema = catalogue[spec["class_type"]]
        required = {"input": {"required": schema.get("input", {}).get("required", {})},
                    "input_order": {"required": schema.get("input_order", {}).get("required", [])}}
        if not required["input_order"]["required"]:
            required.pop("input_order")
        for field, field_schema in _canvas_inputs(required, spec["inputs"]):
            if field not in spec["inputs"]:
                raise ValueError(f"Hosted schema requires {name}.{field}.")
            value = spec["inputs"][field]
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                if value[0] not in graph or value[1] >= len(catalogue[graph[value[0]]["class_type"]].get("output", [])):
                    raise ValueError(f"Invalid hosted graph link at {name}.{field}.")
                continue
            kind = field_schema[0]
            options = field_schema[1] if len(field_schema) > 1 and isinstance(field_schema[1], dict) else {}
            choices = kind if isinstance(kind, list) else options.get("options") if kind == "COMBO" else None
            upload = any(options.get(key) for key in ("image_upload", "video_upload", "audio_upload"))
            if choices and not upload and value not in choices:
                raise ValueError(f"Hosted schema does not offer {name}.{field}={value}.")


def capability(catalogue):
    from .workflows import normalize_request, build_workflow
    from .runner import ProviderError
    try:
        for mode in ("source", "generated", "silent"):
            request = normalize_request({"model_id": "ltx-2.5", "effect_id": "remove-object", "provider": "local",
                "prompt": "Remove the selected object; preserve the scene.", "width": 512, "height": 320,
                "frames": 49, "fps": 24, "seed": 1, "audio_mode": mode, "mask_tracking_method": "static",
                "enhance_prompt": False, "export_uncomposited": True, "job_id": "cloud-capability"})
            logical = build_workflow(request, {"source": "source.mp4", "mask": "mask.png"})
            native = native_graph(logical, request, {"source": "source.mp4", "generation_mask": "mask.mp4", "composite_mask": "alpha.mp4", "source_audio": "source.wav"}, mode == "source")
            validate_graph(native, catalogue)
    except (ValueError, KeyError, ProviderError) as exc:
        return {"available": False, "tasks": [], "detail": str(exc)[:1000]}
    return {"available": True, "tasks": ["inpaint"], "basis": "actual hosted node schemas and exact default profile weights",
            "execution": "native Cloud composite video; explicit host source/mask preparation and optional removal lighting correction",
            "render_verified": False}


def prepare(request, assets, output_dir, cancel, settings, progress):
    from PIL import Image
    import numpy as np
    from custom_nodes.openframe import media
    from . import cloud

    logical, prepared, original, alpha, tracking = cloud.prepare(request, assets, output_dir, cancel, settings, progress)
    directory = output_dir / "cloud-input"
    width, height, frames, fps = (request[k] for k in ("width", "height", "frames", "fps"))
    path = directory / (request["job_id"] + "-composite-mask.mp4")
    cloud._lossless_input(path, (np.repeat((m * 255).round().astype(np.uint8)[..., None], 3, axis=2) for m in alpha), width, height, fps, cancel)
    prepared["composite_mask"] = path

    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(assets["source"])], capture_output=True, timeout=30, check=True)
    streams = json.loads(probe.stdout)["streams"]
    source_has_audio = any(s["codec_type"] == "audio" for s in streams)
    save = logical["save"]["inputs"]
    source_audio_used = save.get("preserve_audio", True) and source_has_audio
    if any(["source_audio", 0] == value for spec in logical.values() for value in spec["inputs"].values()) or source_audio_used:
        path = directory / (request["job_id"] + "-source-audio.wav")
        enabled = logical.get("source_audio", {}).get("inputs", {}).get("enabled", False)
        args = ["ffmpeg", "-v", "error", "-y"]
        if enabled and source_has_audio:
            args += ["-ss", str(request.get("trim_start", 0)), "-i", str(assets["source"]), "-map", "0:a:0"]
        else:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        count = round(frames / fps * 48000)
        # WAV has no stream timestamp. Materialize any leading source offset
        # (and trim negative preroll) rather than moving its sound to time zero.
        args += ["-ac", "2", "-ar", "48000", "-af", f"aresample=48000:async=1:first_pts=0,apad=whole_len={count},atrim=end_sample={count}", "-c:a", "pcm_f32le", str(path)]
        cancel(); subprocess.run(args, capture_output=True, timeout=180, check=True); cancel()
        prepared["source_audio"] = path

    reference_info = None
    if logical.get("reference", {}).get("class_type") == "OpenFrameInpaintFirstFrame":
        from PIL import ImageOps
        # Apply the same source-native guard and FFmpeg fit as the local helper.
        source_info = next(s for s in streams if s["codec_type"] == "video")
        native_size = (source_info["width"], source_info["height"])
        rotation = next((item.get("rotation", 0) for item in source_info.get("side_data_list", []) if "rotation" in item), 0)
        if abs(int(rotation)) % 180 == 90:
            native_size = native_size[::-1]
        with Image.open(assets["reference"]) as image:
            if ImageOps.exif_transpose(image).size != native_size:
                raise ValueError("The edited starting frame must match the source video's native dimensions.")
            if image.convert("RGBA").getextrema()[3][0] < 255:
                raise ValueError("The edited starting frame must be fully opaque.")
        fitted = media.decode_frames(assets["reference"], width, height, fps, 1)[0]
        path = directory / (request["job_id"] + "-reference.png")
        Image.fromarray(fitted).save(path); prepared["reference"] = path
        padded = np.pad(fitted, ((0, (-height) % 64), (0, (-width) % 64), (0, 0)), mode="edge")
        path = directory / (request["job_id"] + "-reference-padded.png")
        Image.fromarray(padded).save(path); prepared["reference_padded"] = path
        with Path(assets["reference"]).open("rb") as stream:
            reference_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        reference_info = {"mode": "edited-first-frame", "source_start_seconds": request.get("trim_start", 0),
            "native_size": list(native_size), "fitted_size": [width, height],
            "image_sha256": reference_sha,
            "fitted_rgb_sha256": hashlib.sha256(fitted.tobytes()).hexdigest(),
            "padding": {"right": (-width) % 64, "bottom": (-height) % 64},
            "later_identity_guaranteed": False}
    return logical, prepared, original, alpha, tracking, source_audio_used, reference_info


def native_graph(logical, request, filenames, source_audio_used=False):
    graph = copy.deepcopy(logical)

    def node(name, cls, **inputs):
        graph[name] = {"class_type": cls, "inputs": inputs, "_meta": {"title": cls}}
        return [name, 0]

    def replace(value, mappings):
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
            return mappings.get(tuple(value), value)
        return value

    width, height = request["width"], request["height"]
    source = node("cloud_source_file", "LoadVideo", file=filenames["source"])
    source = node("cloud_source", "GetVideoComponents", video=source)
    plate = node("cloud_plate", "ImageCrop", image=source, width=width, height=height, x=0, y=0)
    mask = node("cloud_mask_file", "LoadVideo", file=filenames["generation_mask"])
    mask = node("cloud_mask_frames", "GetVideoComponents", video=mask)
    mask = node("cloud_mask", "ImageToMask", image=mask, channel="red")
    alpha = node("cloud_alpha_file", "LoadVideo", file=filenames["composite_mask"])
    alpha = node("cloud_alpha_frames", "GetVideoComponents", video=alpha)
    alpha = node("cloud_alpha", "ImageToMask", image=alpha, channel="red")
    mappings = {("source", 0): plate, ("source", 1): mask, ("source", 2): alpha,
                ("pad_refinement", 0): source, ("pad_refinement", 1): mask}
    graph.pop("source")
    graph.pop("pad_refinement", None)
    if "reference_padding" in graph:
        mappings[("reference_padding", 0)] = node("cloud_reference_padded", "LoadImage", image=filenames["reference_padded"])
        graph.pop("reference_padding")
        graph.pop("reference_padding_mask", None)
        graph["reference"] = {"class_type": "LoadImage", "inputs": {"image": filenames["reference"]}}
    if "source_audio" in filenames:
        graph["source_audio"] = {"class_type": "LoadAudio", "inputs": {"audio": filenames["source_audio"]}}
    else:
        graph.pop("source_audio", None)
    prompt = graph.pop("prompt_record")["inputs"]
    if "enhance_prompt" in graph and graph["enhance_prompt"]["inputs"].get("sampling_mode") == "on":
        # Hosted schema requires this field; native textgen's omitted value is 0.
        graph["enhance_prompt"]["inputs"].setdefault("sampling_mode.presence_penalty", 0.0)
    if isinstance(prompt["model_prompt"], str):
        prompt["model_prompt"] = node("cloud_model_prompt", "PrimitiveStringMultiline", value=prompt["model_prompt"])
    mappings[("prompt_record", 0)] = prompt["model_prompt"]
    for spec in graph.values():
        spec["inputs"] = {key: replace(value, mappings) for key, value in spec["inputs"].items()}
        if spec["class_type"] == "OpenFrameGreenFill":
            spec["class_type"] = "LTXVInpaintPreprocess"
    save = graph.pop("save")["inputs"]
    raw = graph.pop("save_uncomposited", None)
    fit = graph.pop("fit_plate", None)
    generated = fit["inputs"]["images"] if fit else save["images"]
    if save.get("preserve_outside_mask"):
        final = node("cloud_composite", "ImageCompositeMasked", destination=plate, source=generated, mask=alpha, x=0, y=0, resize_source=False)
    else:
        final = generated
    audio = ["source_audio", 0] if source_audio_used else save.get("audio")

    def video(name, images, suffix):
        inputs = {"images": images, "fps": request["fps"]}
        if audio:
            inputs["audio"] = audio
        output = node(name + "_video", "CreateVideo", **inputs)
        node(name, "SaveVideo", video=output, filename_prefix="openframe/" + request["job_id"] + suffix,
             format="mp4", **{"format.codec": "h264", "format.codec.encoding": "re-encode",
                              "format.codec.encoding.crf": 17})

    video("save", final, "_native_composite")
    if raw:
        video("save_uncomposited", raw["inputs"]["images"], "_uncomposited")
    if fit or request.get("encoding_quality") in {"standard", "high"} or (save.get("match_lighting") and save.get("preserve_outside_mask")):
        node("save_frames", "SaveImage", images=generated, filename_prefix="openframe/" + request["job_id"] + "_lighting_input")
        if audio:
            node("save_audio", "SaveAudio", audio=audio, filename_prefix="openframe/" + request["job_id"] + "_lighting_audio")
    node("save_prompt", "SaveText", text=prompt["model_prompt"], filename_prefix="openframe/" + request["job_id"] + "_model_prompt", format="txt")
    return graph


def inspect_video(path, request, expect_audio):
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)], capture_output=True, timeout=120, check=True)
    streams = json.loads(result.stdout)["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), {})
    audio = [s for s in streams if s["codec_type"] == "audio"]
    if (video.get("width"), video.get("height"), int(video.get("nb_read_frames", 0))) != (request["width"], request["height"], request["frames"]):
        raise ValueError("Hosted Cloud returned an unexpected video canvas/frame count; no partial result was published.")
    rate = video.get("avg_frame_rate", "0/1").split("/")
    if len(rate) != 2 or not float(rate[1]) or abs(float(rate[0]) / float(rate[1]) - request["fps"]) > .001:
        raise ValueError("Hosted Cloud returned an unexpected video frame rate.")
    if bool(audio) != bool(expect_audio):
        raise ValueError("Hosted Cloud audio streams do not match the selected source/generated/silent route.")
    return {"width": video["width"], "height": video["height"], "frames": int(video["nb_read_frames"]), "fps": request["fps"], "audio_streams": len(audio)}


def run(request, assets, output_dir, settings, on_progress, is_cancelled):
    from PIL import Image
    import numpy as np
    from custom_nodes.openframe import media
    from . import cloud
    from .runner import ProviderError, _raise_if_cancelled

    if request["task"] != "inpaint":
        raise ProviderError("The native LTX 2.5 Cloud adapter currently implements masked inpainting only.")
    if request.get("inpaint_composite_mode") == "plate-fit":
        try:
            from custom_nodes.openframe.plate_fit import fit_plate_frames
        except ImportError as exc:
            raise ProviderError("Plate-fit finishing needs the cloud extra, including SciPy, installed on the app host before submitting to Cloud.") from exc
    cancel = lambda: _raise_if_cancelled(is_cancelled)
    auth = cloud.auth_status(settings, refresh=True)
    if auth["mode"] == "missing":
        raise ProviderError("Sign in with `comfy cloud login` or configure a Comfy API key.")
    catalogue = cloud.node_catalog(settings)
    started = time.monotonic()
    on_progress(.02, "Preparing source interval, masks and audio locally for native Cloud rendering")
    logical, prepared, original, alpha, tracking, source_audio_used, reference_info = prepare(request, assets, output_dir, cancel, settings, on_progress)
    graph = native_graph(logical, request, {role: path.name for role, path in prepared.items()}, source_audio_used)
    validate_graph(graph, catalogue)
    from .export import to_ui_workflow
    cloud_ui = to_ui_workflow(graph, catalogue)
    execute = cloud._run_cli if auth["mode"] == "cli-oauth" else cloud._run_sdk
    args = (graph, prepared, output_dir, settings, on_progress, cancel) if auth["mode"] == "cli-oauth" else (graph, prepared, request, output_dir, settings, on_progress, cancel)
    ident, executed, outputs = execute(*args)
    save = logical["save"]["inputs"]
    lighting = bool(save.get("match_lighting") and save.get("preserve_outside_mask"))
    plate_fit = "fit_plate" in logical
    bitrate = request.get("encoding_quality") in {"standard", "high"}
    finishing = lighting or plate_fit or bitrate
    expect_audio = bool(source_audio_used or save.get("audio"))
    final, checks = [], {}
    for name, role in (("save", "preview" if finishing else "result"), ("save_uncomposited", "uncomposited")):
        if name not in graph:
            continue
        files = outputs.get(name, [])
        if len(files) != 1:
            raise ProviderError("Hosted Cloud did not return exactly one requested video for " + name)
        checks[name] = inspect_video(files[0], request, expect_audio)
        target = output_dir / (request["job_id"] + ("-cloud-native-composite.mp4" if name == "save" else "-cloud-uncomposited.mp4"))
        shutil.move(str(files[0]), target)
        final.append({"path": str(target), "kind": "video", "role": role})
    if finishing:
        frames = outputs.get("save_frames", [])
        if len(frames) != request["frames"] or any(p.suffix.lower() != ".png" for p in frames):
            raise ProviderError("Cloud returned incomplete finishing inputs; no partial result was published.")
        def generated_at(index):
            with Image.open(frames[index]) as image:
                if image.size != (request["width"], request["height"]):
                    raise ProviderError("Unexpected finishing-input canvas.")
                return np.asarray(image.convert("RGB"), np.float32) / 255
        def corrected():
            if plate_fit:
                pixels = fit_plate_frames(request["frames"], request["height"], request["width"], generated_at,
                    lambda i: original[i].astype(np.float32) / 255, lambda i: alpha[i], cancel)
            else:
                pixels = (generated_at(i) for i in range(request["frames"]))
            for index, frame in enumerate(pixels):
                cancel()
                blend = save.get("preserve_outside_mask")
                yield media.composite_frame(frame, original[index].astype(np.float32) / 255 if blend else None,
                    alpha[index] if blend else None, lighting)
        audio = outputs.get("save_audio", [])
        if len(audio) != int(expect_audio):
            raise ProviderError("Cloud returned incomplete audio for the explicit local finishing.")
        suffix = "plate-fit" if plate_fit else "lighting-corrected" if lighting else "bitrate-" + request["encoding_quality"]
        target = output_dir / (request["job_id"] + "-cloud-" + suffix + ".mp4")
        on_progress(.94, "Applying the recorded finishing locally; retaining the native Cloud composite")
        media.encode_video(target, corrected(), request["width"], request["height"], request["fps"], request["frames"],
            source_audio=audio[0] if audio else None, check_cancelled=cancel, encoding_quality=request.get("encoding_quality", "legacy"))
        checks["corrected_result"] = inspect_video(target, request, expect_audio)
        final.insert(0, {"path": str(target), "kind": "video", "role": "result"})
    if request.get("export_mask", True):
        target = output_dir / (request["job_id"] + "-mask.mp4")
        media.encode_mask_video(target, alpha, request["width"], request["height"], request["fps"])
        final.append({"path": str(target), "kind": "video", "role": "mask"})
    prompts = outputs.get("save_prompt", [])
    if len(prompts) != 1 or prompts[0].stat().st_size > 128 * 1024:
        raise ProviderError("Cloud did not return bounded model-prompt provenance.")
    model_prompt = prompts[0].read_text(encoding="utf-8")
    prepared_info = {}
    for role, path in prepared.items():
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        prepared_info[role] = {"filename": path.name, "sha256": digest, "size": path.stat().st_size,
            "relative_path": str(path.relative_to(output_dir)) if path.is_relative_to(output_dir) else None}
    metadata = {"provider": "comfy-cloud", "auth_mode": auth["mode"], "provider_job_id": ident, "provider_url": cloud.HOSTED_URL,
        "request": request, "seconds": time.monotonic() - started, "execution": "hosted-cloud-diffusion-local-media",
        "workflow_role": "local-replay-recipe", "cloud_workflow": executed, "cloud_ui_workflow": cloud_ui, "prepared_inputs": prepared_info,
        "pipeline": "ltx-2.5-inpaint-" + request.get("video_refinement", "two-stage"),
        "video_prompt": {"original": request["prompt"], "model_prompt": model_prompt, "enhanced": bool(request.get("enhance_prompt"))},
        "audio_policy": {"selected_mode": request.get("audio_mode"), "legacy_flags_preserved": request.get("audio_mode") is None,
            "mux_source": "source" if source_audio_used else "generated" if save.get("audio") else "none", "stream_checks": checks,
            "note": "Native Cloud audio routing; sound quality/alignment remain unverified without a live run."},
        "processing": {"input_encoding": "lossless-rgb-h264", "cloud_output": "native-composite-video",
            "cloud_video_role": "preview" if finishing else "result", "host_lighting_correction": lighting,
            "host_plate_fit": plate_fit,
            "native_video_encoding": "H264 CRF17; native SaveVideo does not expose the app's bitrate targets",
            "host_bitrate_target": request["encoding_quality"] if bitrate else None,
            "composite": "native ImageCompositeMasked; optional exact shared CPU finishing, followed by one alpha composite",
            "mask_feather_method": logical["source"]["inputs"]["feather_method"],
            "cloud_composite_alpha_encoding": "8-bit; max rounding error 0.5/255; zero exterior remains zero",
            "host_corrected_alpha": "original floating-point CPU mask",
            "note": "The native graph returns composited video/audio, plus requested raw video. Source/mask/reference/audio preparation is local. Recorded removal lighting correction, replacement plate fitting or explicit Standard/High bitrate encoding runs locally from lossless 8-bit PNG intermediates; native Cloud composite is retained as a preview. Local replay retains the original floating-point sampler/compositor path."}}
    if plate_fit:
        from custom_nodes.openframe.plate_fit import UPSTREAM_REVISION, UPSTREAM_SOURCE
        metadata["plate_fit"] = {"upstream_revision": UPSTREAM_REVISION, "upstream_source": UPSTREAM_SOURCE,
            "license": "Apache-2.0", "execution": "explicit local finishing after native Cloud render",
            "frames": request["frames"], "temporal_radius": 2, "log_ratio_bound": .4,
            "alignment": False, "grain": False, "mask_changed": False, "alpha_composites": 1}
    if tracking:
        metadata["tracking"] = tracking
    if reference_info:
        metadata["inpaint_first_frame"] = reference_info
    if request.get("export_uncomposited"):
        metadata["uncomposited"] = {"role": "uncomposited", "stage": "decoded RGB before Laplacian and plate compositing; exact canvas cropped"}
    (output_dir / "workflow.cloud.json").write_text(json.dumps(executed, indent=2))
    for paths in outputs.values():
        for path in paths:
            if path.is_relative_to(output_dir / "cloud-output"):
                path.unlink(missing_ok=True)
    return {"outputs": final, "workflow": logical, "ui_workflow": None, "metadata": metadata}
