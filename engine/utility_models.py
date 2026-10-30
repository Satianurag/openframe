"""Metadata-only pins for the released auxiliary video models; no local downloads."""
TWEEN_COMMIT = "15b88d16898c14aa0812672f86186a82f4769594"
LDF_SOURCE_COMMIT = "61b34d2379df8a313e8e4cb467cc2f74c52b45d7"
LDF_SOURCE_SHA256 = "3a903aeb5353c7e5eb932f129d975d1750246502937d8f7b283b61a269c23668"

UTILITY_MODEL_FILES = {
    "ldf-vfi": [
        {"repo": "onecat-ai/LDF-VFI", "revision": "87816885edfe4dba20190aea399b40181239824f", "file": "Wan2.1_VAE_cond_v2.pth", "category": "ldf-vfi", "size_bytes": 801028218, "expected_sha256": "96fcd7f89998868a681b715d030eac99420335421785fccc581c2541303b9515", "license": "Apache-2.0"},
        {"repo": "onecat-ai/LDF-VFI", "revision": "87816885edfe4dba20190aea399b40181239824f", "file": "transformer/config.json", "category": "ldf-vfi/transformer", "size_bytes": 534, "license": "Apache-2.0"},
        {"repo": "onecat-ai/LDF-VFI", "revision": "87816885edfe4dba20190aea399b40181239824f", "file": "transformer/diffusion_pytorch_model.safetensors", "category": "ldf-vfi/transformer", "size_bytes": 5641946552, "expected_sha256": "73b82c245d9985f5311b0bb4568cba63bca0304ec83a26f17e57a89604174d0f", "license": "Apache-2.0"},
    ],
}
