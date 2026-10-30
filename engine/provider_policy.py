"""Supported public execution providers."""


def require_provider_enabled(provider):
    if provider not in {"local", "comfy-cloud"}:
        raise ValueError("Unknown compute provider. Select Local ComfyUI or Comfy Cloud; no other provider was substituted.")
