from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    frames: int = Field(default=97, ge=9, le=2401)
    fps: float = Field(default=24, ge=1, le=120)
    steps: int = Field(default=8, ge=1, le=50)
    guidance: float = Field(default=1, ge=0, le=30)
    source_asset_id: str | None = None
    mask_asset_id: str | None = None
    reference_asset_id: str | None = None
    strength: float = Field(default=0.75, ge=0.05, le=1)
    generate_audio: bool = True
    preserve_audio: bool = True
    preserve_outside_mask: bool = True
    mask_tracking: bool = True
    mask_tracking_method: Literal["sam2", "flow", "static"] = "sam2"
    export_mask: bool = True
    trim_start: float = Field(default=0, ge=0, le=86400)
    mask_dilation: int = Field(default=8, ge=0, le=64)
    mask_feather: int = Field(default=8, ge=0, le=32)
    mask_edit_margin: int | None = Field(default=None, ge=0, le=64)

    @field_validator("source_asset_id", "mask_asset_id", "reference_asset_id")
    @classmethod
    def valid_id(cls, value):
        if value is None or value == "":
            return None
        if len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Use an asset ID returned by the upload endpoint")
        return value


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_provider: str | None = Field(default=None, max_length=40)
    comfy_url: str | None = None
    comfy_cloud_url: str | None = None
    comfy_api_key: str | None = Field(default=None, max_length=4096)
    comfy_cloud_api_key: str | None = Field(default=None, max_length=4096)
    comfy_cli_path: str | None = Field(default=None, max_length=4096)
    modal_app: str | None = Field(default=None, max_length=100)
    modal_environment: str | None = Field(default=None, max_length=100)
    modal_function: str | None = Field(default=None, max_length=100)
    modal_volume: str | None = Field(default=None, max_length=100)
    modal_progress_dict: str | None = Field(default=None, max_length=100)

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
