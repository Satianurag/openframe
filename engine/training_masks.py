"""Opt-in spatial loss support; adapted from Apache-2.0 Fizgig.

Upstream: shootthesound/Fizgig@6fb10a3bc2f70c8d664262fb48358edbf505788b,
src/fizgig/{families/driver.py,flux3/driver.py,dataset/masks.py}.
See docs/licenses/Fizgig-LICENSE.txt. The original velocity target and timestep
weight remain unchanged. Only spatial weights are normalized per image.
"""
import hashlib
import json
from pathlib import Path
import random

FIZGIG_COMMIT = "6fb10a3bc2f70c8d664262fb48358edbf505788b"
OUTSIDE_WEIGHT = 0.1


def validate_loss_mask(path, size):
    from PIL import Image
    with Image.open(path) as mask:
        if mask.format != "PNG" or mask.mode != "L" or getattr(mask, "n_frames", 1) != 1 or mask.size != tuple(size):
            raise ValueError("Loss masks must be grayscale PNGs with the exact paired photograph dimensions.")
        from PIL import ImageStat
        coverage = ImageStat.Stat(mask).mean[0] / 255
        if coverage < .01:
            raise ValueError("A loss mask must cover at least1% of its photograph; review the full head, hair and ears.")
    return coverage


def paired_transform(transform, image, mask_path, **kwargs):
    """Replay only the existing CPU crop/flip RNG; leave image pixels/RNG unchanged."""
    import torch
    from PIL import Image
    before_torch, before_python = torch.get_rng_state(), random.getstate()
    transformed_image = transform(image, **kwargs)
    after_torch, after_python = torch.get_rng_state(), random.getstate()
    try:
        torch.set_rng_state(before_torch)
        random.setstate(before_python)
        with Image.open(mask_path) as mask:
            transformed_mask = (transform(mask.convert("RGB"), **kwargs)[:1] + 1) / 2
    finally:
        torch.set_rng_state(after_torch)
        random.setstate(after_python)
    if transformed_mask.mean().item() < .01:
        raise ValueError("The trainer crop removed too much head-mask support; review image/mask framing.")
    print("OPENFRAME_LOSS_MASK:" + json.dumps({
        "filename": Path(mask_path).name, "source_size": list(image.size),
        "transformed_shape": list(transformed_mask.shape),
        "coverage": transformed_mask.mean().item(),
        "transformed_sha256": hashlib.sha256(transformed_mask.numpy().tobytes()).hexdigest(),
    }), flush=True)
    return transformed_image, transformed_mask


def masked_velocity_loss(prediction, target, timestep_weight, pixel_mask, height, width):
    import torch.nn.functional as F
    # Fizgig uses area-resized spatial support, a0.1 floor, and per-image mean1
    # normalization. Keep Diffusers' existing timestep weighting separate.
    weights = F.interpolate(pixel_mask.float().to(prediction.device), size=(height, width), mode="area").flatten(1)
    if weights.shape != prediction.shape[:2]:
        raise ValueError("Loss mask token geometry differs from the native FLUX3 prediction.")
    weights = weights.clamp(min=OUTSIDE_WEIGHT, max=1.)
    weights = weights / weights.mean(dim=1, keepdim=True).clamp_min(1e-8)
    squared_error = (timestep_weight.float() * (prediction.float() - target.float()).pow(2)).mean(dim=-1)
    return (squared_error * weights).mean()


def patch_masked_trainer(source):
    """Patch only the checksum-pinned trainer; old unmasked source is untouched."""
    replacements = {
        'class DreamBoothDataset(Dataset):': '''from engine.training_masks import paired_transform, masked_velocity_loss
_OPENFRAME_MASKS = json.loads(Path(os.environ["OPENFRAME_TRAINING_MASKS"]).read_text())

class DreamBoothDataset(Dataset):''',
        '        self.pixel_values = []': '        self.loss_masks = []\n        self.pixel_values = []',
        '        for i, image in enumerate(self.instance_images):\n            image = exif_transpose(image)': '        for i, image in enumerate(self.instance_images):\n            loss_mask_path = _OPENFRAME_MASKS[Path(image.filename).name]\n            image = exif_transpose(image)',
        '''            image = self.train_transform(
                image,
                size=target,
                center_crop=args.center_crop,
                random_flip=args.random_flip,
            )
            self.pixel_values.append((image, bucket_idx))''': '''            image, loss_mask = paired_transform(
                self.train_transform, image, loss_mask_path,
                size=target, center_crop=args.center_crop, random_flip=args.random_flip,
            )
            self.loss_masks.append(loss_mask)
            self.pixel_values.append((image, bucket_idx))''',
        '        instance_image, bucket_idx = self.pixel_values[index % self.num_instance_images]': '        instance_image, bucket_idx = self.pixel_values[index % self.num_instance_images]\n        example["loss_mask"] = self.loss_masks[index % self.num_instance_images]',
        '        "indices": indices,': '        "loss_mask": torch.stack([example["loss_mask"] for example in examples]),\n        "indices": indices,',
        '''                loss = torch.mean(
                    (weighting.float() * (model_pred.float() - target.float()) ** 2).reshape(target.shape[0], -1),
                    1,
                )
                loss = loss.mean()''': '''                loss = masked_velocity_loss(model_pred, target, weighting, batch["loss_mask"], lh, lw)''',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise RuntimeError(f"Pinned trainer masked-loss adaptation mismatch: {old[:70]!r} occurs{source.count(old)}times.")
        source = source.replace(old, new)
    return source
