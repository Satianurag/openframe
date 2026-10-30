"""Sequence-only native Comfy output graphs."""
import json
from .narration_models import VOICES


def normalize_narration(r):
    if r.get("provider") not in {"local"}:
        raise ValueError("Narration and word timing require a configured CUDA ComfyUI runtime; hosted Comfy Cloud does not provide these nodes/models.")
    r["caption_language"] = r.get("caption_language", "English")
    if r["caption_language"] not in {"English", "Chinese"}:
        raise ValueError("This narration/caption profile currently supports English and Chinese.")
    if r["model_id"] == "ming-narration":
        if r.get("voice") not in {item["id"] for item in VOICES} or not .75 <= float(r.get("speech_speed", 1)) <= 1.5:
            raise ValueError("Choose a supported Ming voice and an explicit speed from0.75 to1.5.")
        if (r["voice"] in {"US_Emma", "UK_George"}) != (r["caption_language"] == "English"):
            raise ValueError("Choose an English voice for English or a Chinese voice for Chinese narration.")
    else:
        r["generate_captions"] = True
        if not .1 <= float(r.get("audio_duration", 0)) <= 300:
            raise ValueError("Choose a soundtrack interval from0.1 to300seconds.")
    return r


def build_narration_workflow(r, assets=None):
    keep = ("model_id", "prompt", "voice", "speech_speed", "seed", "caption_language", "generate_captions", "audio_start", "audio_duration")
    request = {key: r[key] for key in keep if key in r}
    return {"save": {"class_type": "OpenFrameSequenceNarration", "inputs": {
        "request_json": json.dumps(request, ensure_ascii=False), "audio_filename": (assets or {}).get("audio", ""),
        "filename_prefix": str(r.get("job_id", "OpenFrameNarration")),
    }}}
