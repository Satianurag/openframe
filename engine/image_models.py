"""Expected public metadata only; no weights are included or fetched on import."""
FLUX3_REPO = "black-forest-labs/flux-3-image-klein-comfy"
FLUX3_REVISION = "feef60b0aaf63a4773ace96636ebbcf43b881312"
FLUX3_TEMPLATE_REVISION = "14220b8bd3e86baa852959f17039613191e66656"


def _file(path, size, sha, **extra):
    return {"repo": FLUX3_REPO, "revision": FLUX3_REVISION, "file": path, "category": path.split("/")[0],
            "size_bytes": size, "expected_sha256": sha, "requires_access": True,
            "license": "FLUX Kommunity License 1.0; retain upstream component notices",
            "metadata_source": f"https://huggingface.co/{FLUX3_REPO}/blob/{FLUX3_REVISION}/{path}", **extra}


_VAE = _file("vae/flux2-vae.safetensors", 336211292, "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
             destination_name="flux3-package-vae.safetensors",
             source_note="Exact BFL FLUX3 package autoencoder, aliased to avoid replacing the differently packaged legacy FLUX2 file.")
FLUX3_MODEL_FILES = {
    "flux3-klein": [
        _file("diffusion_models/flux3-image-klein-bf16.safetensors", 11097404512, "c3e9813cdd049c831c836b2e9db61150e49a93fc1a4c63b256494642fee0bd7c"),
        _file("text_encoders/qwen3vl_4b_bf16.safetensors", 8875719408, "f0b24fc5c8d7c0ea6ca909da14c20af5cac53f22506be942c6c956f838b9630f"),
        _file("text_encoders/qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors", 9748113996, "cb8cb9b9dcd2569509de755dca54d96fd93a16a7aabfd2f4051f0a144230620f", role="prompt_expander", when={"image_prompt_mode": "expand"}),
        dict(_VAE),
    ],
    "flux3-klein-int8": [
        _file("diffusion_models/flux3-image-klein-int8-convrot.safetensors", 5827874779, "847d8933548afd93df4af2cac2498e70891bf28d9dae06d695f536992e168fe2"),
        _file("text_encoders/qwen3vl_4b_int8_convrot.safetensors", 4858559240, "32de113cbf8282b02cbff0794b637b9d6676da09314a1db5a30bcea9bf4ee01c"),
        _file("text_encoders/qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", 6724090780, "e5d85a7421d197bf5a12474511936ecabce19a833252f16e9310a983194a4458", role="prompt_expander", when={"image_prompt_mode": "expand"}),
        dict(_VAE),
    ],
}
