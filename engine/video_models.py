"""Pinned video-model metadata; this module never contacts model services."""
WAN_WRAPPER_COMMIT = "088128b224242e110d3906c6750e9a3a348a659b"
LTX25_REVISION = "49b093a39c19169a8a81721dcc541e07e945232f"


def _file(repo, revision, file, category, size, sha=None, **extra):
    return {"repo": repo, "revision": revision, "file": file, "category": category, "size_bytes": size, **({"expected_sha256": sha} if sha else {}), **extra}


def video_model_files(existing):
    common_wan = [dict(x) for x in existing["wan-animate"] if x["category"] in {"text_encoders", "vae", "clip_vision"}]
    result = {"video-tools": []}
    for profile, filename, checksum in [
        ("wan-animate-2", "wan_animate_2_bf16.safetensors", "642e906c7deaa27072a90ea433319b18f274da438ba75e350373467a0421f177"),
        ("wan-animate-2-distilled", "wan_animate_2_distill_bf16.safetensors", "eb05383cb4b71228bbeb959f4468431a93ab25d0399054b317f399be114d08f9"),
    ]:
        result[profile] = [_file("Comfy-Org/Wan-Animate-2", "e7181fe1896b7f2ce34120d1a3663413548240d7", "diffusion_models/" + filename, "diffusion_models", 32789894104, checksum, license="Apache-2.0"), *common_wan]
    result["longcat-avatar-1.5"] = [
        _file("Kijai/WanVideo_comfy", "8260d429d19fd7a72304cad059160b95d843913f", "LongCat/LongCat-Avatar-15_bf16.safetensors", "diffusion_models", 31706036736, "7186e134eb6e9ca6346f8db8b981bfe13fc725fa1bb9f0ad007ed29690d10349", license="MIT (upstream model)", source_note="Kijai's single-file conversion for the pinned WanVideoWrapper; upstream meituan-longcat/LongCat-Video-Avatar-1.5."),
        _file("Kijai/WanVideo_comfy", "8260d429d19fd7a72304cad059160b95d843913f", "LongCat/LongCat-Avatar-15_dmd_distill_lora_rank128_bf16.safetensors", "loras", 1261613536, "fe8f66e2c9e7dffb910311c71a5e5927678439a23e83fd291b49870d1bca6157", license="MIT (upstream model)"),
        *[dict(x) for x in common_wan if x["category"] != "clip_vision"],
        *[_file("meituan-longcat/LongCat-Video-Avatar-1.5", "92016c71d5d318d0f5d84e4db30015a571484ab6", "whisper-large-v3/" + name, "audio_encoders/longcat-whisper-large-v3", size, sha, license="MIT") for name, size, sha in [
            ("config.json", 1272, None), ("preprocessor_config.json", 340, None),
            ("model.safetensors", 3087130976, "a8e94b85976e5864ba3e9525c7e6c83b2a1eca42d4b797a0c7c24d778e40fd95"),
        ]],
    ]
    ltx = []
    for file, category, size, sha in [
        ("diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors", "diffusion_models", 42018190584, "31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4"),
        ("text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors", "text_encoders", 26263858182, "ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1"),
        ("vae/ltx-2.5-video-vae-bf16.safetensors", "vae", 1472223346, "847e14ca7f3355debca0cea4eaa24ac0fbcdf0061da054ac89ca638a869ddba3"),
        ("vae/ltx-2.5-audio-vae-bf16.safetensors", "vae", 364866540, "c52733d37f6a7fb7949c3dc0fb468c6cb2169e4d836983a73babb9f0d54837a5"),
        ("latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors", "latent_upscale_models", 995778752, "eb5a71fe4068ee87ccdb1c3aa635e547ca76bd2d30ae20ae889f2c325c0677e8"),
    ]:
        extra = {"tasks": ["text-to-video", "image-to-video", "transition-video", "restyle"], "when": {"video_refinement": "two-stage"}} if category == "latent_upscale_models" else {}
        if category == "text_encoders":
            extra["tasks"] = ["text-to-video", "image-to-video", "reference-video", "transition-video", "inpaint", "restyle", "video-outpaint", "video-extend", "video-upscale", "alpha-matte", "clean-plate"]
        ltx.append(_file("Lightricks/LTX-2.5", LTX25_REVISION, file, category, size, sha, requires_access=True, license="LTX-2.5 repository license; Gemma component terms apply", **extra))
    ltx.append(_file("Comfy-Org/gemma-4", "63d0f7c476756b88910170c1df75e2384ea1af31", "text_encoders/gemma4_e2b_it_bf16.safetensors", "text_encoders", 10278774160, "dcc3c8d27be2db2ef38b78d564ebfa1e92eb24665ed2751f2983275f03a067c8", tasks=["text-to-video", "image-to-video", "reference-video", "transition-video", "inpaint", "restyle", "video-outpaint", "video-extend", "video-upscale", "clean-plate"], license="See Gemma 4 model terms", feature="enhance_prompt"))
    ltx.append(_file("Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control", "20a580c8606c06a0988d40375a61309e0fe5893d", "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", "loras", 654465352, "a1b888a87f661d27f08b394ae559e8e1050be33900bcc36a5cdf659e48f88d18", tasks=["restyle"], when={"restyle_method": "canny"}, license="LTX-2 Community License", source_note="Explicit LTX 2.5 pairing in the pinned Union-Control workflow; reference downscale factor comes from adapter metadata."))
    ltx.append(_file("Lightricks/LTX-2.5-22b-IC-LoRA-Water-Simulation", "7a458d0c206d6f80ee7bae2f46e21e959f6fc42e",
        "ltx-2.5-22b-ic-lora-water-simulation-0.9.safetensors", "loras", 906080568,
        "58c244d24a4381858749e66fae9fd1b91aec6b546f83f3f81a7a10b4934a7857",
        tasks=["restyle"], when={"restyle_method": "water"}, requires_access=True,
        license="LTX-2.x Community License", source_note="Official model card specifies native-resolution stage1 only, full dry RGB guide, ADD WATER caption, strength1 and CFG1; no refinement."))
    ltx.append(_file("Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients", "9cb727f45e0b88cfb49ce90cd6c04bbee4dda07e",
        "ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors", "loras", 1308778338,
        "515e4e139001ac6282357a5b35372e42e98b3affd5fcc886a52242abeed19559",
        tasks=["reference-video"], requires_access=True,
        license="LTX-2 Community License",
        source_note="Official reference-sheet Ingredients adapter pinned by the LTX 2.5 single-stage distilled example; strength 1.3."))
    inpaint = next(dict(x) for x in existing["ltx-2.3"] if x.get("tasks") == ["inpaint"])
    inpaint["tasks"] = ["inpaint", "video-outpaint"]
    inpaint["source_note"] = "Explicitly paired with LTX 2.5 in the official 2.5 inpaint/outpaint templates; the 2.3 filename is intentional."
    ltx.append(inpaint)
    for name, revision, filename, size, sha, tasks in [
        ("Clean-Plate", "5cdacad3ee33574ecb11120b873dec320de79b37", "ltx-2.5-22b-ic-lora-clean-plate-1.0.safetensors", 327318439, "27f4f7ba552d3bf7273dd817291123a5934f17e7698ca9cd8945b079a5358393", ["clean-plate"]),
        ("Alpha-Gen", "4cc554f7f8dd858b50e80f1d37d70ce0103f5c94", "ltx-2.5-22b-ic-lora-alpha-gen-0.9.safetensors", 1308787472, "d9e143f979e0756f0c83d772e6a8890f4c6b933db1f7d93fc06e25c179f3fd36", ["alpha-matte"]),
        ("Pixel-Spatial-Upscaler", "59f26f1e0c11af42f1affa924b4ef231e9e98b2a", "ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors", 327322640, "984851b769ea2bcb4c9e0a239a7676239e42c6a6001ddc69943b41ff0b283c1d", ["video-upscale"]),
        ("Refine-Details", "4912c478b35dd96b6cdcc5f7c7ff9d72c2c57929", "ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors", 1308787534, "771a84f70e143af89867fc714ebbf7bd6edcaa4974c0360cba4a2d292a99f0e6", ["video-upscale"]),
        ("SDR-To-HDR", "c7578ebddb54f4210e534e4d8cad698a5a520692", "ltx-2.5-22b-ic-lora-sdr-to-hdr-1.0.safetensors", 1308787472, "0b39eac09672c18d0d10f401d5e71a68a73225f1169df826b092b7e5ef489675", ["sdr-to-hdr"]),
    ]:
        extra = {"when": {"upscale_mode": "pixel-2x" if name == "Pixel-Spatial-Upscaler" else "tiled-refine"}} if name in {"Pixel-Spatial-Upscaler", "Refine-Details"} else {}
        ltx.append(_file("Lightricks/LTX-2.5-22b-IC-LoRA-" + name, revision, filename, "loras", size, sha, tasks=tasks, requires_access=True, license="LTX-2.5 adapter repository license", **extra))
    ltx.append(_file("Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR", "c7578ebddb54f4210e534e4d8cad698a5a520692", "ltx-2.5-22b-ic-lora-sdr-to-hdr-scene-emb.safetensors", "embeddings", 12614165, "63c03987a1984f6d4b3d3440c15deee66b0310c01950496329f983f5dc8c88bd", tasks=["sdr-to-hdr"], requires_access=True))
    result["ltx-2.5"] = ltx
    return result
