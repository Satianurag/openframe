"""Native distilled FLUX 3 graphs; all model choices are explicit and pinned.

Comfy templates: 14220b8bd3e86baa852959f17039613191e66656.
BFL's native package: feef60b0aaf63a4773ace96636ebbcf43b881312.
The helper nodes format/expand prompts and preserve source pixels; diffusion,
reference conditioning, text/image encoders and sampling remain native ComfyUI.
"""
import json

PROFILES = {
    "flux3-klein": {"unet": "flux3-image-klein-bf16.safetensors", "encoder": "qwen3vl_4b_bf16.safetensors",
                    "upsampler": "qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors", "precision": "BF16 generator/encoder, INT8 prompt upsampler"},
    "flux3-klein-int8": {"unet": "flux3-image-klein-int8-convrot.safetensors", "encoder": "qwen3vl_4b_int8_convrot.safetensors",
                         "upsampler": "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", "precision": "INT8 ConvRot generator/encoder, W4A8 prompt upsampler"},
}
VAE = "flux3-package-vae.safetensors"
REGION_PLUGIN_REVISION = "6005efc02f7745649118edd89cdd084c2b9bd3ae"
REGION_SIZE = 1024
REGION_DEPENDENCY = {
    "repository": "https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git",
    "revision": REGION_PLUGIN_REVISION, "license": "GPL-3.0",
    "directory": "custom_nodes/ComfyUI-Inpaint-CropAndStitch",
    "required_nodes": ["InpaintCropImproved", "InpaintStitchImproved"],
    "dependencies": ["numpy", "Pillow", "scipy", "torch", "torchvision"],
    "installation": "Check out this revision in the declared directory; reuse ComfyUI's compatible Torch/torchvision and install missing numpy/Pillow/scipy dependencies. Keep this external package under its upstream GPL license.",
}


def validate_flux3_request(r):
    """Also enforce the contract for CLI/export callers without Pydantic."""
    count = len(r.get("reference_asset_ids") or []) + bool(r.get("reference_asset_id")) + (r["task"] in {"image-edit", "image-outpaint"})
    if r["task"] == "text-to-image" and r.get("source_asset_id"):
        raise ValueError("Use image-edit for a source image, or attach it as an ordered reference for text-to-image.")
    if float(r.get("guidance", 1)) != 1 or r.get("negative_prompt", "").strip():
        raise ValueError("The distilled FLUX3 profiles use CFG 1 and no negative prompt, matching the official native workflow.")
    megapixels = float(r.get("image_reference_megapixels", 1))
    if not .25 <= megapixels <= 4 or count * megapixels > 16:
        raise ValueError("References use 0.25–4 megapixels each, with at most 16 megapixels total.")
    mode = r.get("image_prompt_mode", "expand")
    if mode not in {"expand", "caption"}:
        raise ValueError("Choose automatic prompt expansion or an explicit complete caption.")
    if mode == "caption" and len(str(r.get("prompt", "")).strip()) < 80:
        raise ValueError("Caption mode requires a complete scene/edit description of at least 80 characters; use prompt expansion for a short request.")
    preservation = r.get("image_preservation", "none")
    if r["task"] == "image-outpaint":
        if r.get("mask_asset_id"):
            raise ValueError("Expand Image derives the protected original rectangle; an external mask is not used.")
        if r.get("source_width") and r.get("source_height"):
            if (r["width"] < r["source_width"] or r["height"] < r["source_height"]
                    or (r["width"], r["height"]) == (r["source_width"], r["source_height"])):
                raise ValueError("Expansion must enlarge at least one axis without shrinking either original axis.")
        preservation = "inside-mask"
        r["mask_feather"] = 0
    if preservation not in {"none", "outside-mask", "inside-mask"}:
        raise ValueError("Unknown image preservation mode.")
    if preservation != "none" and r["task"] not in {"image-edit", "image-outpaint"}:
        raise ValueError("Pixel preservation applies only to source-image editing.")
    if r.get("mask_asset_id") and preservation == "none":
        raise ValueError("An image mask needs an explicit pixel-preservation mode. FLUX3 boxes alone are not hard masks.")
    rows = r.get("image_layout") or []
    focus = r.get("image_edit_focus", "full")
    if focus not in {"full", "masked-region"}:
        raise ValueError("Unknown image edit focus.")
    if focus == "masked-region" and (r["model_id"] not in PROFILES or r["task"] != "image-edit"
            or preservation != "outside-mask" or not r.get("source_asset_id") or not r.get("mask_asset_id")
            or count != 1 or rows):
        raise ValueError("Region focus requires distilled FLUX3, one source image, an outside-mask edit and no additional references or layout boxes.")
    if not isinstance(rows, list) or len(rows) > 32:
        raise ValueError("Use at most 32 image layout elements.")
    import re
    seen = set()
    for row in rows:
        name = row.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name) or name in seen:
            raise ValueError("Layout IDs must be unique lower-case names.")
        seen.add(name)
        if not isinstance(row.get("description"), str) or not 1 <= len(row["description"]) <= 1000:
            raise ValueError("Every layout element requires a bounded description.")
        for field in ("bbox", "source_bbox", "target_bbox"):
            box = row.get(field)
            if box is not None and (not isinstance(box, (list, tuple)) or len(box) != 4 or any(type(v) is not int for v in box)
                                    or not (0 <= box[0] < box[2] <= 1000 and 0 <= box[1] < box[3] <= 1000)):
                raise ValueError("Layout boxes must be positive-area [top,left,bottom,right] integers within 0–1000.")
        ref = row.get("source_reference")
        if ref is not None and (type(ref) is not int or not 0 <= ref < count):
            raise ValueError("A layout source reference must identify an attached image, in source-first order.")
        if row.get("bbox") is not None:
            if any(row.get(key) is not None for key in ("source_reference", "source_bbox", "target_bbox")):
                raise ValueError("A layout box cannot also contain source/target edit fields.")
        elif ref is not None:
            if row.get("source_bbox") is None:
                raise ValueError("Referenced edits need a source box.")
        elif row.get("source_bbox") is not None or row.get("target_bbox") is None:
            raise ValueError("New/replacement elements require a target box and no source box.")
    r.update(image_prompt_mode=mode, image_preservation=preservation, image_reference_megapixels=megapixels, image_layout=rows)


def build_flux3_workflow(r, assets=None, profile=None):
    files, graph = dict(assets or {}), {}
    profile = profile or PROFILES[r["model_id"]]
    region_focus = r.get("image_edit_focus", "full") == "masked-region"
    def node(name, cls, **inputs):
        graph[name] = {"class_type": cls, "inputs": inputs, "_meta": {"title": cls}}
        return [name, 0]

    model = node("model", "UNETLoader", unet_name=profile["unet"], weight_dtype="default")
    clip = node("text_encoder", "CLIPLoader", clip_name=profile["encoder"], type="flux3", device="default")
    vae = node("vae", "VAELoader", vae_name=VAE)
    references = []
    if r["task"] in {"image-edit", "image-outpaint"}:
        references.append(("image", files.get("source", "source.png")))
    if files.get("reference") or r.get("reference_asset_id"):
        references.append(("reference", files.get("reference", "reference.png")))
    count = max(len(r.get("reference_asset_ids") or []), sum(key.startswith("reference_") for key in files))
    references.extend((f"reference_{i}", files.get(f"reference_{i}", f"reference_{i}.png")) for i in range(count))
    if len(references) > 10:
        raise ValueError("FLUX3 supports at most ten total images including the source.")
    images, original = [], None
    for name, filename in references:
        image = node(name, "LoadImage", image=filename)
        if name == "image":
            original = image
            if region_focus:
                mask = node("mask", "OpenFrameLoadImageMask", image=files.get("mask", "mask.png"))
                node("region_crop", "InpaintCropImproved", image=original, mask=mask,
                     downscale_algorithm="bilinear", upscale_algorithm="bicubic",
                     preresize=False, preresize_mode="ensure minimum resolution",
                     preresize_min_width=1024, preresize_min_height=1024,
                     preresize_max_width=16384, preresize_max_height=16384,
                     mask_fill_holes=False, mask_expand_pixels=0, mask_invert=False,
                     mask_blend_pixels=0, mask_hipass_filter=0.0,
                     extend_for_outpainting=False, extend_up_factor=1.0, extend_down_factor=1.0,
                     extend_left_factor=1.0, extend_right_factor=1.0,
                     context_from_mask_extend_factor=1.2, output_resize_to_target_size=True,
                     output_target_width=REGION_SIZE, output_target_height=REGION_SIZE,
                     output_padding="16", device_mode="cpu (compatible)")
                image = node("region_info", "OpenFrameImageRegionInfo", image=["region_crop", 1],
                             source=original, stitcher=["region_crop", 0], plugin_revision=REGION_PLUGIN_REVISION)
            if r["task"] == "image-outpaint":
                image = node("expand_canvas", "OpenFrameExpandImageCanvas", image=image, source_alpha=["image", 1],
                             width=r["width"], height=r["height"], anchor_x=r.get("outpaint_anchor_x", .5), anchor_y=r.get("outpaint_anchor_y", .5))
                original = image
        # Both the captioner and VAE see the same ordered, aspect-preserved refs.
        images.append(node(name + "_resize", "ImageScaleToTotalPixels", image=image, upscale_method="lanczos",
                           megapixels=r["image_reference_megapixels"], resolution_steps=16))
    prompt_inputs = {"request": r["prompt"], "mode": r["image_prompt_mode"], "width": r["width"], "height": r["height"],
                     "layout_json": json.dumps(r["image_layout"], ensure_ascii=False)}
    if region_focus:
        prompt_inputs.update(width=REGION_SIZE, height=REGION_SIZE)
    prompt_inputs.update({f"image_{index}": value for index, value in enumerate(images)})
    if r["image_prompt_mode"] == "expand":
        prompt_inputs["clip"] = node("prompt_model", "CLIPLoader", clip_name=profile["upsampler"], type="flux3", device="default")
    prompt = node("prompt_caption", "OpenFrameFlux3Prompt", **prompt_inputs)
    positive = node("positive", "CLIPTextEncode", clip=clip, text=prompt)
    negative = node("negative", "CLIPTextEncode", clip=clip, text="")
    # This is the same native reference-latent append operation used by
    # ReferenceMultiLatent, with explicit fixed slots for portable API canvases.
    for index, image in enumerate(images):
        latent = node(f"ref_encode_{index}", "VAEEncode", pixels=image, vae=vae)
        positive = node(f"ref_positive_{index}", "ReferenceLatent", conditioning=positive, latent=latent)
        negative = node(f"ref_negative_{index}", "ReferenceLatent", conditioning=negative, latent=latent)
    preservation_mask = None
    anchored_canvas = noise_mask = None
    if r["task"] == "image-outpaint":
        anchored_canvas = ["expand_canvas", 0]
        noise_mask = node("canvas_outside", "InvertMask", mask=["expand_canvas", 1])
    elif region_focus:
        preservation_mask = ["mask", 0]
        anchored_canvas, noise_mask = ["region_info", 0], ["region_crop", 2]
    elif r["image_preservation"] != "none":
        preservation_mask = node("mask", "OpenFrameLoadImageMask", image=files.get("mask", "mask.png"))
        anchored_canvas = node("edit_canvas", "OpenFrameImageEditCanvas", image=original, mask=preservation_mask,
                               width=r["width"], height=r["height"], preservation=r["image_preservation"])
        noise_mask = ["edit_canvas", 1]
    if anchored_canvas is not None:
        # Anchor the original throughout native denoising, not only at final
        # compositing. Encode the full canvas, not its smaller reference copy.
        latent = node("canvas_encode", "VAEEncode", pixels=anchored_canvas, vae=vae)
        if r["batch_size"] > 1:
            latent = node("canvas_batch", "RepeatLatentBatch", samples=latent, amount=r["batch_size"])
        latent = node("canvas_noise_mask", "SetLatentNoiseMask", samples=latent, mask=noise_mask)
    else:
        latent = node("empty", "EmptyFlux2LatentImage", width=r["width"], height=r["height"], batch_size=r["batch_size"])
    sample = node("sample", "KSampler", model=model, positive=positive, negative=negative, latent_image=latent,
                  seed=r["seed"], steps=r["steps"], cfg=r["guidance"], sampler_name="euler", scheduler="simple", denoise=1.0)
    result = node("decode", "VAEDecode", samples=sample, vae=vae)
    if region_focus:
        result = node("region_stitch", "InpaintStitchImproved", stitcher=["region_crop", 0], inpainted_image=result)
    extra = {}
    if r["image_preservation"] != "none":
        if r["task"] == "image-outpaint":
            extra = {"source": original, "source_alpha": ["expand_canvas", 2], "mask": ["expand_canvas", 1],
                     "harmonize_outside": True}
        else:
            extra = {"source": original, "source_alpha": ["image", 1], "mask": preservation_mask}
    node("save", "OpenFrameSaveImage", images=result, caption=prompt, filename_prefix=str(r.get("job_id", "OpenFrame")),
         preservation=r["image_preservation"], feather=int(r.get("mask_feather", 8)), **extra)
    return graph
