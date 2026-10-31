"""Supported capabilities, not a list of hypothetical model integrations."""
from copy import deepcopy
from .image_catalog import FLUX3_MODELS
from .video_catalog import VIDEO_MODELS, additional_video_effects
from .depth_models import DEPTH_MODELS, depth_effect
from .narration_models import NARRATION_MODELS, NARRATION_EFFECTS
from .matte_models import MATTE_MODEL, MATTE_EFFECT
from .training_models import BASE_MODEL
from .vace14_models import VACE14_MODEL
from .recast_models import RECAST_MODEL
from .smoke_models import SMOKE_MODEL
from .relight_models import RELIGHT_MODEL
from .image_relight_models import IMAGE_RELIGHT_MODEL
from .portrait_relight_models import PORTRAIT_RELIGHT_MODEL
from .ripple_models import RIPPLE_MODEL
from .editvid_models import EDITVID_MODEL

# Per-effect limits for ordered additional references. None means the effect
# inherits the selected model's max_references (used by image effects, where
# the still source itself counts toward the limit).
REFERENCE_LIMITS_BY_TASK = {
    "reference-video": {"min": 1, "max": 9},
    "image-to-video": {"min": 0, "max": 1},
    "transition-video": {"min": 0, "max": 1},
    "inpaint": {"min": 0, "max": 1},
}

MODELS = [
    {"id": "ltx-2.3", "name": "LTX 2.3", "audio_modes_by_task": {"inpaint": ["source", "generated", "silent"], "restyle": ["source", "generated", "silent"]}, "recommended_vfx_longest_side": 1024, "strength_controls": {"inpaint": {"label": "Source guidance", "hint": "Higher values keep source conditioning stronger."}, "restyle": {"label": "Transformation strength", "hint": "Higher values allow more regeneration and can change scene geometry."}}, "family": "LTX", "badge": "VFX + audio", "description": "22B video generation with native audio and IC-LoRA masked video editing.", "tasks": ["text-to-video", "image-to-video", "inpaint", "restyle"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 8, "default_guidance": 1, "default_fps": 24, "default_frames": 97, "max_frames": 241, "dimension_multiple": 32, "frame_multiple": 8, "supports_audio": True, "supports_mask": True, "supports_reference": False, "reference_tasks": [], "min_width": 256, "min_height": 256, "max_width": 1536, "max_height": 1536},
    {"id": "ltx-0.9.8", "name": "LTX Fast", "family": "LTX", "badge": "Lightweight", "description": "Distilled 2B LTX model for rapid text-to-video and image animation. No native audio or IC-LoRA editing.", "tasks": ["text-to-video", "image-to-video"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 8, "default_guidance": 1, "default_fps": 24, "default_frames": 97, "max_frames": 241, "dimension_multiple": 32, "frame_multiple": 8, "supports_audio": False, "supports_mask": False, "supports_reference": False, "reference_tasks": [], "min_width": 256, "min_height": 256, "max_width": 1536, "max_height": 1536},
    {"id": "wan-vace", "name": "Wan VACE", "strength_controls": {"inpaint": {"label": "Source guidance", "hint": "Higher values preserve more source structure; lower values allow larger changes."}, "restyle": {"label": "Source guidance", "hint": "Higher values preserve more source structure; lower values allow larger style changes."}}, "family": "Wan", "badge": "Reference + VFX", "description": "Wan 2.1 VACE 1.3B for masked editing, reference-guided generation and scene restyling.", "tasks": ["text-to-video", "image-to-video", "inpaint", "restyle"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 20, "default_guidance": 5, "default_fps": 16, "default_frames": 81, "max_frames": 161, "dimension_multiple": 16, "frame_multiple": 4, "supports_audio": False, "supports_mask": True, "supports_reference": True, "reference_tasks": ["text-to-video", "inpaint", "restyle"], "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280},
]
MODELS.extend([
    {"id": "wan-s2v", "name": "Wan 2.2 Speech to Video", "family": "Wan", "badge": "Portrait + speech", "description": "Purpose-trained 14B sound-to-video model with a portrait and uploaded speech conditioning. Uses native 16 fps and preserves the selected recording.", "tasks": ["audio-to-video"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 20, "default_guidance": 6, "default_fps": 16, "fixed_fps": 16, "default_frames": 77, "min_frames": 73, "max_frames": 161, "dimension_multiple": 16, "frame_multiple": 4, "supports_audio": False, "supports_audio_input": True, "supports_mask": False, "supports_reference": False, "reference_tasks": [], "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280},
    {"id": "flux-klein-4b", "name": "FLUX.2 Klein 4B", "family": "FLUX", "badge": "Image + references", "description": "Native still-image generation and editing with up to four visual references. Reference guidance is not a trained or guaranteed identity lock.", "tasks": ["text-to-image", "image-edit"], "output_kind": "image", "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"], "default_steps": 4, "default_guidance": 1, "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 16, "frame_multiple": 1, "supports_audio": False, "supports_mask": False, "supports_reference": True, "reference_tasks": ["text-to-image", "image-edit"], "max_references": 4, "max_batch_size": 4, "min_width": 256, "min_height": 256, "max_width": 1536, "max_height": 1536},
    {"id": "wan-animate", "name": "Wan 2.2 Animate", "family": "Wan", "badge": "Motion + character", "description": "14B character animation with extracted body pose and face motion. Replacement additionally conditions on a tracked mask and the original background.", "tasks": ["motion-transfer", "character-replacement"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 6, "default_guidance": 1, "default_fps": 16, "default_frames": 77, "max_frames": 161, "dimension_multiple": 16, "frame_multiple": 4, "supports_audio": False, "supports_mask": True, "supports_reference": True, "reference_tasks": ["motion-transfer", "character-replacement"], "max_references": 1, "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280},
])
MODELS.extend([
    {"id": "birefnet", "name": "BiRefNet", "family": "BiRefNet", "badge": "Transparent PNG", "description": "Dedicated foreground segmentation with soft alpha. Keeps the source canvas size.", "tasks": ["background-removal"], "output_kind": "image", "preserve_source_dimensions": True, "aspect_ratios": [], "default_steps": 1, "default_guidance": 1, "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 1, "frame_multiple": 1, "supports_audio": False, "supports_mask": False, "supports_reference": False, "reference_tasks": [], "min_width": 64, "min_height": 64, "max_width": 4096, "max_height": 4096},
    {"id": "kokoro-82m", "name": "Kokoro 82M", "family": "Kokoro", "badge": "CPU speech", "description": "English text-to-speech with four built-in voices, generated inside ComfyUI on CPU. No voice cloning.", "tasks": ["text-to-speech"], "output_kind": "audio", "compute_kind": "cpu", "voices": [{"id": "af_heart", "name": "Heart · American English"}, {"id": "am_michael", "name": "Michael · American English"}, {"id": "bf_emma", "name": "Emma · British English"}, {"id": "bm_george", "name": "George · British English"}], "aspect_ratios": [], "default_steps": 1, "default_guidance": 1, "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 1, "frame_multiple": 1, "supports_audio": True, "supports_mask": False, "supports_reference": False, "reference_tasks": [], "min_width": 1, "min_height": 1, "max_width": 4096, "max_height": 4096, "max_script_characters": 2000},
])
MODELS.extend([VACE14_MODEL, RIPPLE_MODEL])
MODELS.extend(FLUX3_MODELS)
MODELS.extend(VIDEO_MODELS)
MODELS.extend(DEPTH_MODELS)
MODELS.extend(NARRATION_MODELS)
MODELS.append(MATTE_MODEL)
MODELS.append(BASE_MODEL)
MODELS.append(RECAST_MODEL)
MODELS.append(SMOKE_MODEL)
MODELS.append(RELIGHT_MODEL)
MODELS.append(IMAGE_RELIGHT_MODEL)
MODELS.append(PORTRAIT_RELIGHT_MODEL)
MODELS.append(EDITVID_MODEL)
MODELS.append({"id": "qwen-image-layered", "name": "Qwen Image Layered", "family": "Qwen", "badge": "RGBA layers", "description": "Regenerate a source image as an ordered stack of transparent layers. This is generative decomposition, not exact original-image segmentation.", "tasks": ["image-layers"], "output_kind": "image", "supported_providers": ["local"], "requires_prompt": False, "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"], "default_width": 640, "default_height": 640, "default_steps": 50, "default_guidance": 4, "default_negative_prompt": "", "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 16, "frame_multiple": 1, "min_width": 256, "min_height": 256, "max_width": 1024, "max_height": 1024, "max_batch_size": 1, "supports_reference": False, "supports_mask": False, "supports_audio": False, "reference_tasks": [], "layer_count": {"min": 2, "max": 8, "default": 4}, "license": "Apache-2.0", "implementation_status": "implemented; runtime validation pending"})
_IMAGE_MODELS = ["flux-klein-4b", "flux3-klein-base", *[model["id"] for model in FLUX3_MODELS]]
_ALL = [m["id"] for m in MODELS if "text-to-video" in m["tasks"]]
_VFX = ["ltx-2.5", "ltx-2.3", "wan-vace"]

def _effect(id, name, description, category, task, prompt, models, *, video=False, image=False, mask=False, audio=False, reference=False):
    item = {"id": id, "name": name, "description": description, "category": category, "task": task, "prompt": prompt, "model_ids": models, "requires_video": video, "requires_image": image, "requires_mask": mask, "requires_audio": audio, "requires_reference": reference, "output_kind": "audio" if task == "text-to-speech" else "image" if task in {"text-to-image", "image-edit", "image-outpaint", "background-removal"} else "video", "kind": "workflow-preset"}
    if limits := REFERENCE_LIMITS_BY_TASK.get(task):
        item.update(min_references=limits["min"], max_references=limits["max"])
    return item

EFFECTS = [
    _effect("text-to-video", "Create video", "Turn a detailed scene description into a moving shot.", "Generate", "text-to-video", "", _ALL),
    _effect("image-to-video", "Animate image", "Give a photograph movement while retaining its opening composition.", "Generate", "image-to-video", "Natural cinematic movement, coherent detail, smooth motion.", _ALL, image=True),
    _effect("reference-to-video", "Reference to video", "Steer a shot with one reference sheet built from one to nine character, location or prop images in order.", "Generate", "reference-video", "", ["ltx-2.5"], reference=True),
    _effect("remove-object", "Vanish", "Regenerate a painted region and preserve the surrounding plate.", "VFX", "inpaint", "A clean, uninterrupted background, natural scene details, consistent lighting and camera movement.", [*_VFX, "wan-vace-14b", "ltx-ripple"], video=True, mask=True),
    _effect("replace-object", "Replace", "Paint the area to change, then describe what belongs there.", "VFX", "inpaint", "", [*_VFX, "wan-vace-14b", "ltx-ripple"], video=True, mask=True),
    _effect("restyle", "Restyle", "Reimagine the full clip using video conditioning.", "Transform", "restyle", "A cinematic reinterpretation of the source scene, coherent movement and detailed textures.", [*_VFX, "flux-klein-editvid"], video=True),
    _effect("cinematic", "Cinematic", "A film-lighting prompt preset for video transformation.", "Transform", "restyle", "Cinematic natural lighting, rich film colours, realistic textures, subtle atmospheric depth, preserve the scene's composition and movement.", _VFX, video=True),
    _effect("slow-motion", "Slow motion", "Generate graceful slow motion from an opening image.", "Motion", "image-to-video", "Extreme slow motion, graceful deliberate movement, physically plausible motion, a smooth cinematic camera.", _ALL, image=True),
    _effect("dissolve", "Dissolve", "A prompt-led particle transformation starting from your image.", "VFX", "image-to-video", "The main subject gradually dissolves into thousands of fine luminous particles drifting through the air. Continuous transformation, cinematic lighting, steady camera.", _ALL, image=True),
    _effect("weather", "Change weather", "Reimagine a clip with atmosphere described in your prompt.", "Transform", "restyle", "Gentle rain falls through the scene, wet reflective surfaces, overcast cinematic light, coherent motion and natural atmosphere.", _VFX, video=True),
    _effect("product-reveal", "Product reveal", "Build a controlled product shot from a reference image.", "Motion", "image-to-video", "A premium product reveal, slow camera orbit, controlled studio highlights, elegant dark backdrop, preserve the product's shape and details.", _ALL, image=True),
    _effect("create-image", "Create image", "Generate a still image from text, with optional visual references.", "Image", "text-to-image", "", _IMAGE_MODELS),
    _effect("relight-image", "Relight image", "Choose portrait relighting with restored background, or the historical explicit lighting-map recipe.", "Image", "image-edit", "", ["qwen-portrait-relight", "qwen-image-relight"], image=True),
    _effect("edit-image", "Edit image", "Edit a source image with instructions and optional additional references.", "Image", "image-edit", "", _IMAGE_MODELS, image=True),
    _effect("expand-image", "Expand image", "Generate new canvas around an image while compositing its original pixels and transparency back unchanged.", "Image", "image-outpaint", "Extend the scene naturally into the added canvas, continuing its lighting, perspective and surroundings.", [model["id"] for model in FLUX3_MODELS], image=True),
    _effect("speak", "Speak", "Animate a portrait using an uploaded voice recording. The recording conditions the model and is retained in the output.", "Speak", "audio-to-video", "The person speaks naturally in sync with the provided speech recording, expressive mouth movement, steady camera.", ["longcat-avatar-1.5", "wan-s2v"], image=True, audio=True),
    {**_effect("motion-transfer", "Motion transfer", "Drive a reference character with actual source motion using the selected model's conditioning path.", "Motion", "motion-transfer", "The reference character follows the performer's movements, coherent anatomy and natural expression.", ["wan-animate-2", "wan-animate-2-distilled", "wan-animate"], video=True, reference=True), "default_model_id": "wan-animate"},
    {**_effect("character-replacement", "Character replacement", "Replace a performer using a character reference and tracked foreground. SCAIL-2 uses the full driving video; legacy Wan Animate uses extracted pose and face motion.", "Character", "character-replacement", "The reference character performs the original movements in the original scene, natural consistent lighting.", ["scail-2", "wan-animate"], video=True, mask=True, reference=True), "default_model_id": "scail-2"},
    _effect("remove-background", "Background remover", "Extract the foreground as a transparent PNG using a dedicated soft-alpha model.", "Image", "background-removal", "Extract the foreground.", ["birefnet"], image=True),
    {**_effect("generate-speech", "Generate speech", "Turn a script into a voice recording using the selected model's supported language and voice.", "Speak", "text-to-speech", "", ["ming-narration", "kokoro-82m"]), "default_model_id": "ming-narration"},
]
EFFECTS.extend(additional_video_effects(_effect))
EFFECTS.append({**_effect("relight", "Relight video", "Change scene lighting using the released sphere-conditioned LTX adapter.", "VFX", "restyle", "relight the video to match the light-direction ball. hard low-angle sunlight from the right", ["ltx-2.3-relight"], video=True), "requires_reference": True, "default_model_id": "ltx-2.3-relight"})
EFFECTS.extend(NARRATION_EFFECTS)
EFFECTS.append(MATTE_EFFECT)
EFFECTS.append(depth_effect(_effect))
EFFECTS.append({**_effect("decompose-image", "Image layers", "Regenerate an image as editable transparent layers in back-to-front order.", "Image", "image-layers", "", ["qwen-image-layered"], image=True), "prompt_policy": "optional", "output_kind": "image"})
PROVIDERS = [
    {"id": "local", "name": "Local ComfyUI", "description": "Run on your own ComfyUI installation.", "configured": True, "available": False},
    {"id": "comfy-cloud", "name": "Comfy Cloud / API", "description": "Connect directly to Comfy Cloud. Supported hosted workflows use explicit local media preparation/compositing; no rented-GPU relay.", "configured": False, "available": False},
]

def get_catalog():
    result = deepcopy({"models": MODELS, "effects": EFFECTS, "providers": PROVIDERS})
    enabled = {p["id"] for p in result["providers"]}
    for model in result["models"]:
        supported = model.get("supported_providers", ["local", "comfy-cloud"] if model["id"] in {"ltx-2.3", "ltx-0.9.8", "wan-vace"} else ["local"])
        model["enabled_providers"] = [p for p in supported if p in enabled]
    return result

def model_by_id(model_id):
    return next((deepcopy(x) for x in MODELS if x["id"] == model_id), None)

def reference_limits(model, effect):
    """Return the active {min, max} ordered-reference limit for one effect/model."""
    maximum = effect.get("max_references")
    minimum = effect.get("min_references", 0)
    by_task = (model or {}).get("reference_limits_by_task") or {}
    if effect.get("task") in by_task:
        task_limit = int(by_task[effect["task"]])
        maximum = task_limit if maximum is None else min(int(maximum), task_limit)
    if maximum is None:
        maximum = int((model or {}).get("max_references", 1))
    return {"min": max(0, int(minimum)), "max": max(0, maximum)}

def effect_by_id(effect_id):
    return next((deepcopy(x) for x in EFFECTS if x["id"] == effect_id), None)


def allows_restyle_first_frame(model, request):
    """The optional Union-Control still is scoped to declared effects and Canny."""
    return (request.get("restyle_method") == "canny" and
            request.get("effect_id") in model.get("restyle_first_frame_effects", []))
