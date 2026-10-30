"""Isolated CUDA-host entry point; the studio process never imports model stacks."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["synthesize", "transcribe"])
    parser.add_argument("request")
    parser.add_argument("audio")
    parser.add_argument("metadata")
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text())
    root = Path(os.environ["OPENFRAME_MODEL_CACHE"])
    import numpy as np
    import soundfile as sf
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("The narration worker requires CUDA")
    seed = int(request.get("seed", 42))
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    audio = Path(args.audio)
    if args.mode == "synthesize":
        sys.path.insert(0, os.environ["OPENFRAME_MING_SOURCE"])
        from ming_tts import MingTTS
        model_dir = root / "tts/ming3"
        if not (model_dir / "model.safetensors").is_file():
            raise RuntimeError("Install the pinned Ming files on the configured CUDA ComfyUI host before starting")
        model = MingTTS(str(model_dir), device="cuda:0", text_normalization=True, cache_prompts=False)
        raw = audio.with_name(audio.stem + ".raw.wav")
        try:
            model.synthesize(task="IP", text=request["prompt"], controls={"ip": request["voice"]},
                             use_zero_spk_emb=True, max_decode_steps=1000, output_path=str(raw))
            info = sf.info(raw)
            if not 0 < info.duration <= 120:
                raise RuntimeError("Synthesized narration is empty or exceeds120seconds; shorten the script")
            speed = float(request.get("speech_speed", 1))
            if speed == 1:
                raw.replace(audio)
            else:
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af", f"atempo={speed}",
                                "-c:a", "pcm_s16le", str(audio)], check=True, capture_output=True, timeout=120)
            metadata = {"mode": "built-in voice", "voice": request["voice"], "language": request["caption_language"],
                        "script": request["prompt"], "speed": speed, "original_duration": info.duration,
                        "duration": sf.info(audio).duration, "text_normalization": True, "raw_text": False,
                        "note": "Published raw-text benchmark settings differ from production sentence splitting/normalization; no pronunciation guarantee."}
        finally:
            raw.unlink(missing_ok=True)
    else:
        from qwen_asr import Qwen3ASRModel
        info = sf.info(audio)
        if not 0 < info.duration <= 300.1:
            raise ValueError("Caption input must contain at most300seconds of selected audio")
        model = Qwen3ASRModel.from_pretrained(str(root / "asr/qwen3"), dtype=torch.bfloat16,
            device_map="cuda:0", attn_implementation="sdpa", local_files_only=True, max_inference_batch_size=1,
            max_new_tokens=4096, forced_aligner=str(root / "asr/qwen3-aligner"),
            forced_aligner_kwargs={"dtype": torch.bfloat16, "device_map": "cuda:0", "attn_implementation": "sdpa", "local_files_only": True})
        result = model.transcribe(audio=str(audio), language=request["caption_language"], return_time_stamps=True)[0]
        words = []
        for item in result.time_stamps or []:
            start, end, text = float(item.start_time), float(item.end_time), str(item.text).strip()
            if not text:
                continue
            if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start <= end <= info.duration + .1:
                raise ValueError("The aligner returned an invalid word interval")
            if words and start < words[-1]["start"]:
                raise ValueError("The aligner returned unordered words")
            words.append({"start": start, "end": min(end, info.duration), "text": text[:300]})
        if not words or len(words) > 10000:
            raise ValueError("No bounded word-aligned transcript was returned; review the selected soundtrack")
        metadata = {"language": result.language, "text": result.text, "words": words, "duration": info.duration,
                    "timing_source": "Qwen3-ASR recognition followed by Qwen3-ForcedAligner; times are seconds in the selected audio interval"}
    Path(args.metadata).write_text(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
