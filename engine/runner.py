"""Real execution adapters. All providers execute the selected ComfyUI graph."""
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import threading
import time
import uuid

import httpx
from .workflows import build_workflow, normalize_request


class JobCancelled(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


_CLOUD_CONFIG_LOCK = threading.Lock()


def _raise_if_cancelled(is_cancelled):
    if is_cancelled():
        raise JobCancelled("Generation cancelled.")


def _url(value):
    value = str(value).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ProviderError("Provider URL must be an HTTP(S) URL without embedded credentials.")
    return value


def check_provider(provider, settings):
    try:
        if provider == "comfy-cloud":
            from .cloud import HOSTED_URL, check_hosted
            if settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/") == HOSTED_URL:
                return check_hosted(settings)
            key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
            if not key:
                return {"available": False, "detail": "Add a Comfy API key and a deployment containing the OpenFrame node pack."}
            url = _url(settings.get("comfy_cloud_url", "https://cloud.comfy.org"))
            response = httpx.get(url + "/api/v2/jobs", headers={"Authorization": f"Bearer {key}"}, params={"limit": 1}, timeout=15)
            if response.status_code not in {200, 501}:
                raise ProviderError(f"Comfy API returned HTTP {response.status_code}.")
            return {"available": True, "detail": "Comfy API responds. Your deployment must contain the model weights and OpenFrame custom nodes; node availability is validated on submission."}
        if provider != "local":
            raise ProviderError("Unknown compute provider.")
        url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
        headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
        with httpx.Client(timeout=15, headers=headers) as client:
            response = client.get(url + "/system_stats"); response.raise_for_status()
            info = client.get(url + "/object_info"); info.raise_for_status()
            classes = info.json()
            missing = [name for name in ("OpenFrameSaveVideo", "OpenFrameVideoInput", "OpenFrameGreenFill", "OpenFramePadForRefinement") if name not in classes]
            if missing:
                return {"available": False, "detail": "ComfyUI is running. Install the OpenFrame node pack and restart: " + ", ".join(missing)}
            available = []
            ckpts = classes.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            unets = classes.get("UNETLoader", {}).get("input", {}).get("required", {}).get("unet_name", [[]])[0]
            if "ltxv-2b-0.9.8-distilled.safetensors" in ckpts:
                available.append("ltx-0.9.8")
            if "ltx-2.3-22b-dev.safetensors" in ckpts:
                available.append("ltx-2.3")
            if "wan2.1_vace_1.3B_fp16.safetensors" in unets:
                available.append("wan-vace")
            if "wan2.1_vace_14B_fp16.safetensors" in unets:
                available.append("wan-vace-14b")
            if "flux-2-klein-4b-fp8.safetensors" in unets:
                available.append("flux-klein-4b")
            from .flux3_workflows import PROFILES as FLUX3_PROFILES, VAE as FLUX3_VAE
            from .flux3_character_workflows import BASE_PROFILE
            clips = classes.get("CLIPLoader", {}).get("input", {}).get("required", {}).get("clip_name", [[]])[0]
            vaes = classes.get("VAELoader", {}).get("input", {}).get("required", {}).get("vae_name", [[]])[0]
            clip_types = classes.get("CLIPLoader", {}).get("input", {}).get("required", {}).get("type", [[]])[0]
            for model_id, profile in {**FLUX3_PROFILES, "flux3-klein-base": BASE_PROFILE}.items():
                if (profile["unet"] in unets and profile["encoder"] in clips and profile["upsampler"] in clips
                        and FLUX3_VAE in vaes and "flux3" in clip_types
                        and all(name in classes for name in ("OpenFrameFlux3Prompt", "OpenFrameSaveImage", "EmptyFlux2LatentImage", "ReferenceLatent"))):
                    if model_id != "flux3-klein-base" or all(name in classes for name in ("OpenFrameCharacterCaption", "LoraLoaderModelOnly")):
                        available.append(model_id)
            qwen_loras = classes.get("LoraLoaderModelOnly", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0]
            if ("qwen_image_edit_2509_fp8_e4m3fn.safetensors" in unets
                    and "qwen_2.5_vl_7b_fp8_scaled.safetensors" in clips and "qwen_image_vae.safetensors" in vaes
                    and all(name in qwen_loras for name in ("Qwen-Image-Lightning-8steps-V1.1.safetensors", "qwen-multi-angle-lighting-251121.safetensors"))
                    and "qwen_image" in clip_types
                    and all(name in classes for name in ("TextEncodeQwenImageEditPlus", "ModelSamplingAuraFlow", "CFGNorm", "ImageScaleToTotalPixels"))):
                available.append("qwen-image-relight")
            portrait_ready = classes.get("OpenFramePortraitAlphas", {}).get("input", {}).get("required", {}).get("source_mask", [None, {}])
            checkpoints = classes.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            if ("qwen_image_edit_2509_fp8_e4m3fn.safetensors" in unets
                    and "qwen_2.5_vl_7b_fp8_scaled.safetensors" in clips and "qwen_image_vae.safetensors" in vaes
                    and all(name in qwen_loras for name in ("Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", "Qwen-Image-Edit-2509-Relight.safetensors"))
                    and "sam3.1_multiplex_fp16.safetensors" in checkpoints and "qwen_image" in clip_types
                    and len(portrait_ready) > 1 and portrait_ready[1].get("openframe_portrait_alpha_available")
                    and all(name in classes for name in ("TextEncodeQwenImageEditPlus", "FluxKontextImageScale", "SAM3_VideoTrack", "SCAIL2ColoredMask", "MaskComposite", "ImageCompositeMasked", "OpenFrameImageBrightness"))):
                available.append("qwen-portrait-relight")
            if "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors" in unets:
                available.append("wan-animate")
            audio_encoders = classes.get("AudioEncoderLoader", {}).get("input", {}).get("required", {}).get("audio_encoder_name", [[]])[0]
            if ("wan2.2_s2v_14B_bf16.safetensors" in unets and "wav2vec2_large_english_fp16.safetensors" in audio_encoders
                    and all(name in classes for name in ("AudioEncoderEncode", "WanSoundImageToVideo"))):
                available.append("wan-s2v")
            matte_models = classes.get("LoadBackgroundRemovalModel", {}).get("input", {}).get("required", {}).get("bg_removal_name", [[]])[0]
            if "birefnet.safetensors" in matte_models and all(name in classes for name in ("RemoveBackground", "JoinImageWithAlpha")):
                available.append("birefnet")
            voice_options = classes.get("OpenFrameKokoroSpeech", {}).get("input", {}).get("required", {}).get("voice", [])
            if len(voice_options) > 1 and voice_options[1].get("openframe_kokoro_available") is True and "OpenFrameSaveAudio" in classes:
                available.append("kokoro-82m")
            narration_options = classes.get("OpenFrameSequenceNarration", {}).get("input", {}).get("required", {}).get("request_json", [])
            narration_runtime = narration_options[1].get("openframe_narration_runtime", {}) if len(narration_options) > 1 else {}
            if narration_runtime.get("ming"):
                available.append("ming-narration")
            if narration_runtime.get("captions"):
                available.append("qwen-caption")
            matte_options = classes.get("OpenFrameSemanticMatte", {}).get("input", {}).get("required", {}).get("prompt", [])
            if len(matte_options) > 1 and matte_options[1].get("openframe_semantic_matte_available") is True:
                available.append("sam3.1-vitmatte")
            depth_options = classes.get("OpenFrameVideoDepth", {}).get("input", {}).get("required", {}).get("profile", [])
            if len(depth_options) > 1 and any(device.get("type") == "cuda" for device in response.json().get("devices", [])):
                available.extend(depth_options[1].get("openframe_depth_available", []))
            from .ripple_models import RIPPLE_FILE
            ripple_loras = classes.get("LoraLoaderModelOnly", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0]
            if ("ltx-2.5-22b-distilled-transformer-bf16.safetensors" in unets
                    and "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors" in clips
                    and all(name in vaes for name in ("ltx-2.5-video-vae-bf16.safetensors", "ltx-2.5-audio-vae-bf16.safetensors"))
                    and RIPPLE_FILE in ripple_loras
                    and all(name in classes for name in ("LTXAddVideoICLoRAGuide", "ImageBatch", "OpenFrameRecordVideoPrompt"))):
                available.append("ltx-ripple")
            from .video_capabilities import video_provider_capabilities
            video_capabilities = video_provider_capabilities(classes)
            available.extend(video_capabilities["model_ids"])
            from .editvid_models import editvid_available
            if editvid_available(classes):
                available.append("flux-klein-editvid")
            from .recast_models import recast_available, recast_support_capability
            if recast_available(classes):
                available.append("scail-2")
                video_capabilities["model_capabilities"]["scail-2"] = recast_support_capability(classes)
            from .smoke_models import smoke_available
            if smoke_available(classes):
                available.append("ltx-2.3-transition")
            from .relight_models import relight_available
            if relight_available(classes):
                available.append("ltx-2.3-relight")
            training_options = classes.get("OpenFrameTrainCharacter", {}).get("input", {}).get("required", {}).get("request_json", [])
            training = training_options[1] if len(training_options) > 1 else {}
            return {"available": True, "detail": "ComfyUI and OpenFrame nodes are available. Selected graph validates all required weights at submission.", "models": list(dict.fromkeys(available)),
                    "training_available": training.get("openframe_training_available") is True,
                    "training_detail": training.get("openframe_training_detail", "Install the configured Linux CUDA character-training runtime."),
                    "model_capabilities": video_capabilities["model_capabilities"], "narration_runtime": narration_runtime, "devices": response.json().get("devices", [])}
    except Exception as exc:
        return {"available": False, "detail": f"{type(exc).__name__}: {str(exc)[:500]}"}


def _cancel_local(client, prompt_id):
    client.post("/queue", json={"delete": [prompt_id]})
    queue = client.get("/queue").json()
    if any(item[1] == prompt_id for item in queue.get("queue_running", [])):
        client.post("/interrupt", json={})


def _run_local(request, assets, output_dir, settings, on_progress, is_cancelled):
    import websocket
    url = _url(settings.get("comfy_url", "http://127.0.0.1:8188"))
    client_id = uuid.uuid4().hex
    ws = None
    prompt_id = None
    headers = {"Authorization": "Bearer " + settings["comfy_api_key"]} if settings.get("comfy_api_key") else {}
    with httpx.Client(base_url=url, timeout=120, headers=headers) as client:
        if request.get("model_id") in {"ming-narration", "qwen-caption"}:
            response = client.get("/object_info/OpenFrameSequenceNarration")
            response.raise_for_status()
            options = response.json().get("OpenFrameSequenceNarration", {}).get("input", {}).get("required", {}).get("request_json", [])
            runtime = options[1].get("openframe_narration_runtime", {}) if len(options) > 1 else {}
            if (request["model_id"] == "ming-narration" and not runtime.get("ming")) or (request.get("generate_captions") and not runtime.get("captions")) or (request["model_id"] == "qwen-caption" and not runtime.get("captions")):
                raise ProviderError(runtime.get("detail", "Install the pinned Linux CUDA speech/ASR runtime on the ComfyUI host; see NARRATION-RUNTIME.md."))
        if request.get("provider") == "local" and request.get("_character_adapter"):
            from .training import training_host_id
            if request["_character_adapter"].get("host_id") != training_host_id(settings):
                raise ProviderError("The trained character belongs to a different ComfyUI endpoint. Reconnect its training host before rendering.")
        if request.get("model_id") == "sam3.1-vitmatte":
            response = client.get("/object_info/OpenFrameSemanticMatte")
            response.raise_for_status()
            options = response.json().get("OpenFrameSemanticMatte", {}).get("input", {}).get("required", {}).get("prompt", [])
            if len(options) < 2 or options[1].get("openframe_semantic_matte_available") is not True:
                raise ProviderError("Configure the Linux CUDA SAM3.1/ViTMatte runtime on the ComfyUI host before submitting this matte workflow; see RECAST-RUNTIME.md.")
        if request.get("recast_reference_cleanup"):
            response = client.get("/object_info/OpenFrameReferenceForeground")
            response.raise_for_status()
            options = response.json().get("OpenFrameReferenceForeground", {}).get("input", {}).get("required", {}).get("reference_image", [])
            if len(options) < 2 or options[1].get("openframe_reference_cleanup_available") is not True:
                raise ProviderError("Install the current OpenFrame nodes, pinned ViTMatte files and numba on the Local ComfyUI host before enabling Clean reference edges.")
        if request.get("recast_composite_tracking") in {"official", "official-union"}:
            from .recast_models import recast_support_capability
            response = client.get("/object_info/OpenFrameRecastOfficialSupport")
            response.raise_for_status()
            support = recast_support_capability(response.json())
            if request["recast_composite_tracking"] not in support["composite_tracking_methods"]:
                raise ProviderError("Update the OpenFrame nodes for the selected support method. " + support["official_support_detail"])
        if request["model_id"] == "flux-klein-editvid":
            from .editvid_models import editvid_available
            response = client.get("/object_info")
            response.raise_for_status()
            if not editvid_available(response.json()):
                raise ProviderError("Install the pinned native EditVid port, OpenFrame interval node and exact9B/encoder/VAE files on the Local host; see EDITVID-RUNTIME.md. No substitute model will be used.")
        filenames = {}
        for role, path in assets.items():
            _raise_if_cancelled(is_cancelled)
            name = f"openframe_{request['job_id']}_{role}{Path(path).suffix.lower()}"
            on_progress(.02, f"Uploading {role}")
            with Path(path).open("rb") as file:
                response = client.post("/upload/image", files={"image": (name, file)}, data={"type": "input", "overwrite": "false"})
            response.raise_for_status(); data = response.json()
            filenames[role] = "/".join(x for x in (data.get("subfolder", ""), data["name"]) if x)
        graph = build_workflow(request, filenames)
        try:
            wsurl = url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
            try:
                ws = websocket.create_connection(f"{wsurl}/ws?clientId={client_id}", timeout=2, suppress_origin=True, header=headers)
            except (OSError, websocket.WebSocketException):
                ws = None  # History polling remains authoritative.
            response = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
            if response.status_code >= 400:
                raise ProviderError("ComfyUI rejected the workflow: " + response.text[:5000])
            prompt_id = response.json()["prompt_id"]
            (output_dir / "provider-job.json").write_text(json.dumps({"provider": "local", "prompt_id": prompt_id, "url": url}))
            on_progress(.05, "Queued in ComfyUI")
            completed = set(); last_poll = 0.0; start = time.monotonic(); current = None
            while True:
                if is_cancelled():
                    _cancel_local(client, prompt_id)
                    raise JobCancelled("ComfyUI job cancelled.")
                if time.monotonic() - start > 7200:
                    _cancel_local(client, prompt_id)
                    raise ProviderError("ComfyUI execution exceeded two hours and was cancelled.")
                if ws:
                    try:
                        message = ws.recv()
                        if isinstance(message, str):
                            event = json.loads(message); data = event.get("data", {})
                            if data.get("prompt_id") in {None, prompt_id}:
                                if event.get("type") == "executing" and data.get("node"):
                                    if current:
                                        completed.add(current)
                                    current = str(data["node"])
                                    stage = graph.get(current, {}).get("class_type", "ComfyUI")
                                    on_progress(min(.88, .08 + .8 * len(completed) / len(graph)), stage)
                                elif event.get("type") == "progress" and data.get("max"):
                                    fraction = min(1, data.get("value", 0) / data["max"])
                                    tracking = current == "source"
                                    refining = current == "sample_refinement"
                                    progress_value = (.08 + .2 * fraction) if tracking else (.72 + .16 * fraction) if refining else (.3 + (.35 if "sample_refinement" in graph else .55) * fraction)
                                    label = "Tracking mask" if tracking else "Refining detail" if refining else "Sampling"
                                    on_progress(progress_value, f"{label} {data.get('value', 0)}/{data['max']}")
                                elif event.get("type") == "execution_error":
                                    raise ProviderError(f"{data.get('node_type', 'ComfyUI')}: {data.get('exception_message', 'Execution failed')}")
                    except websocket.WebSocketTimeoutException:
                        pass
                    except websocket.WebSocketConnectionClosedException:
                        ws = None
                else:
                    time.sleep(.5)
                if time.monotonic() - last_poll < 1.5:
                    continue
                last_poll = time.monotonic()
                response = client.get(f"/history/{prompt_id}"); response.raise_for_status()
                record = response.json().get(prompt_id)
                if not record:
                    continue
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    messages = status.get("messages", [])
                    details = next((m[1] for m in reversed(messages) if m[0] == "execution_error"), {})
                    raise ProviderError(f"ComfyUI failed: {details.get('exception_message', str(messages)[-2000:])}")
                if not status.get("completed"):
                    continue
                outputs = []
                # Only final save-node media; previews must never become output footage.
                groups = [(group, role) for node_id, role in (("save", "result"), ("save_preview", "preview"), ("save_mask", "mask"), ("save_uncomposited", "uncomposited"))
                          for group in record.get("outputs", {}).get(node_id, {}).values()]
                for group, default_role in groups:
                    if not isinstance(group, list):
                        continue
                    for item in group:
                        if not isinstance(item, dict) or not item.get("filename") or Path(item["filename"]).suffix.lower() not in {".mp4", ".webm", ".mov", ".mkv", ".png", ".jpg", ".jpeg", ".webp", ".wav", ".flac", ".mp3", ".ogg", ".zip"}:
                            continue
                        on_progress(.94, "Downloading finished media")
                        filename = Path(item["filename"]).name
                        is_archive = Path(filename).suffix.lower() == ".zip"
                        if is_archive and (request.get("task") != "sdr-to-hdr" or request.get("hdr_output_format") != "exr16"):
                            raise ProviderError("An archive was returned without an explicit HDR EXR export request.")
                        destination = output_dir / filename
                        with client.stream("GET", "/view", params={"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}) as stream:
                            stream.raise_for_status()
                            received = 0
                            with destination.open("wb") as file:
                                for chunk in stream.iter_bytes():
                                    _raise_if_cancelled(is_cancelled)
                                    received += len(chunk)
                                    if is_archive and received > 5 * 1024**3:
                                        raise ProviderError("HDR archive transfer exceeded the bounded export size.")
                                    file.write(chunk)
                        outputs.append({"path": str(destination), "kind": "archive" if destination.suffix.lower() == ".zip" else "image" if destination.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else "audio" if destination.suffix.lower() in {".wav", ".flac", ".mp3", ".ogg"} else "video", "role": item.get("role", default_role) if default_role == "result" else default_role})
                if not outputs:
                    raise ProviderError("ComfyUI completed but the final save node returned no image, audio or video. Inspect the execution history.")
                legacy_inpaint = request["model_id"] == "ltx-2.3" and request["task"] == "inpaint"
                pipeline = ("ltx-inpaint-two-stage" if "sample_refinement" in graph else "ltx-inpaint-single-stage") if legacy_inpaint else request["model_id"] + ":" + request["task"] + (":two-stage" if "sample_refinement" in graph else "")
                metadata = {"prompt_id": prompt_id, "provider": "local", "request": request, "seconds": time.monotonic() - start, "pipeline": pipeline}
                if request["model_id"] == "flux-klein-editvid":
                    from .editvid_models import EDITVID_MODEL, EDITVID_COMMIT
                    metadata["editvid"] = {
                        "native_port_revision": EDITVID_COMMIT, "license": EDITVID_MODEL["license"],
                        "source_description": request["restyle_source_prompt"], "edit_description": request["prompt"],
                        "source_interval": record.get("outputs", {}).get("source", {}).get("openframe_editvid", []),
                        "sampler": {key: value for key, value in graph["sample"]["inputs"].items() if not isinstance(value, list)},
                        "audio_mode": "source" if graph["save"]["inputs"]["preserve_audio"] else "silent",
                        "limits": "Short-clip source motion guidance, not exact pixels/identity; inspect fast motion and occlusion.",
                    }
                if request["model_id"] in {"ltx-2.3", "ltx-2.5"} and request["task"] in {"inpaint", "restyle"}:
                    save_audio = graph["save"]["inputs"]
                    metadata["audio_policy"] = {
                        "selected_mode": request.get("audio_mode"),
                        "legacy_flags_preserved": request.get("audio_mode") is None,
                        "source_audio_requested": bool(save_audio.get("preserve_audio") and save_audio.get("source_filename")),
                        "generated_audio_connected": "audio" in save_audio,
                        "generated_audio_node": save_audio.get("audio"),
                        "source_has_priority": bool(save_audio.get("preserve_audio", True)),
                        "missing_source_audio": ("generated fallback" if "audio" in save_audio else "silent") if save_audio.get("preserve_audio", True) else "source not requested",
                        "note": "Graph routing provenance; the registered output asset records whether an audio stream actually exists. Generated sound quality requires listening review.",
                    }
                if request["model_id"] == "ltx-2.5" and "save_uncomposited" in graph:
                    metadata["uncomposited_output"] = {
                        "role": "uncomposited", "source_node": graph["save_uncomposited"]["inputs"]["images"],
                        "stage": "decoded RGB before Laplacian blending and original-plate compositing; padding cropped to requested canvas",
                        "audio_policy": metadata.get("audio_policy"),
                    }
                if request["model_id"] == "qwen-portrait-relight":
                    from .portrait_relight_models import PORTRAIT_RELIGHT_MODEL
                    alpha = record.get("outputs", {}).get("portrait_alpha", {}).get("openframe_portrait_alpha", [])
                    if not alpha:
                        raise ValueError("Portrait background finishing completed without alpha provenance")
                    metadata["image_relight"] = {
                        "workflow_source": PORTRAIT_RELIGHT_MODEL["workflow_source"],
                        "source_asset_id": request.get("source_asset_id"), "prompt": request.get("prompt"),
                        "model_prompt": "重新照明," + request.get("prompt", ""),
                        "sampler": "euler", "scheduler": "simple", "steps": 4, "guidance": 1, "denoise": 1,
                        "background_finish": alpha[0], "raw_output_role": "uncomposited",
                        "original_background": "Restored on native source canvas before optional post-render brightness",
                        "exact_pixel_preservation": False,
                    }
                if request["model_id"] == "qwen-image-relight":
                    from .image_relight_models import IMAGE_RELIGHT_MODEL
                    metadata["image_relight"] = {
                        "workflow_source": IMAGE_RELIGHT_MODEL["workflow_source"],
                        "source_asset_id": request.get("source_asset_id"),
                        "lighting_map_asset_id": request.get("reference_asset_id"),
                        "prompt": request.get("prompt"), "sampler": "euler", "scheduler": "simple",
                        "steps": 8, "guidance": 1, "denoise": 1, "shift": 3, "cfg_norm": 1,
                        "lighting_adapter_strength": 1, "lightning_adapter_strength": 1,
                        "source_megapixels": 1, "vae_crop_grid": 8,
                        "control_parameters": "Saved app document snapshot; the exported lighting-map PNG is conditioning authority",
                        "exact_pixel_preservation": False,
                    }
                if request["model_id"] == "ltx-2.3-transition":
                    from .smoke_models import WORKFLOW_SOURCE
                    metadata["transition_recipe"] = {"workflow_source": WORKFLOW_SOURCE,
                        "adapter_strength": 1.0, "guide_strength": .7, "endpoint_compression": 25,
                        "sampler": "SamplerEulerAncestral", "eta": 0.0, "s_noise": 1.0,
                        "steps": 8, "cfg": 1, "trigger": "zhuanchang", "refinement": False,
                        "midpoint_guide": False, "overlay_or_crossfade": False,
                        "framing": "native centered nearest-exact resize before LTXVPreprocess",
                        "adaptations": ["Actual uploaded image/video endpoints", "Explicit output canvas and 121/241 frames at 24 fps", "Recorded trigger and optional clip concatenation"]}
                if "recast_condition_0" in graph:
                    from .recast_models import RECAST_TEMPLATE
                    masks = record.get("outputs", {}).get("recast_masks", {}).get("openframe_recast_masks", [])
                    if not masks:
                        raise ProviderError("Recast returned no performer-mask provenance.")
                    support = record.get("outputs", {}).get("composite_support", {}).get("openframe_recast_support", [])
                    if "composite_support" in graph and not support:
                        raise ProviderError("Recast returned no official composite-support provenance.")
                    cleanup = record.get("outputs", {}).get("clean_reference", {}).get("openframe_reference_cleanup", [])
                    if "clean_reference" in graph and not cleanup:
                        raise ProviderError("Recast returned no reference-cleanup provenance.")
                    metadata["recast"] = {**masks[0], "template": RECAST_TEMPLATE,
                        "composite_tracking": ("official-union" if "generated_images" in graph.get("composite_support", {}).get("inputs", {}) else "official") if support else "native",
                        "composite_support": support[0] if support else masks[0],
                        "mask_output_semantics": "actual final feathered composite support",
                        "source_selection": "painted first-frame override" if "initial_mask" in graph else "automatic human concept",
                        "reference_selection": "automatic human concept", "max_people": 1,
                        "reference_cleanup": cleanup[0] if cleanup else None,
                        "driving_condition": "full RGB video plus identity-colored segmentation",
                        "raw_output_role": "uncomposited", "raw_note": "Encoded raw decoded RGB before overlap color matching and original-plate compositing; silent diagnostic.",
                        "chunks": [{"length": value["inputs"]["length"], "offset": value["inputs"]["video_frame_offset"]}
                                   for key, value in graph.items() if key.startswith("recast_condition_")],
                        "steps": request["steps"], "guidance": request["guidance"], "sampler": "euler", "scheduler": "simple", "shift": 5,
                        "dpo_strength": 1, "turbo": False, "held_object_preservation_guaranteed": False}
                if request["model_id"] == "ltx-ripple":
                    from .ripple_models import PAINTAPLATE_REVISION, RIPPLE_REVISION, WORKFLOW_URL
                    metadata["ripple"] = {"workflow_source": WORKFLOW_URL, "workflow_revision": PAINTAPLATE_REVISION,
                        "adapter_revision": RIPPLE_REVISION, "adapter_strength": 1.35,
                        "reference_asset_id": request["reference_asset_id"], "reference_frame_index": 0,
                        "source_start_seconds": request.get("trim_start", 0), "guide_frames": request["frames"],
                        "precision": "BF16 base/encoder instead of upstream INT8 ConvRot",
                        "composite": "original tracked mask; no lighting rematch or Laplacian blend",
                        "raw_output_requested": bool(request.get("export_uncomposited"))}
                if "fit_plate" in graph:
                    fits = record.get("outputs", {}).get("fit_plate", {}).get("openframe_plate_fit", [])
                    if not fits:
                        raise ProviderError("The requested plate-fit node did not return its finishing provenance.")
                    metadata["plate_fit"] = fits[0]
                if request["model_id"] == "ltx-2.3-relight":
                    from .relight_models import WORKFLOW_URL, ENCODER
                    spheres = record.get("outputs", {}).get("relight_sphere", {}).get("openframe_relight_sphere", [])
                    if not spheres:
                        raise ProviderError("The Relight sphere loader did not return its input provenance.")
                    metadata["relight"] = {"workflow": WORKFLOW_URL, "canvas": [1280, 704],
                        "sphere_input": spheres[0],
                        "sphere_box": [1115, 22, 143, 143], "sphere_asset_id": request.get("reference_asset_id"),
                        "rotation": request.get("relight_rotation"), "elevation": request.get("relight_elevation"),
                        "intensity": request.get("relight_intensity"), "sphere_conditioning": "explicit uploaded PNG, not scalar-only rendering",
                        "encoder": ENCODER, "encoder_adaptation": "cached FP8 Gemma instead of template comfy_gemma_3_12B_it",
                        "distilled_lora_strength": .5, "relight_strength": 1, "guide_strength": 1,
                        "stages": 1, "sampler": "euler_ancestral_cfg_pp", "preprocess": False,
                        "source_audio_only": True, "identity_preservation_guaranteed": False}
                if request.get("restyle_method") == "water":
                    metadata["water_simulation"] = {
                        "template_commit": "220e1d45aa0469f518e982102fca4dca92a61862",
                        "template": "example_workflows/2.5/LTX-2.5_V2V_ICLoRA_Single_Stage_Distilled.json",
                        "model_card": "https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation/blob/7a458d0c206d6f80ee7bae2f46e21e959f6fc42e/README.md",
                        "adapter_revision": "7a458d0c206d6f80ee7bae2f46e21e959f6fc42e",
                        "adapter_strength": 1.0, "source_guide_strength": 1.0,
                        "source_guide": "complete dry RGB video at output resolution, not edge/depth annotations",
                        "source_start_seconds": request.get("trim_start", 0),
                        "inference_size": [request["width"], request["height"]],
                        "frames": request["frames"], "fps": 24, "stages": 1,
                        "identity_preservation_guaranteed": False}
                    metadata["pipeline"] = "ltx-2.5:restyle:water:single-stage"
                if "restyle_control" in graph:
                    controls = record.get("outputs", {}).get("restyle_control", {}).get("openframe_restyle_control", [])
                    if not controls:
                        raise ProviderError("Canny-guided restyling returned no source/control provenance.")
                    metadata["restyle_control"] = {**controls[0], "guide_strength": 1.0,
                        "template_commit": "220e1d45aa0469f518e982102fca4dca92a61862",
                        "template": "example_workflows/2.5/LTX-2.5_ICLoRA_Union_Control_Distilled.json",
                        "output_size": [request["width"], request["height"]],
                        "inference_size": [graph["empty"]["inputs"]["width"] * 2, graph["empty"]["inputs"]["height"] * 2]}
                    metadata["pipeline"] = "ltx-2.5:restyle:canny:two-stage"
                    if "first_frame_condition" in graph:
                        references = record.get("outputs", {}).get("reference", {}).get("openframe_restyle_reference", [])
                        if not references:
                            raise ProviderError("Weather first-frame conditioning returned no image provenance.")
                        metadata["restyle_first_frame"] = {**references[0],
                            "reference_asset_id": request.get("reference_asset_id"),
                            "source_start_seconds": request.get("trim_start", 0),
                            "coarse_size": [graph["empty"]["inputs"]["width"], graph["empty"]["inputs"]["height"]],
                            "refinement_size": metadata["restyle_control"]["inference_size"],
                            "strength": 1.0, "upstream_nodes": [3159, 4970]}
                        metadata["pipeline"] = "ltx-2.5:restyle:canny:first-frame:two-stage"
                if "inpaint_first_frame" in graph:
                    references = record.get("outputs", {}).get("reference", {}).get("openframe_inpaint_reference", [])
                    if not references:
                        raise ProviderError("Edited-first-frame inpainting returned no image provenance.")
                    metadata["inpaint_first_frame"] = {**references[0],
                        "reference_asset_id": request.get("reference_asset_id"),
                        "template_commit": "220e1d45aa0469f518e982102fca4dca92a61862",
                        "template": "example_workflows/2.5/LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json",
                        "coarse_size": [graph["empty"]["inputs"]["width"], graph["empty"]["inputs"]["height"]],
                        "refinement_size": [graph["empty"]["inputs"]["width"] * 2, graph["empty"]["inputs"]["height"] * 2],
                        "coarse_strength": .7, "refinement_strength": 1.0,
                        "image_compression": 18, "upstream_nodes": [5388, 3159, 5213]}
                    metadata["pipeline"] = "ltx-2.5:inpaint:edited-first-frame:two-stage"
                if "prompt_record" in graph:
                    prompt_records = record.get("outputs", {}).get("prompt_record", {}).get("openframe_prompt", [])
                    if not prompt_records:
                        raise ProviderError("Video generation finished without its required model-prompt provenance.")
                    metadata["video_prompt"] = prompt_records[0]
                if request["model_id"] in {"ming-narration", "qwen-caption"}:
                    narration = record.get("outputs", {}).get("save", {}).get("openframe_narration", [])
                    if not narration:
                        raise ProviderError("The sequence audio job returned no synthesis/transcription provenance.")
                    metadata["narration"] = narration[0]
                if request["task"] == "transition-video":
                    endpoint_records = record.get("outputs", {}).get("transition_inputs", {}).get("openframe_transition_inputs", [])
                    assembly_records = record.get("outputs", {}).get("save", {}).get("openframe_transition", [])
                    if not endpoint_records or not assembly_records:
                        raise ProviderError("The transition completed without endpoint/assembly provenance.")
                    metadata.update(transition_inputs=endpoint_records[0], transition=assembly_records[0])
                    if "reference" in graph and graph["reference"]["class_type"] == "OpenFrameTransitionGuide":
                        guide_records = record.get("outputs", {}).get("reference", {}).get("openframe_transition_guide", [])
                        if not guide_records:
                            raise ProviderError("The transition completed without midpoint-guide provenance.")
                        metadata["transition_midpoint_guide"] = guide_records[0]
                if request["task"] == "image-layers":
                    layer_records = record.get("outputs", {}).get("save", {}).get("openframe_layers", [])
                    if not layer_records:
                        raise ProviderError("Layer decomposition finished without its required stack-order metadata.")
                    metadata["layers"] = layer_records[0]
                if request["task"] == "video-depth":
                    depth_records = record.get("outputs", {}).get("save", {}).get("openframe_depth", [])
                    if not depth_records:
                        raise ProviderError("Depth output is missing its required numeric scale/validity metadata.")
                    metadata["depth"] = depth_records[0]
                if request["task"] == "sdr-to-hdr":
                    hdr_records = record.get("outputs", {}).get("save", {}).get("openframe_hdr", [])
                    if not hdr_records:
                        raise ProviderError("HDR conversion finished without its required colour/export provenance.")
                    metadata["hdr"] = hdr_records[0]
                if request["task"] == "semantic-matte":
                    matte_records = record.get("outputs", {}).get("source", {}).get("openframe_matte", [])
                    if not matte_records:
                        raise ProviderError("Subject matting returned no selection/alpha provenance.")
                    metadata["matte"] = matte_records[0]
                if request.get("image_brightness"):
                    brightness_records = record.get("outputs", {}).get("image_brightness", {}).get("openframe_image_brightness", [])
                    if not brightness_records:
                        raise ProviderError("Post-render brightness returned no adjustment provenance.")
                    metadata["image_brightness"] = brightness_records[0]
                if request["model_id"] in {"flux3-klein", "flux3-klein-int8", "flux3-klein-base"}:
                    from .flux3_workflows import PROFILES
                    from .flux3_character_workflows import BASE_PROFILE
                    from .image_models import FLUX3_REVISION, FLUX3_TEMPLATE_REVISION
                    prompt_records = record.get("outputs", {}).get("prompt_caption", {}).get("openframe_prompt", [])
                    image_records = record.get("outputs", {}).get("save", {}).get("openframe_image", [])
                    if not prompt_records:
                        raise ProviderError("FLUX3 finished without its required caption provenance; the render cannot be marked reproducible.")
                    metadata.update(image_prompt=prompt_records[0], image_processing=image_records[0] if image_records else {},
                                    image_pipeline={"profile": BASE_PROFILE if request["model_id"] == "flux3-klein-base" else PROFILES[request["model_id"]], "model_revision": FLUX3_REVISION,
                                                    "template_revision": FLUX3_TEMPLATE_REVISION, "reference_megapixels": request.get("image_reference_megapixels", 1),
                                                    "sampler": "euler", "scheduler": "simple", "variant": "base" if request["model_id"] == "flux3-klein-base" else "distilled"})
                    if request.get("_character_adapter"):
                        metadata["character_adapter"] = {**request["_character_adapter"], "strength": request.get("character_strength", 1)}
                    if request.get("image_edit_focus") == "masked-region":
                        region_records = record.get("outputs", {}).get("region_info", {}).get("openframe_image_region", [])
                        if not region_records:
                            raise ProviderError("Region editing is missing its crop/stitch geometry provenance.")
                        metadata["image_region"] = region_records[0]
                    if request["task"] == "image-outpaint":
                        canvas_records = record.get("outputs", {}).get("expand_canvas", {}).get("openframe_canvas", [])
                        if not canvas_records:
                            raise ProviderError("Image expansion is missing its original-pixel placement provenance.")
                        metadata["image_canvas"] = canvas_records[0]
                if request["model_id"] == "wan-vace-14b" and request.get("vace_reference_mode") == "first-frame":
                    from .vace14_models import FIRST_FRAME_SOURCE
                    metadata["vace_conditioning"] = {
                        "reference_mode": "first-frame", "known_control_frame_indices": [0],
                        "appearance_reference_latent": False, "source_context_frames": [1, request["frames"] - 1],
                        "final_support": "Original tracked edit mask, including frame0; independent of zero-first conditioning mask.",
                        "known_frame_pixel_restoration": False,
                        "mask_temporal_resampling": "Official nearest-exact to latent length; the edited first frame enters inactive-frame VAE conditioning, not a hard pixel freeze.",
                        "upstream": FIRST_FRAME_SOURCE,
                    }
                ui_workflow = None
                try:
                    from .export import to_ui_workflow
                    schema_response = client.get("/object_info"); schema_response.raise_for_status()
                    ui_workflow = to_ui_workflow(graph, schema_response.json())
                    (output_dir / "workflow.ui.json").write_text(json.dumps(ui_workflow, indent=2))
                except Exception as exc:
                    metadata["ui_export_error"] = str(exc)[:500]
                return {"outputs": outputs, "workflow": graph, "ui_workflow": ui_workflow, "metadata": metadata}
        except BaseException:
            if prompt_id:
                try:
                    _cancel_local(client, prompt_id)
                except Exception:
                    pass
            raise
        finally:
            if ws:
                ws.close()



def _run_cloud(request, assets, output_dir, settings, on_progress, is_cancelled):
    from .cloud import HOSTED_URL, run_hosted
    if settings.get("comfy_cloud_url", HOSTED_URL).rstrip("/") == HOSTED_URL:
        return run_hosted(request, assets, output_dir, settings, on_progress, is_cancelled)
    try:
        from comfy_sdk import Comfy
    except ImportError as exc:
        raise ProviderError("Install the cloud extra: pip install '.[cloud]'.") from exc
    key = settings.get("comfy_cloud_api_key") or os.environ.get("COMFY_API_KEY")
    if not key:
        raise ProviderError("A Comfy API key is required for this provider.")
    graph = build_workflow(request, {role: Path(path).name for role, path in assets.items()})
    # Current official SDK resolves the endpoint at construction from COMFY_BASE_URL.
    with _CLOUD_CONFIG_LOCK:
        old_url = os.environ.get("COMFY_BASE_URL")
        os.environ["COMFY_BASE_URL"] = _url(settings.get("comfy_cloud_url", "https://cloud.comfy.org"))
        try:
            client = Comfy(api_key=key)
        finally:
            if old_url is None:
                os.environ.pop("COMFY_BASE_URL", None)
            else:
                os.environ["COMFY_BASE_URL"] = old_url
    wf = client.workflows.from_json(graph)
    for role, path in assets.items():
        asset = client.assets.from_file(str(path))
        if role == "source":
            if "source" in graph:
                wf.set_input("source", "filename", asset)
                wf.set_input("save", "source_filename", asset)
            else:
                wf.set_input("image", "image", asset)
        elif role == "mask" and "source" in graph:
            wf.set_input("source", "mask_filename", asset)
        elif role == "reference" and "reference" in graph:
            wf.set_input("reference", "image", asset)
    _raise_if_cancelled(is_cancelled)
    on_progress(.04, "Uploading assets and submitting to Comfy API")
    # Do not retry an ambiguous submission: duplicate execution can incur a second charge.
    job = client.submit(wf, idempotency_key=request["job_id"])
    (output_dir / "provider-job.json").write_text(json.dumps({"provider": "comfy-cloud", "job_id": job.id}))
    try:
        start = time.monotonic()
        while True:
            if is_cancelled():
                job.cancel()
                # Confirm the terminal state rather than treating an HTTP cancellation request as completion.
                job.wait(timeout=60)
                if job.status not in {"cancelled", "canceled", "failed", "succeeded"}:
                    raise ProviderError("Comfy cancellation is still pending. Check job " + job.id)
                raise JobCancelled("Comfy API cancellation completed.")
            job.refresh()
            if job.status in {"succeeded", "failed", "cancelled", "canceled"}:
                break
            on_progress(.1, "Comfy API: " + job.status)
            if time.monotonic() - start > 7200:
                job.cancel()
                raise ProviderError("Cloud render exceeded two hours; cancellation requested for " + job.id)
            time.sleep(2)
        job.result()
        outputs = []
        for item in job.get_outputs("save"):
            filename = Path(item.name).name
            if Path(filename).suffix.lower() not in {".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg", ".webp", ".wav", ".flac", ".mp3", ".ogg"}:
                continue
            destination = output_dir / filename
            item.to_file(str(destination)); outputs.append({"path": str(destination), "kind": "video"})
        if not outputs:
            raise ProviderError("Comfy API returned no final video. Verify the OpenFrame node pack in your Build.")
        return {"outputs": outputs, "workflow": graph, "metadata": {"provider": "comfy-cloud", "job_id": job.id, "request": request}}
    except BaseException:
        if job.status not in {"succeeded", "failed", "cancelled", "canceled"}:
            try:
                job.cancel()
            except Exception:
                pass
        raise


def run_job(request, assets, output_dir, settings, on_progress, is_cancelled):
    output_dir = Path(output_dir).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    r = normalize_request(request)
    required_assets = {
        "inpaint": {"source", "mask"}, "image-to-video": {"source"}, "restyle": {"source"},
        "image-edit": {"source"}, "background-removal": {"source"}, "audio-to-video": {"source", "audio"},
        "motion-transfer": {"source", "reference"}, "character-replacement": {"source", "reference", "mask"},
    }.get(r["task"], set())
    from .catalog import model_by_id
    model = model_by_id(r["model_id"])
    if model.get("mask_optional"):
        required_assets.discard("mask")
    if r.get("vace_reference_mode") == "first-frame":
        required_assets.add("reference")
    if missing_assets := required_assets - assets.keys():
        raise ProviderError("Missing required input assets: " + ", ".join(sorted(missing_assets)))
    if r.get("vace_reference_mode") == "first-frame":
        import subprocess
        from PIL import Image, ImageOps
        dimensions = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(assets["source"])], text=True, timeout=30).strip()
        native_size = tuple(int(value) for value in dimensions.split("x"))
        with Image.open(assets["reference"]) as image:
            if ImageOps.exif_transpose(image).size != native_size:
                raise ProviderError("The edited first frame must match the source video's native dimensions.")
    if model.get("mask_input_kinds") == ["image"] and assets.get("mask") and Path(assets["mask"]).suffix.lower() in {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}:
        raise ProviderError("This model accepts a painted first-frame mask, not a mask video.")
    r["job_id"] = str(request.get("job_id") or uuid.uuid4().hex)
    if not r["job_id"].replace("-", "").isalnum():
        raise ProviderError("Invalid job identifier.")
    _raise_if_cancelled(is_cancelled)
    provider = r.get("provider", settings.get("default_provider", "local"))
    from .provider_policy import require_provider_enabled
    try:
        require_provider_enabled(provider)
    except ValueError as exc:
        raise ProviderError(str(exc)) from exc
    if model.get("supported_providers") and provider not in model["supported_providers"]:
        raise ProviderError("The selected model is unavailable on this provider; no substitute render was submitted.")
    if provider == "comfy-cloud" and r["task"] in {"text-to-image", "image-edit", "audio-to-video", "motion-transfer", "character-replacement", "background-removal", "text-to-speech"}:
        raise ProviderError("This operation requires Local ComfyUI; the Cloud adapter does not implement it. No substitute render was submitted.")
    runner = {"local": _run_local, "comfy-cloud": _run_cloud}.get(provider)
    if not runner:
        raise ProviderError("Unknown compute provider.")
    result = runner(r, assets, output_dir, settings, on_progress, is_cancelled)
    _raise_if_cancelled(is_cancelled)
    on_progress(1.0, "Complete")
    return result
