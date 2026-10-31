from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImageLayoutElement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    description: str = Field(min_length=1, max_length=1000)
    bbox: tuple[int, int, int, int] | None = None
    source_reference: int | None = Field(default=None, ge=0, le=9)
    source_bbox: tuple[int, int, int, int] | None = None
    target_bbox: tuple[int, int, int, int] | None = None

    @field_validator("bbox", "source_bbox", "target_bbox")
    @classmethod
    def valid_box(cls, value):
        if value is not None:
            top, left, bottom, right = value
            if not (0 <= top < bottom <= 1000 and 0 <= left < right <= 1000):
                raise ValueError("Boxes use [top, left, bottom, right] within 0–1000, with positive area")
        return value

    @model_validator(mode="after")
    def valid_operation(self):
        if self.bbox is not None:
            if any(x is not None for x in (self.source_reference, self.source_bbox, self.target_bbox)):
                raise ValueError("Use bbox for layout, or source/target boxes for an edit, not both")
        elif self.source_reference is not None:
            if self.source_bbox is None:
                raise ValueError("A referenced edit requires its source box; a null target removes it")
        elif self.source_bbox is not None or self.target_bbox is None:
            raise ValueError("A new/replacement element requires a target box and no source box")
        return self


class RenderRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_id: str = Field(min_length=1, max_length=100)
    effect_id: str = Field(default="text-to-video", max_length=100)
    provider: str = Field(default="local", max_length=40)
    prompt: str = Field(default="", max_length=16000)
    negative_prompt: str = Field(default="", max_length=16000)
    seed: int = Field(default=-1, ge=-1, le=2**53 - 1)
    width: int = Field(default=768, ge=64, le=4096)
    height: int = Field(default=512, ge=64, le=4096)
    frames: int = Field(default=97, ge=1, le=2401)
    fps: float = Field(default=24, ge=1, le=120)
    steps: int = Field(default=8, ge=1, le=50)
    guidance: float = Field(default=1, ge=0, le=30)
    source_asset_id: str | None = None
    mask_asset_id: str | None = None
    reference_asset_id: str | None = None
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=50)
    image_prompt_mode: Literal["expand", "caption"] = "expand"
    image_layout: list[ImageLayoutElement] = Field(default_factory=list, max_length=32)
    image_preservation: Literal["none", "outside-mask", "inside-mask"] = "none"
    image_edit_focus: Literal["full", "masked-region"] = "full"
    image_brightness: float = Field(default=0, ge=-100, le=100)
    image_reference_megapixels: float = Field(default=1, ge=0.25, le=4)
    audio_asset_id: str | None = None
    audio_start: float = Field(default=0, ge=0, le=86400)
    batch_size: int = Field(default=1, ge=1, le=4)
    voice: Literal["af_heart", "am_michael", "bf_emma", "bm_george", "US_Emma", "UK_George", "灵小柔", "灵楷"] = "af_heart"
    speech_speed: float = Field(default=1, ge=0.5, le=2)
    generate_captions: bool = False
    caption_language: Literal["English", "Chinese"] = "English"
    audio_duration: float = Field(default=30, ge=0.1, le=300)
    strength: float = Field(default=0.75, ge=0.05, le=1)
    audio_mode: Literal["source", "generated", "silent"] | None = None
    inpaint_reference_mode: Literal["edited-first-frame"] | None = None
    inpaint_composite_mode: Literal["legacy", "plate-fit"] | None = None
    generate_audio: bool = True
    preserve_audio: bool = True
    preserve_outside_mask: bool = True
    mask_tracking: bool = True
    mask_tracking_method: Literal["sam2", "flow", "static"] = "sam2"
    export_mask: bool = True
    export_uncomposited: bool = False
    recast_composite_tracking: Literal["native", "official", "official-union"] | None = None
    recast_reference_cleanup: bool = False
    vace_reference_mode: Literal["appearance", "first-frame"] = "appearance"
    trim_start: float = Field(default=0, ge=0, le=86400)
    mask_dilation: int = Field(default=8, ge=0, le=64)
    mask_feather: int = Field(default=8, ge=0, le=32)
    mask_edit_margin: int | None = Field(default=None, ge=0, le=64)
    reframe_fit: Literal["crop", "pad"] = "crop"
    anchor_x: float = Field(default=0.5, ge=0, le=1)
    anchor_y: float = Field(default=0.5, ge=0, le=1)
    encoding_quality: Literal["legacy", "standard", "high"] = "legacy"
    motion_prompt: str = Field(default="", max_length=3000)
    pose_strength: float = Field(default=1, ge=0, le=2)
    reference_strength: float = Field(default=1, ge=0, le=2)
    pose_start_percent: float = Field(default=0, ge=0, le=1)
    pose_end_percent: float = Field(default=1, ge=0, le=1)
    audio_conditioning_strength: float = Field(default=1, ge=0, le=2)
    enhance_prompt: bool | None = None
    video_refinement: Literal["single", "two-stage"] = "two-stage"
    restyle_method: Literal["latent", "canny", "water"] = "latent"
    restyle_source_prompt: str = Field(default="", max_length=3000)
    relight_rotation: float = Field(default=0, ge=-180, le=180)
    relight_elevation: float = Field(default=45, ge=5, le=85)
    relight_intensity: float = Field(default=1, ge=0.2, le=3)
    context_frames: int = Field(default=17, ge=1, le=129)
    outpaint_scale: float = Field(default=1, ge=0.1, le=1)
    outpaint_anchor_x: float = Field(default=0.5, ge=0, le=1)
    outpaint_anchor_y: float = Field(default=0.5, ge=0, le=1)
    upscale_mode: Literal["pixel-2x", "tiled-refine"] = "pixel-2x"
    source_width: int | None = Field(default=None, ge=1, le=16384)
    source_height: int | None = Field(default=None, ge=1, le=16384)
    end_asset_id: str | None = None
    transition_include_inputs: bool = False
    input_frames: int | None = Field(default=None, ge=2, le=241)
    input_fps: float | None = Field(default=None, ge=1, le=120)
    layer_count: int = Field(default=4, ge=2, le=8)
    depth_colormap: Literal["grayscale", "turbo", "inferno", "magma", "viridis"] = "grayscale"
    depth_side_by_side: bool = False
    depth_inference_mode: Literal["chunk", "offline"] = "chunk"
    character_adapter_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    character_strength: float = Field(default=1, ge=0, le=2)
    hdr_output_format: Literal["hevc10", "prores10", "exr16"] = "hevc10"
    extension_direction: Literal["sequel", "prequel"] = "sequel"
    trimap_radius: int = Field(default=12, ge=1, le=64)
    subject_confidence: float = Field(default=.5, ge=.1, le=.9)

    @model_validator(mode="after")
    def valid_pose_interval(self):
        if self.pose_start_percent > self.pose_end_percent:
            raise ValueError("Pose start must not be later than pose end")
        return self

    @field_validator("source_asset_id", "mask_asset_id", "reference_asset_id", "audio_asset_id", "end_asset_id")
    @classmethod
    def valid_id(cls, value):
        if value is None or value == "":
            return None
        if len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Use an asset ID returned by the upload endpoint")
        return value

    @field_validator("reference_asset_ids")
    @classmethod
    def valid_references(cls, values):
        for value in values:
            if not value or cls.valid_id(value) is None:
                raise ValueError("Use uploaded image asset IDs")
        if len(set(values)) != len(values):
            raise ValueError("Reference images must be distinct")
        return values


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_provider: str | None = Field(default=None, max_length=40)
    comfy_url: str | None = None
    comfy_cloud_url: str | None = None
    comfy_api_key: str | None = Field(default=None, max_length=4096)
    comfy_cloud_api_key: str | None = Field(default=None, max_length=4096)
    comfy_cli_path: str | None = Field(default=None, max_length=4096)

    @field_validator("comfy_url", "comfy_cloud_url")
    @classmethod
    def valid_url(cls, value):
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Use an HTTP(S) URL without embedded credentials")
        return value.rstrip("/")


class JobUpdate(BaseModel):
    favorite: bool


class PresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    request: RenderRequest


def request_asset_ids(data: dict) -> dict[str, str]:
    result = {role: data[role + "_asset_id"] for role in ("source", "mask", "reference", "audio", "end") if data.get(role + "_asset_id")}
    result.update({f"reference_{index}": ident for index, ident in enumerate(data.get("reference_asset_ids", []))})
    if data.get("effect_id") == "train-identity":
        result.update({f"dataset_{index}": ident for index, ident in enumerate(data.get("dataset_asset_ids", []))})
        result.update({f"loss_mask_{index}": ident for index, ident in enumerate(data.get("loss_mask_asset_ids", []))})
    return result
