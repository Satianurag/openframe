"""Media endpoints and final assembly around genuine LTX transition diffusion."""


def validate_transition_request(request):
    if request["fps"] != 24 or request["frames"] not in {121, 241}:
        raise ValueError("Transitions use 121 or 241 frames at 24 fps (5.04 or 10.04 seconds).")
    if request.get("trim_start", 0):
        raise ValueError("Transitions use the complete supplied clips, each up to five seconds. Trim a longer source explicitly first.")
    if request.get("reframe_fit", "crop") not in {"crop", "pad"}:
        raise ValueError("Choose crop or pad for transition input framing.")
    for key in ("anchor_x", "anchor_y"):
        if not 0 <= float(request.get(key, .5)) <= 1:
            raise ValueError("Transition framing anchors must be between zero and one.")


def prepare_transition_images(node, request, assets, *, native_resize=False):
    validate_transition_request(request)
    files = assets or {}
    start = node("transition_inputs", "OpenFrameTransitionInputs",
        source_filename=files.get("source", "source.png"), end_filename=files.get("end", "end.png"),
        width=request["width"], height=request["height"], fit=request.get("reframe_fit", "crop"),
        anchor_x=request.get("anchor_x", .5), anchor_y=request.get("anchor_y", .5),
        **({"fit_on_load": False} if native_resize else {}))
    return start, ["transition_inputs", 1]


def save_transition(node, request, assets, images, audio=None):
    files = assets or {}
    extra = {"audio": audio} if audio is not None and request.get("generate_audio", True) else {}
    return node("save", "OpenFrameSaveTransition", images=images, fps=request["fps"], frames=request["frames"],
        source_filename=files.get("source", "source.png"), end_filename=files.get("end", "end.png"),
        include_inputs=request.get("transition_include_inputs", False), preserve_audio=request.get("preserve_audio", True),
        fit=request.get("reframe_fit", "crop"), anchor_x=request.get("anchor_x", .5), anchor_y=request.get("anchor_y", .5),
        encoding_quality=request.get("encoding_quality", "legacy"), filename_prefix=str(request.get("job_id", "OpenFrame")), **extra)
