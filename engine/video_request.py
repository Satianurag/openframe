"""Validation for task-specific video controls; no runtime or model imports."""


def normalize_video_request(r, model, effect, error):
    if r["model_id"] == "ltx-2.3-relight":
        from .relight_workflows import normalize_relight
        normalize_relight(r, error)
    provider_tasks = model.get("provider_tasks", {}).get(r.get("provider", "local"))
    if provider_tasks is not None and r["task"] not in provider_tasks:
        raise error("This provider does not implement the selected model operation; no substitute workflow will be used.")
    inpaint_reference_mode = r.get("inpaint_reference_mode")
    if inpaint_reference_mode is not None:
        if (inpaint_reference_mode not in model.get("inpaint_reference_modes", []) or r["task"] != "inpaint"
                or not r.get("reference_asset_id") or r.get("reference_asset_ids")):
            raise error("Edited-first-frame inpainting requires LTX 2.5, one full edited starting image and its source video/mask.")
        if r.get("video_refinement", "two-stage") != "two-stage":
            raise error("Edited-first-frame inpainting uses the official two-stage recipe.")
    if model.get("inpaint_reference_modes") and r["task"] == "inpaint" and (r.get("reference_asset_id") or r.get("reference_asset_ids")) and inpaint_reference_mode is None:
        raise error("Select edited-first-frame mode explicitly; an isolated object reference is not supported by this inpainting recipe.")
    # Optional so old saved requests retain their exact source/fallback behavior.
    audio_mode = r.get("audio_mode")
    if audio_mode is not None:
        if audio_mode not in model.get("audio_modes_by_task", {}).get(r["task"], []):
            raise error("This model and operation do not support the selected explicit audio mode.")
        if r.get("provider", "local") not in model.get("supported_providers", ["local", "comfy-cloud"]):
            raise error("The selected model/audio route is unavailable on this provider; no model will be substituted.")
        r["preserve_audio"] = audio_mode == "source"
        r["generate_audio"] = audio_mode == "generated"
    if r["model_id"] == "ltx-2.3-transition":
        from .transitions import validate_transition_request
        try:
            validate_transition_request(r)
        except ValueError as exc:
            raise error(str(exc)) from exc
        if r["steps"] != 8 or r["guidance"] != 1 or r["strength"] != .7:
            raise error("The released transition recipe uses eight steps, CFG 1 and endpoint-guide strength 0.7.")
        if r.get("enhance_prompt"):
            raise error("The transition adapter uses the supplied direction and its recorded trigger without prompt enhancement.")
        if r.get("reframe_fit", "crop") != "crop" or any(float(r.get(k, .5)) != .5 for k in ("anchor_x", "anchor_y")):
            raise error("This matched transition template uses centered cropping for both endpoints. Choose LTX 2.5 for custom crop/pad anchors.")
        r["video_refinement"] = "single"
        r["enhance_prompt"] = False
    if r.get("export_uncomposited") and (r["task"] != "inpaint" or not model.get("supports_uncomposited")):
        raise error("The selected model/task does not expose an uncomposited diagnostic output.")
    r["inpaint_composite_mode"] = r.get("inpaint_composite_mode") or "legacy"
    if r["inpaint_composite_mode"] not in {"legacy", "plate-fit"}:
        raise error("Choose a supported inpainting finishing method.")
    if r["inpaint_composite_mode"] == "plate-fit" and (r["model_id"] != "ltx-2.5"
            or r["effect_id"] != "replace-object" or not r.get("preserve_outside_mask", True)):
        raise error("Plate fitting is available for LTX 2.5 object replacement with original-background preservation.")
    if r["model_id"] == "ltx-ripple":
        if not r.get("reference_asset_id"):
            raise error("Ripple requires an edited full starting frame.")
        if r["steps"] != 8 or r["guidance"] != 1:
            raise error("The pinned Ripple profile uses eight steps and guidance 1.")
        if r.get("enhance_prompt"):
            raise error("Ripple uses the supplied first-frame description without prompt enhancement.")
        r["video_refinement"] = "single"
        r["enhance_prompt"] = False
    r["restyle_method"] = r.get("restyle_method") or "latent"
    if r["restyle_method"] not in {"latent", "canny", "water"}:
        raise error("Choose a supported video editing method.")
    if r["restyle_method"] == "water":
        if r["model_id"] != "ltx-2.5" or r["effect_id"] != "weather":
            raise error("Water simulation is available only for the LTX 2.5 Weather operation.")
        if r["steps"] != 8 or r["guidance"] != 1 or r["strength"] != 1 or r["fps"] != 24:
            raise error("The official Water recipe uses eight steps, CFG 1, strength 1 and 24 fps.")
        if r.get("video_refinement", "single") != "single" or r.get("enhance_prompt") or r["negative_prompt"].strip():
            raise error("Water simulation uses one native-resolution stage, the exact supplied caption and no negative prompt.")
        if r.get("mask_asset_id") or r.get("reference_asset_id") or r.get("reference_asset_ids"):
            raise error("Water simulation conditions on the complete source video, without a mask or extra image reference.")
        if r.get("audio_mode") == "generated" or r.get("generate_audio"):
            raise error("The matched Water recipe supports source audio or silence, not generated audio.")
        if r["frames"] > 185 or max(r["width"], r["height"]) > 1920 or min(r["width"], r["height"]) > 1088:
            raise error("Water simulation supports at most 185 frames and a 1920×1088 canvas in either orientation.")
        if "ADD WATER" not in r["prompt"] or not all(label in r["prompt"].lower() for label in ("reference shows", "edited shows")):
            raise error("Use the trained caption format: Reference shows … Edited shows … ADD WATER …")
        r["video_refinement"] = "single"
        r["enhance_prompt"] = False
    if r["restyle_method"] == "canny":
        if r["model_id"] != "ltx-2.5" or r["task"] != "restyle":
            raise error("Canny-guided restyling requires LTX 2.5 and the restyle operation.")
        if r["steps"] != 8 or r["guidance"] != 1 or r["strength"] != 1:
            raise error("The official Union-Control recipe uses eight first-stage steps, guidance 1 and source-guide strength 1, followed by three refinement steps.")
        r["video_refinement"] = "two-stage"
    if r["model_id"] == "ldf-vfi":
        import math
        r["input_frames"] = int(r.get("input_frames") or 17)
        r["input_fps"] = float(r.get("input_fps") or 0)
        if not 2 <= r["input_frames"] <= 241 or not 1 <= r["input_fps"] < r["fps"] <= min(120, r["input_fps"] * 16):
            raise error("FPS boost requires 2–241 input frames, the actual source FPS, and an output rate above source and at most 16×/120 fps.")
        r["frames"] = math.floor((r["input_frames"] - 1) / r["input_fps"] * r["fps"] + 1e-9) + 1
        if r["frames"] > 2401:
            raise error("FPS boost is limited to 2,401 output frames per job.")
    limits = {**model.get("default_task_limits", {}), **model.get("task_limits", {}).get(r["task"], {})}
    if r["frames"] > limits.get("max_frames", model["max_frames"]):
        raise error("The selected operation exceeds its supported frame count.")
    if max(r["width"], r["height"]) > limits.get("max_long_side", max(model["max_width"], model["max_height"])) or r["width"] * r["height"] > limits.get("max_pixels", model["max_width"] * model["max_height"]):
        raise error("The selected operation exceeds its supported spatial canvas.")
    if min(r["width"], r["height"]) > limits.get("max_short_side", min(model["max_width"], model["max_height"])):
        raise error("The selected operation exceeds its supported short-side dimension.")
    if r["model_id"] == "sam3.1-vitmatte":
        r["trimap_radius"] = int(12 if r.get("trimap_radius") is None else r["trimap_radius"])
        r["subject_confidence"] = float(.5 if r.get("subject_confidence") is None else r["subject_confidence"])
        if not 1 <= r["trimap_radius"] <= 64 or not .1 <= r["subject_confidence"] <= .9 or not 1 <= len(r["prompt"]) <= 200:
            raise error("Describe the foreground in 1–200 characters, with a 1–64 pixel trimap and confidence from 0.1 to 0.9.")
    if model.get("supports_motion_controls"):
        for name, default, low, high in [("pose_strength", 1, 0, 2), ("reference_strength", 1, 0, 2), ("pose_start_percent", 0, 0, 1), ("pose_end_percent", 1, 0, 1)]:
            r[name] = float(r.get(name, default))
            if not low <= r[name] <= high:
                raise error(f"{name} is outside its supported range.")
        if r["pose_start_percent"] >= r["pose_end_percent"]:
            raise error("Pose conditioning must end after it starts.")
    if r["model_id"] == "longcat-avatar-1.5":
        if r["steps"] != 8 or r["guidance"] != 1:
            raise error("LongCat Avatar 1.5 uses its released eight-step DMD schedule with guidance 1.")
        r["audio_conditioning_strength"] = float(r.get("audio_conditioning_strength", 1))
        if not 0 <= r["audio_conditioning_strength"] <= 2:
            raise error("Audio conditioning strength must be from 0 to 2.")
    if r["model_id"] == "ltx-2.5":
        if r["task"] == "reference-video":
            if r["steps"] != 8 or r["guidance"] != 1 or r["fps"] != 24:
                raise error("The official Ingredients IC-LoRA recipe uses eight steps, guidance 1 and 24 fps.")
            r["video_refinement"] = "single"
        if r.get("enhance_prompt") is None:
            r["enhance_prompt"] = r["task"] != "inpaint"
        r.setdefault("video_refinement", "two-stage")
        if r["video_refinement"] not in {"single", "two-stage"}:
            raise error("Choose single or two-stage video refinement.")
        if r["task"] == "video-extend":
            r["context_frames"] = int(r.get("context_frames", 17))
            if not 1 <= r["context_frames"] <= 129 or (r["context_frames"] - 1) % 8 or r["context_frames"] >= r["frames"]:
                raise error("Extend context must be 8n+1 frames, from 1 to 129, and shorter than total output.")
        if r["task"] == "video-outpaint":
            for key, default, low in [("outpaint_scale", 1, .1), ("outpaint_anchor_x", .5, 0), ("outpaint_anchor_y", .5, 0)]:
                r[key] = float(r.get(key, default))
                if not low <= r[key] <= 1:
                    raise error(f"{key} is outside its supported range.")
        if r["task"] == "video-upscale":
            r.setdefault("upscale_mode", "pixel-2x")
            if r["upscale_mode"] not in {"pixel-2x", "tiled-refine"}:
                raise error("Choose pixel-2x or tiled-refine upscaling.")
            if r["upscale_mode"] == "tiled-refine" and (max(r["width"], r["height"]) < 1024 or min(r["width"], r["height"]) < 576):
                raise error("Tiled refinement requires at least a 1024×576 canvas (either orientation).")
        if r["task"] == "alpha-matte" or r["task"] == "video-upscale" and r.get("upscale_mode") == "pixel-2x":
            if not r.get("source_width") or not r.get("source_height"):
                raise error("Import a source video before building this native-resolution operation.")
            if r["task"] == "alpha-matte" and any(int(r["source_" + axis]) % 2 for axis in ("width", "height")):
                raise error("Transparent video and its browser-compatible mask require even source dimensions. Crop or pad the source explicitly first.")
            factor = 2 if r["task"] == "video-upscale" else 1
            expected = [((int(r["source_" + axis]) * factor + 31) // 32) * 32 for axis in ("width", "height")]
            if [r["width"], r["height"]] != expected:
                raise error("This operation pads the native source dimensions for inference; it does not accept an arbitrary resize.")
        if r["task"] == "transition-video" and (r["fps"] != 24 or r["frames"] not in {121, 241}):
            raise error("Transitions use 121 or 241 frames at 24 fps; the actual durations are 5.04 or 10.04 seconds.")
    if r["model_id"] == "video-tools":
        r.setdefault("reframe_fit", "crop")
        r.setdefault("anchor_x", .5)
        r.setdefault("anchor_y", .5)
        if r["reframe_fit"] not in {"crop", "pad"} or not all(0 <= float(r[k]) <= 1 for k in ("anchor_x", "anchor_y")):
            raise error("Choose crop/pad and anchors from 0 to 1.")
    if r["task"] == "video-extend":
        r["extension_direction"] = r.get("extension_direction") or "sequel"
        if r["extension_direction"] not in {"sequel", "prequel"}:
            raise error("Choose sequel or prequel extension.")
    if r["task"] == "sdr-to-hdr":
        r["hdr_output_format"] = r.get("hdr_output_format") or "hevc10"
        if r["hdr_output_format"] not in {"hevc10", "prores10", "exr16"}:
            raise error("Choose 10-bit HEVC, 10-bit ProRes or 16-bit float EXR.")
        if r["hdr_output_format"] == "exr16" and r["width"] * r["height"] * r["frames"] * 6 > 4 * 1024**3:
            raise error("The uncompressed half-float EXR estimate exceeds 4 GiB; shorten the selected interval.")
    if r.get("encoding_quality", "legacy") not in {"legacy", "standard", "high"}:
        raise error("Choose standard or high output encoding quality.")
