"""Native single-pass transition graph adapted from the MIT Comfy template.

The sampler, guide ordering, guide strength, preprocessing, weights and decoder
settings follow the pinned template. OpenFrame supplies real media endpoints,
bounded 8n+1 output dimensions/timing, prompt provenance and optional assembly.
No midpoint still, alpha dissolve, optical-flow interpolation or Fluid overlay.
"""
import re
from .smoke_models import CHECKPOINT, ENCODER, ADAPTER
from .transitions import prepare_transition_images, save_transition


def build_smoke_workflow(r, assets=None):
    graph = {}

    def node(name, kind, **inputs):
        graph[name] = {"class_type": kind, "inputs": inputs}
        return [name, 0]

    start, end = prepare_transition_images(node, r, assets, native_resize=True)
    for name, image in (("start", start), ("end", end)):
        resized = node(name + "_resize", "ResizeImageMaskNode", input=image,
            resize_type="scale dimensions", **{"resize_type.width": r["width"],
            "resize_type.height": r["height"], "resize_type.crop": "center", "scale_method": "nearest-exact"})
        node(name + "_preprocess", "LTXVPreprocess", image=resized, img_compression=25)

    base = node("model", "CheckpointLoaderSimple", ckpt_name=CHECKPOINT)
    vae = ["model", 2]
    model = node("adapter", "LoraLoaderModelOnly", model=base, lora_name=ADAPTER, strength_model=1.0)
    clip = node("text_encoder", "LTXAVTextEncoderLoader", text_encoder=ENCODER, ckpt_name=CHECKPOINT, device="default")
    audio_vae = node("audio_vae", "LTXVAudioVAELoader", ckpt_name=CHECKPOINT)
    prompt = r["prompt"]
    if not re.search(r"\bzhuanchang\b", prompt, flags=re.IGNORECASE):
        prompt = prompt.rstrip(" ,.") + ", zhuanchang"
    prompt = node("prompt_record", "OpenFrameRecordVideoPrompt", original=r["prompt"], model_prompt=prompt, enhanced=False)
    positive = node("positive", "CLIPTextEncode", clip=clip, text=prompt)
    negative = node("negative", "CLIPTextEncode", clip=clip, text=r["negative_prompt"])
    node("condition", "LTXVConditioning", positive=positive, negative=negative, frame_rate=r["fps"])
    empty = node("empty", "EmptyLTXVLatentVideo", width=r["width"], height=r["height"], length=r["frames"], batch_size=1)
    audio = node("empty_audio", "LTXVEmptyLatentAudio", audio_vae=audio_vae,
        frames_number=r["frames"], frame_rate=r["fps"], batch_size=1)
    node("guide_start", "LTXVAddGuide", positive=["condition", 0], negative=["condition", 1],
        vae=vae, latent=empty, image=["start_preprocess", 0], frame_idx=0, strength=.7)
    node("guide_end", "LTXVAddGuide", positive=["guide_start", 0], negative=["guide_start", 1],
        vae=vae, latent=["guide_start", 2], image=["end_preprocess", 0], frame_idx=-1, strength=.7)
    av = node("av", "LTXVConcatAVLatent", video_latent=["guide_end", 2], audio_latent=audio)
    guider = node("guider", "CFGGuider", model=model, positive=["guide_end", 0], negative=["guide_end", 1], cfg=1.0)
    noise = node("noise", "RandomNoise", noise_seed=r["seed"])
    sampler = node("sampler", "SamplerEulerAncestral", eta=0.0, s_noise=1.0)
    sigmas = node("sigmas", "ManualSigmas", sigmas="1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0")
    node("sample", "SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler, sigmas=sigmas, latent_image=av)
    node("separate", "LTXVSeparateAVLatent", av_latent=["sample", 1])
    node("crop_guides", "LTXVCropGuides", positive=["guide_end", 0], negative=["guide_end", 1], latent=["separate", 0])
    decoded = node("decode", "VAEDecodeTiled", samples=["crop_guides", 2], vae=vae,
        tile_size=768, overlap=64, temporal_size=4096, temporal_overlap=64)
    decoded_audio = node("decode_audio", "LTXVAudioVAEDecode", samples=["separate", 1], audio_vae=audio_vae) if r.get("generate_audio", True) else None
    save_transition(node, r, assets, decoded, decoded_audio)
    return graph
