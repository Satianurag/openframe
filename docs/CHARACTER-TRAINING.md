# Character training and inference

## Local runtime

Character Training accepts20–50 distinct photographs and queues the real `OpenFrameTrainCharacter` output node on a configured Linux CUDA ComfyUI host. Follow [the runtime guide](../custom_nodes/openframe/CHARACTER-TRAINING-RUNTIME.md). The application does not download a user's adapter to the UI host, publish it, or silently transfer it between Comfy endpoints. Hosted Comfy Cloud training is unsupported.

The implementation uses the official [Diffusers FLUX3 Klein DreamBooth trainer](https://github.com/huggingface/diffusers/blob/aae97e79e8e6a55e0b43114f9c8916c06d4bca8c/examples/dreambooth/train_dreambooth_lora_flux3_klein.py), revision `aae97e79e8e6a55e0b43114f9c8916c06d4bca8c`. Original script SHA256: `89cc2ff1af1909c1652deefdee7a60e589c3d4e7169d22ab7e05e3ca0c49be72`. Training and inference use the matching undistilled FLUX3 Klein Base profile, not a distilled substitute. Model weights retain their declared license/access conditions; the application license does not override them.

## Request and recovery

The bounded request records name, trigger token,20–50 image IDs, steps500–3000, resolution512/768/1024, rank16/32, learning rate, seed and Local provider. Images are validated and hashed; duplicate image content is rejected. Optional `loss_mask_asset_ids` must contain one ordered PNG mask per photograph. The masked-loss adaptation retains the pinned trainer's image transformations and applies per-image normalized foreground loss with fixed outside weight0.1. Source and Apache attribution are retained in `engine/training_masks.py` and [Fizgig license](licenses/Fizgig-LICENSE.txt).

Checkpointing occurs every500 steps and retains at most two checkpoints. Cancellation removes the queued prompt or interrupts the running prompt and terminates its trainer child. There is no automatic retry, checkpoint resume or automatic validation render. Retry-from-start is explicit. Dataset assets and registered adapters remain protected by their persistent references.

Registry records bind the adapter to its configured Comfy host and matching base-model hash. Inference verifies the adapter SHA before native loading and applies the trigger token in the native caption path. An endpoint change or saved-request reuse does not move weights. Metadata bundles include exact requirements and provenance but not adapter weights or user photographs.

## Verified scope and limits

Targeted normalization, host binding, path safety, asset pairing, capability, CPU node/graph and portable bundle checks passed. Actual500-step training and matched registered-adapter inference exercised the Local HTTP/node path on a controlled Linux CUDA host. This does not establish a clean independent-PC installation or Cloud support.

The reviewed dataset contained20 distinct video-derived frames of one person in one outfit/location. It is correlated data, not20 independent photographs or evidence of broad identity generalization. Training executed with512 resolution, rank16 and learning rate0.0001. Full-image, improved-framing and masked-loss comparisons completed, but **trained-only identity acceptance failed**: coherent portraits still changed important face proportions.

A final reference-assisted candidate retained the same adapter, caption, seed and native50-step/CFG3.5 recipe, adding one reviewed photograph as native reference conditioning. Likeness improved materially, but it copied head/shoulder framing/background and missed the requested waist-up composition. This is a qualified reference-assistance result, not proof that the adapter alone preserves identity. See [the released-code rationale and limitations](research/character-reference-inference.md).

No further automatic training or parameter sweep is implied. User photographs, adapters and evaluation imagery are excluded from source releases.
