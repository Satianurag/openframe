"""Semantic selection is explicit; automatic AlphaGen remains a separate path."""


def build_matte_workflow(r, assets=None):
    source = (assets or {}).get("source", "source.mp4")
    return {
        "source": {"class_type": "OpenFrameSemanticMatte", "inputs": {
            "filename": source, "prompt": r["prompt"], "width": r["width"], "height": r["height"],
            "frames": r["frames"], "fps": r["fps"], "trim_start": r.get("trim_start", 0),
            "trimap_radius": r["trimap_radius"], "subject_confidence": r["subject_confidence"]}},
        "alpha_image": {"class_type": "MaskToImage", "inputs": {"mask": ["source", 1]}},
        "save": {"class_type": "OpenFrameSaveAlphaVideo", "inputs": {
            "original": ["source", 0], "matte": ["alpha_image", 0], "fps": r["fps"],
            "filename_prefix": str(r.get("job_id", "OpenFrameMatte")), "source_filename": source,
            "trim_start": r.get("trim_start", 0), "preserve_audio": r.get("preserve_audio", True)}},
    }
