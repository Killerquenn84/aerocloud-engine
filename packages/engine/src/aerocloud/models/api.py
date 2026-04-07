"""API request/response models — Phase 12 FastAPI types."""

from __future__ import annotations

from pydantic import Field

from aerocloud.models.base import AeroCloudBase
from aerocloud.models.layout import LayoutScore, PlacedWord


class RenderRequest(AeroCloudBase):
    """Request payload for POST /render."""

    text: str = Field(..., min_length=1, max_length=50_000)
    shape_b64: str = Field(..., description="Base64-encoded silhouette mask PNG")
    width: int = Field(default=1024, gt=0, le=4096)
    height: int = Field(default=1024, gt=0, le=4096)
    seed: int = Field(default=42, ge=0)
    max_words: int = Field(default=200, gt=0, le=2000)
    font_family: str = Field(default="Inter")


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
