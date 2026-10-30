"""Compatible undistilled FLUX3 inference for trained private adapters."""
import re
from .flux3_workflows import PROFILES, validate_flux3_request, build_flux3_workflow
from .training_models import BASE_SHA256

BASE_PROFILE = {**PROFILES["flux3-klein"], "unet": "flux3-image-klein-base-bf16.safetensors", "precision": "BF16 undistilled generator/encoder; INT8 prompt expander"}


def validate_character_request(r):
    if float(r.get("guidance", 3.5)) != 3.5:
        raise ValueError("The undistilled character profile uses the official CFG 3.5 recipe.")
    checked = dict(r, guidance=1)
    validate_flux3_request(checked)
    r.update({key: value for key, value in checked.items() if key != "guidance"})
    if not 0 <= float(r.get("character_strength", 1)) <= 2:
        raise ValueError("Character adapter strength must be from 0 to 2.")
    adapter = r.get("_character_adapter")
    if r.get("character_adapter_id") and not adapter:
        raise ValueError("Resolve the selected trained character through the private adapter registry before rendering.")
    if adapter:
        if adapter.get("model_id") != "flux3-klein-base" or adapter.get("base_model_sha256") != BASE_SHA256:
            raise ValueError("This character adapter was not trained against the selected base checkpoint.")
        if not re.fullmatch(r"openframe/[a-zA-Z0-9-]{16,64}/character\.safetensors", adapter.get("lora_name", "")):
            raise ValueError("Invalid registered character adapter location.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{3,31}", adapter.get("trigger_token", "")):
            raise ValueError("Invalid registered character trigger.")


def build_character_workflow(r, assets=None):
    graph = build_flux3_workflow(r, assets, profile=BASE_PROFILE)
    adapter = r.get("_character_adapter")
    if adapter:
        graph["character_adapter"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["model", 0], "lora_name": adapter["lora_name"], "strength_model": float(r.get("character_strength", 1))}}
        if r.get("provider") == "local":
            graph["character_adapter"]["class_type"] = "OpenFrameRegisteredCharacterAdapter"
            graph["character_adapter"]["inputs"]["sha256"] = adapter["sha256"]
        graph["sample"]["inputs"]["model"] = ["character_adapter", 0]
        graph["character_caption"] = {"class_type": "OpenFrameCharacterCaption", "inputs": {"caption": ["prompt_caption", 0], "trigger_token": adapter["trigger_token"]}}
        graph["positive"]["inputs"]["text"] = ["character_caption", 0]
        graph["save"]["inputs"]["caption"] = ["character_caption", 0]
    return graph
