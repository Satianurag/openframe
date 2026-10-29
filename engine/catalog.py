"""Supported capabilities, not a list of hypothetical model integrations."""
from copy import deepcopy

MODELS = [
    {"id": "ltx-2.3", "name": "LTX 2.3", "recommended_vfx_longest_side": 1024, "strength_controls": {"inpaint": {"label": "Source guidance", "hint": "Higher values keep source conditioning stronger."}, "restyle": {"label": "Transformation strength", "hint": "Higher values allow more regeneration and can change scene geometry."}}, "family": "LTX", "badge": "VFX + audio", "description": "22B video generation with native audio and IC-LoRA masked video editing.", "tasks": ["text-to-video", "image-to-video", "inpaint", "restyle"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 8, "default_guidance": 1, "default_fps": 24, "default_frames": 97, "max_frames": 241, "dimension_multiple": 32, "frame_multiple": 8, "supports_audio": True, "supports_mask": True, "supports_reference": False, "reference_tasks": [], "min_width": 256, "min_height": 256, "max_width": 1536, "max_height": 1536},
    {"id": "ltx-0.9.8", "name": "LTX Fast", "family": "LTX", "badge": "Lightweight", "description": "Distilled 2B LTX model for rapid text-to-video and image animation. No native audio or IC-LoRA editing.", "tasks": ["text-to-video", "image-to-video"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 8, "default_guidance": 1, "default_fps": 24, "default_frames": 97, "max_frames": 241, "dimension_multiple": 32, "frame_multiple": 8, "supports_audio": False, "supports_mask": False, "supports_reference": False, "reference_tasks": [], "min_width": 256, "min_height": 256, "max_width": 1536, "max_height": 1536},
    {"id": "wan-vace", "name": "Wan VACE", "strength_controls": {"inpaint": {"label": "Source guidance", "hint": "Higher values preserve more source structure; lower values allow larger changes."}, "restyle": {"label": "Source guidance", "hint": "Higher values preserve more source structure; lower values allow larger style changes."}}, "family": "Wan", "badge": "Reference + VFX", "description": "Wan 2.1 VACE 1.3B for masked editing, reference-guided generation and scene restyling.", "tasks": ["text-to-video", "image-to-video", "inpaint", "restyle"], "aspect_ratios": ["16:9", "9:16", "1:1", "4:3"], "default_steps": 20, "default_guidance": 5, "default_fps": 16, "default_frames": 81, "max_frames": 161, "dimension_multiple": 16, "frame_multiple": 4, "supports_audio": False, "supports_mask": True, "supports_reference": True, "reference_tasks": ["text-to-video", "inpaint", "restyle"], "min_width": 256, "min_height": 256, "max_width": 1280, "max_height": 1280},
]
_ALL = [m["id"] for m in MODELS]
_VFX = ["ltx-2.3", "wan-vace"]

def _effect(id, name, description, category, task, prompt, models, *, video=False, image=False, mask=False):
    return {"id": id, "name": name, "description": description, "category": category, "task": task, "prompt": prompt, "model_ids": models, "requires_video": video, "requires_image": image, "requires_mask": mask, "kind": "workflow-preset"}

EFFECTS = [
    _effect("text-to-video", "Create video", "Turn a detailed scene description into a moving shot.", "Generate", "text-to-video", "", _ALL),
    _effect("image-to-video", "Animate image", "Give a photograph movement while retaining its opening composition.", "Generate", "image-to-video", "Natural cinematic movement, coherent detail, smooth motion.", _ALL, image=True),
    _effect("remove-object", "Vanish", "Regenerate a painted region and preserve the surrounding plate.", "VFX", "inpaint", "A clean, uninterrupted background, natural scene details, consistent lighting and camera movement.", _VFX, video=True, mask=True),
    _effect("replace-object", "Replace", "Paint the area to change, then describe what belongs there.", "VFX", "inpaint", "", _VFX, video=True, mask=True),
    _effect("restyle", "Restyle", "Reimagine the full clip using video conditioning.", "Transform", "restyle", "A cinematic reinterpretation of the source scene, coherent movement and detailed textures.", _VFX, video=True),
    _effect("cinematic", "Cinematic", "A film-lighting prompt preset for video transformation.", "Transform", "restyle", "Cinematic natural lighting, rich film colours, realistic textures, subtle atmospheric depth, preserve the scene's composition and movement.", _VFX, video=True),
    _effect("slow-motion", "Slow motion", "Generate graceful slow motion from an opening image.", "Motion", "image-to-video", "Extreme slow motion, graceful deliberate movement, physically plausible motion, a smooth cinematic camera.", _ALL, image=True),
    _effect("dissolve", "Dissolve", "A prompt-led particle transformation starting from your image.", "VFX", "image-to-video", "The main subject gradually dissolves into thousands of fine luminous particles drifting through the air. Continuous transformation, cinematic lighting, steady camera.", _ALL, image=True),
    _effect("weather", "Change weather", "Reimagine a clip with atmosphere described in your prompt.", "Transform", "restyle", "Gentle rain falls through the scene, wet reflective surfaces, overcast cinematic light, coherent motion and natural atmosphere.", _VFX, video=True),
    _effect("product-reveal", "Product reveal", "Build a controlled product shot from a reference image.", "Motion", "image-to-video", "A premium product reveal, slow camera orbit, controlled studio highlights, elegant dark backdrop, preserve the product's shape and details.", _ALL, image=True),
]
PROVIDERS = [
    {"id": "modal", "name": "Modal GPU", "description": "Your isolated ComfyUI GPU worker with cached model weights.", "configured": False, "available": False},
    {"id": "local", "name": "Local ComfyUI", "description": "Run on your own ComfyUI installation.", "configured": True, "available": False},
    {"id": "comfy-cloud", "name": "Comfy Cloud / API", "description": "Use a Comfy API deployment containing the OpenFrame Build.", "configured": False, "available": False},
]

def get_catalog():
    return deepcopy({"models": MODELS, "effects": EFFECTS, "providers": PROVIDERS})

def model_by_id(model_id):
    return next((deepcopy(x) for x in MODELS if x["id"] == model_id), None)

def effect_by_id(effect_id):
    return next((deepcopy(x) for x in EFFECTS if x["id"] == effect_id), None)
