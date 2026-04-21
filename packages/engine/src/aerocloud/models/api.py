"""API request/response models — Phase 12 FastAPI types."""

from __future__ import annotations

from pydantic import Field, field_validator

from aerocloud.models.base import AeroCloudBase
from aerocloud.models.layout import LayoutScore, PlacedWord
from aerocloud.models.security import (
    validate_font_name,
    validate_hex_color,
    validate_no_path_traversal,
)


class RenderRequest(AeroCloudBase):
    """Request payload for POST /render."""

    text: str = Field(..., min_length=1, max_length=50_000)
    shape_b64: str = Field(..., description="Base64-encoded silhouette mask PNG")
    width: int = Field(default=1024, gt=0, le=4096)
    height: int = Field(default=1024, gt=0, le=4096)
    seed: int = Field(default=42, ge=0)
    max_words: int = Field(default=200, gt=0, le=2000)
    font_family: str = Field(default="Inter")
    colors: list[str] | None = Field(
        default=None,
        description="Optional list of hex fill colors per placed glyph",
    )

    @field_validator("font_family")
    @classmethod
    def _validate_font_family(cls, v: str) -> str:
        """Validate font_family against the assets/fonts/ allow-list (D-16)."""
        return validate_font_name(v)

    @field_validator("shape_b64")
    @classmethod
    def _validate_shape_b64(cls, v: str) -> str:
        """Reject path traversal patterns in shape_b64 field (D-17)."""
        return validate_no_path_traversal(v)

    @field_validator("colors", mode="before")
    @classmethod
    def _validate_colors(cls, v: object) -> object:
        """Validate each color in the colors list against hex allow-list (D-15)."""
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("colors must be a list of hex color strings")
        for color in v:
            if not isinstance(color, str):
                raise ValueError(f"Each color must be a string, got: {type(color)}")
            validate_hex_color(color)
        return v


class RenderResult(AeroCloudBase):
    """Successful render response."""

    reproducibility_id: str
    placed_words: list[PlacedWord]
    score: LayoutScore
    png_b64: str = Field(..., description="Base64-encoded rendered PNG")
    svg: str | None = Field(default=None, description="Optional SVG export")
    elapsed_ms: int = Field(..., ge=0)


class RenderError(AeroCloudBase):
    """Error response envelope."""

    error_code: str = Field(..., description="Stable machine-readable code")
    message: str
    details: dict[str, str] = Field(default_factory=dict)
