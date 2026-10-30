"""Isolated SAM3.1/ViTMatte worker. Frames use inherited anonymous RAM files."""
import argparse
import gc
import inspect
import json
import mmap
from pathlib import Path


def run(args):
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from sam3.model_builder import build_sam3_multiplex_video_predictor
    from sam_runtime_config import SAM3_COMMIT, SAM3_REVISION, VITMATTE_REVISION, MATTING_TRANSFORMERS

    if not torch.cuda.is_available():
        raise ValueError("Official SAM3.1 requires CUDA in the configured isolated Python environment.")
    n, h, w = args.frames, args.height, args.width
    source_map = mmap.mmap(args.source_fd, n * h * w * 3, access=mmap.ACCESS_READ)
    alpha_map = mmap.mmap(args.alpha_fd, n * h * w * 4)
    rgb = np.ndarray((n, h, w, 3), np.uint8, buffer=source_map)
    alpha = np.ndarray((n, h, w), np.float32, buffer=alpha_map)
    masks = np.zeros((n, h, w), dtype=bool)
    counts, seen, object_ids = [0] * n, set(), set()
    root = Path(args.models)
    predictor = build_sam3_multiplex_video_predictor(
        checkpoint_path=str(root / "matting/sam3.1/sam3.1_multiplex.pt"),
        max_num_objects=16, multiplex_count=16, use_fa3=False, compile=False,
        warm_up=False, async_loading_frames=False, default_output_prob_thresh=args.confidence)
    # This pinned release's base session dispatcher passes an unsupported
    # offload_state_to_cpu=False keyword to the multiplex init_state method.
    # Filter only that unused argument, preserving the supported API values.
    original_init = predictor.model.init_state
    valid_init = inspect.signature(original_init).parameters
    def compatible_init(**kw):
        if "offload_state_to_cpu" not in valid_init:
            kw.pop("offload_state_to_cpu", None)
        return original_init(**kw)
    predictor.model.init_state = compatible_init
    session = None
    selection = None
    selected_id = None
    selection_iou = None
    if args.selection_fd is not None:
        selection_map = mmap.mmap(args.selection_fd, h * w, access=mmap.ACCESS_READ)
        selection = np.ndarray((h, w), np.uint8, buffer=selection_map).copy().astype(bool)
        selection_map.close()


    def record(item):
        nonlocal selected_id, selection_iou
        index, output = int(item["frame_index"]), item["outputs"]
        if not 0 <= index < n:
            raise ValueError("SAM3.1 returned an invalid frame index.")
        values = output["out_binary_masks"]
        if isinstance(values, torch.Tensor):
            values = values.cpu().numpy()
        values = np.asarray(values, dtype=bool)
        if values.shape[1:] != (h, w) or len(values) > 16:
            raise ValueError("SAM3.1 returned an incompatible mask canvas or too many objects.")
        ids = [int(x) for x in output["out_obj_ids"]]
        if selection is not None:
            if selected_id is None:
                overlaps = [float((value & selection).sum()) / max(1, int((value | selection).sum())) for value in values]
                if index != 0 or not overlaps or max(overlaps) < .5:
                    raise ValueError("Official SAM3.1 could not match the native selected performer at first-frame IoU >= 0.5; no unrelated track was used.")
                best = int(np.argmax(overlaps))
                selected_id, selection_iou = ids[best], overlaps[best]
            masks[index] = values[ids.index(selected_id)] if selected_id in ids else False
        else:
            masks[index] = values.any(axis=0) if len(values) else False
        counts[index] = len(values)
        object_ids.update(int(x) for x in output["out_obj_ids"])
        seen.add(index)
        print(json.dumps({"progress": .05 + .5 * len(seen) / n, "stage": "Tracking selected foreground"}), flush=True)

    try:
        pil_frames = [Image.fromarray(frame) for frame in rgb]
        session = predictor.handle_request({"type": "start_session", "resource_path": pil_frames, "offload_video_to_cpu": True})["session_id"]
        del pil_frames
        record(predictor.handle_request({"type": "add_prompt", "session_id": session, "frame_index": 0, "text": args.prompt, "output_prob_thresh": args.confidence}))
        for item in predictor.handle_stream_request({"type": "propagate_in_video", "session_id": session, "propagation_direction": "forward", "start_frame_index": 0, "output_prob_thresh": args.confidence}):
            record(item)
    finally:
        if session:
            predictor.handle_request({"type": "close_session", "session_id": session})
        # The upstream constructor enters this autocast context for its lifetime.
        predictor.bf16_context.__exit__(None, None, None)
        del predictor, original_init
        gc.collect()
        torch.cuda.empty_cache()
    if len(seen) != n:
        raise ValueError("SAM3.1 did not return every requested frame; no partial matte was exported.")
    if not masks.any():
        raise ValueError("No foreground matched the description. Choose a visible subject description or another source interval.")
    if args.binary_only:
        alpha[:] = masks
        empty = [i for i, value in enumerate(masks) if not value.any()]
        print(json.dumps({"result": {"method": "official SAM3.1 binary performer support", "sam3_commit": SAM3_COMMIT,
            "sam3_revision": SAM3_REVISION, "foreground_prompt": args.prompt, "confidence": args.confidence,
            "selected_object_id": selected_id, "first_frame_selection_iou": selection_iou,
            "instance_counts": counts, "object_ids": sorted(object_ids), "empty_frames": empty,
            "vitmatte_used": False, "temporal_smoothing": False,
            "conditioning_masks_modified": False, "purpose": "final original-plate compositing support only"}}), flush=True)
        return
    from transformers import VitMatteForImageMatting, VitMatteImageProcessor
    processor = VitMatteImageProcessor.from_pretrained(root / "matting/vitmatte", local_files_only=True)
    model = VitMatteForImageMatting.from_pretrained(root / "matting/vitmatte", local_files_only=True).cuda().eval()
    kernel = np.ones((2 * args.radius + 1, 2 * args.radius + 1), np.uint8)
    with torch.inference_mode():
        for index, coarse in enumerate(masks):
            if not coarse.any():
                alpha[index] = 0
            else:
                foreground = cv2.erode(coarse.astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
                support = cv2.dilate(coarse.astype(np.uint8), kernel).astype(bool)
                trimap = np.zeros((h, w), np.uint8)
                trimap[support] = 128
                trimap[foreground] = 255
                inputs = processor(images=rgb[index], trimaps=trimap, return_tensors="pt").to("cuda")
                predicted = model(**inputs).alphas[0, 0, :h, :w].float().clamp(0, 1).cpu().numpy()
                predicted[~support], predicted[foreground] = 0, 1
                alpha[index] = predicted
            print(json.dumps({"progress": .55 + .43 * (index + 1) / n, "stage": "Refining soft alpha"}), flush=True)
    empty = [i for i, value in enumerate(masks) if not value.any()]
    print(json.dumps({"result": {"method": "SAM3.1 text concept tracking → trimap → ViTMatte Base", "sam3_commit": SAM3_COMMIT,
        "sam3_revision": SAM3_REVISION, "vitmatte_revision": VITMATTE_REVISION, "transformers": MATTING_TRANSFORMERS,
        "foreground_prompt": args.prompt, "confidence": args.confidence, "trimap_radius": args.radius,
        "instance_counts": counts, "object_ids": sorted(object_ids), "empty_frames": empty,
        "rgb": "original source pixels; alpha refinement only", "temporal_alpha": "independent per-frame refinement; no temporal smoothing",
        "compatibility": "ignore the unsupported offload_state_to_cpu=False session keyword; retain all other upstream arguments",
        "warnings": ([f"No selected foreground in {len(empty)} of {n} frames; their alpha is transparent."] if empty else []) +
            (["The 16-instance capacity was reached; inspect whether additional foreground instances were omitted."] if max(counts) == 16 else [])}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("source-fd", "alpha-fd", "frames", "width", "height", "radius"):
        parser.add_argument("--" + name, type=int, required=True)
    parser.add_argument("--binary-only", action="store_true")
    parser.add_argument("--selection-fd", type=int)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--models", required=True)
    run(parser.parse_args())
