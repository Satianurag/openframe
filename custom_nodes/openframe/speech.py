"""Bounded CPU speech generation with explicit provisioned model files."""
from pathlib import Path
import uuid
import wave
import importlib.util
import shutil
import numpy as np
import torch
import folder_paths
import comfy.model_management

VOICES = ["af_heart", "am_michael", "bf_emma", "bm_george"]
_MODEL = None
_PIPELINES = {}


class OpenFrameKokoroSpeech:
    @classmethod
    def INPUT_TYPES(cls):
        root = Path(folder_paths.models_dir) / "tts/kokoro"
        ready = all(importlib.util.find_spec(name) is not None for name in ("kokoro", "en_core_web_sm")) and shutil.which("espeak-ng") is not None and all((root / name).is_file() for name in ["config.json", "kokoro-v1_0.pth", *[v + ".pt" for v in VOICES]])
        return {"required": {"text": ("STRING", {"multiline": True}), "voice": (VOICES, {"default": "af_heart", "openframe_kokoro_available": bool(ready)}), "speed": ("FLOAT", {"default": 1, "min": .5, "max": 2})}}
    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "synthesize"
    CATEGORY = "OpenFrame/Speech"

    def synthesize(self, text, voice, speed):
        global _MODEL
        if voice not in VOICES or not .5 <= speed <= 2 or not 1 <= len(text.strip()) <= 2000:
            raise ValueError("Choose a supported voice, speed 0.5–2, and an English script of 1–2,000 characters.")
        from kokoro import KModel, KPipeline
        import spacy.util
        if not spacy.util.is_package("en_core_web_sm") or not shutil.which("espeak-ng"):
            raise RuntimeError("Kokoro needs the provisioned en_core_web_sm package and espeak-ng. Install the speech dependencies before submitting; this node does not download them.")
        root = Path(folder_paths.models_dir) / "tts/kokoro"
        for name in ("config.json", "kokoro-v1_0.pth", voice + ".pt"):
            if not (root / name).is_file():
                raise RuntimeError(f"Missing Kokoro file {name}. Provision the kokoro-82m profile first.")
        if _MODEL is None:
            _MODEL = KModel(repo_id="hexgrad/Kokoro-82M", config=str(root / "config.json"), model=str(root / "kokoro-v1_0.pth")).to("cpu").eval()
        language = voice[0]
        if language not in _PIPELINES:
            _PIPELINES[language] = KPipeline(lang_code=language, repo_id="hexgrad/Kokoro-82M", model=_MODEL, trf=False, device="cpu")
        chunks, samples = [], 0
        for result in _PIPELINES[language](text, voice=str(root / (voice + ".pt")), speed=speed):
            comfy.model_management.throw_exception_if_processing_interrupted()
            if result.audio is None:
                continue
            chunk = result.audio.detach().cpu().float().reshape(-1)
            samples += chunk.numel()
            if samples > 180 * 24000:
                raise ValueError("Speech exceeded the 180-second job limit. Split the script; no truncated recording was saved.")
            chunks.append(chunk)
        if not chunks:
            raise ValueError("The script produced no spoken audio.")
        return ({"waveform": torch.cat(chunks).reshape(1, 1, -1), "sample_rate": 24000},)


class OpenFrameSaveAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audio": ("AUDIO",), "filename_prefix": ("STRING", {"default": "OpenFrame"})}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OpenFrame/Speech"

    def save(self, audio, filename_prefix):
        root = Path(folder_paths.get_output_directory()) / "openframe"
        root.mkdir(exist_ok=True)
        stem = "".join(c for c in filename_prefix if c.isalnum() or c in "-_")[:80] or "OpenFrame"
        name = f"{stem}_{uuid.uuid4().hex[:10]}.wav"
        waveform = audio["waveform"].detach().cpu().float()[0].numpy()
        pcm = np.round(np.clip(waveform, -1, 1).T * 32767).astype("<i2")
        with wave.open(str(root / name), "wb") as file:
            file.setnchannels(waveform.shape[0]); file.setsampwidth(2)
            file.setframerate(int(audio["sample_rate"])); file.writeframes(pcm.tobytes())
        return {"ui": {"audio": [{"filename": name, "subfolder": "openframe", "type": "output", "format": "audio/wav", "role": "result"}]}, "result": (str(root / name),)}
