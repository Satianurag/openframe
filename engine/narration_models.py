"""Pinned narration/word-timing weights for a configured CUDA ComfyUI host."""
MING_COMMIT = "9332fb9443325d4726ce02cefd4ec1c211df4079"
ASR_COMMIT = "7c6daf77a2421100f5fb066495372c00129d39ff"
MING_REVISION = "7247f4c94a5b2e987404ed28a5cfec41b1a4ca61"
ASR_REVISION = "7278e1e70fe206f11671096ffdd38061171dd6e5"
ALIGNER_REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
VOICES = [{"id": "US_Emma", "name": "Emma · US English"}, {"id": "UK_George", "name": "George · UK English"},
          {"id": "灵小柔", "name": "Ling Xiaorou · Chinese"}, {"id": "灵楷", "name": "Ling Kai · Chinese"}]


def entries(repo, revision, category, files, license):
    return [{"repo": repo, "revision": revision, "file": name, "category": category, "license": license,
             "size_bytes": value[0], **({"expected_sha256": value[1]} if len(value) > 1 else {})} for name, value in files.items()]


MING_FILES = entries("inclusionAI/Ming-3.0-tts-0.5b", MING_REVISION, "tts/ming3", {
    "model.safetensors": (2959055504, "45c4d78d8ad6b1d942e3da86ba035fece02de569f7b2ca7e9d121dfaf18d674c"),
    "campplus.onnx": (28303423, "a6ac6a63997761ae2997373e2ee1c47040854b4b759ea41ec48e4e42df0f4d73"),
    "tokenizer.json": (11431389, "87d54ca3b44ea2f822ba39a0a45cb1b61644bd6606d9d3536dea75367bffb06d"),
    "config.json": (4754,), "configuration.json": (51,), "added_tokens.json": (1785,), "merges.txt": (1671853,),
    "special_tokens_map.json": (2726,), "tokenizer_config.json": (16260,), "vocab.json": (2776833,),
}, "MIT")
ASR_FILES = entries("Qwen/Qwen3-ASR-1.7B", ASR_REVISION, "asr/qwen3", {
    "model-00001-of-00002.safetensors": (4220320824, "a4cd1f1a04d90b757dc7f7dd26254e69a013b19e80efe590a83c6a3bde8608d6"),
    "model-00002-of-00002.safetensors": (478200688, "6e0b9d9e09e2e0238e7ef3cc8a484ab387e91b90f1900bedf88bc92d7929ccfc"),
    "model.safetensors.index.json": (64821,), "config.json": (6194,), "generation_config.json": (142,),
    "chat_template.json": (1161,), "merges.txt": (1671853,), "preprocessor_config.json": (330,),
    "tokenizer_config.json": (12487,), "vocab.json": (2776833,),
}, "Apache-2.0")
ALIGNER_FILES = entries("Qwen/Qwen3-ForcedAligner-0.6B", ALIGNER_REVISION, "asr/qwen3-aligner", {
    "model.safetensors": (1835544544, "47831d0e82f96b20e9034dba01a075ee06436654719f6a68289e49f1b65ce0e7"),
    "config.json": (5982,), "generation_config.json": (115,), "chat_template.json": (1161,), "merges.txt": (1671853,),
    "preprocessor_config.json": (330,), "tokenizer_config.json": (12666,), "vocab.json": (2776833,),
}, "Apache-2.0")
NARRATION_MODEL_FILES = {"ming-narration": MING_FILES + [{**entry, "feature": "generate_captions"} for entry in ASR_FILES + ALIGNER_FILES],
                         "qwen-caption": ASR_FILES + ALIGNER_FILES}
COMMON = {"output_kind": "audio", "compute_kind": "gpu", "supported_providers": ["local"], "internal": True,
          "aspect_ratios": [], "default_steps": 1, "default_guidance": 1, "fixed_steps": 1, "fixed_guidance": 1,
          "default_fps": 1, "default_frames": 1, "max_frames": 1, "dimension_multiple": 1, "frame_multiple": 1,
          "supports_audio": True, "supports_mask": False, "supports_reference": False, "reference_tasks": [],
          "min_width": 1, "min_height": 1, "max_width": 4096, "max_height": 4096}
NARRATION_MODELS = [
    {**COMMON, "id": "ming-narration", "name": "Ming 3.0 narration + Qwen captions", "family": "Ming", "badge": "Sequence narration",
     "tasks": ["text-to-speech"], "voices": VOICES, "max_script_characters": 1200, "license": "MIT; optional Qwen captions Apache-2.0",
     "description": "Explicit English/Chinese built-in voices for sequence shots; actual synthesized duration must fit the shot. Optional ASR word timing is recognized from the generated audio."},
    {**COMMON, "id": "qwen-caption", "name": "Qwen3 ASR + forced alignment", "family": "Qwen", "badge": "Sequence captions",
     "tasks": ["audio-transcription"], "requires_prompt": False, "license": "Apache-2.0",
     "description": "Recognize and align an explicitly selected soundtrack interval. English/Chinese scope; no inferred narration or silent transcript replacement."},
]
NARRATION_EFFECTS = [
    {"id": "narrate-shot", "name": "Narrate sequence shot", "task": "text-to-speech", "model_ids": ["ming-narration"], "output_kind": "audio", "internal": True, "prompt": "", "category": "Sequence", "kind": "workflow-preset"},
    {"id": "transcribe-audio", "name": "Transcribe sequence soundtrack", "task": "audio-transcription", "model_ids": ["qwen-caption"], "output_kind": "audio", "internal": True, "prompt_policy": "empty", "requires_audio": True, "prompt": "", "category": "Sequence", "kind": "workflow-preset"},
]
NARRATION_EFFECTS = [{"requires_video": False, "requires_image": False, "requires_mask": False,
                      "requires_reference": False, "requires_audio": False, "description": "Internal sequence audio operation", **effect}
                     for effect in NARRATION_EFFECTS]
