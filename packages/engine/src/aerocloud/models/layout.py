"""Layout models — Phase 6 Inner Loop output types."""

from __future__ import annotations

from pydantic import Field

from aerocloud.models.base import AeroCloudBase


class PlacedWord(AeroCloudBase):
    """A word with its final position, scale, and rotation in the layout."""

    surface: str
    font_family: str
    font_size: float = Field(..., gt=0.0)
    x: float = Field(..., description="Center x in pixel space")
    y: float = Field(..., description="Center y in pixel space")
    rotation_deg: float = Field(default=0.0, description="0 or 90 only per anti-feature policy")
    scale: float = Field(default=1.0, gt=0.0)


class LayoutScore(AeroCloudBase):
    """Quality metrics for a complete layout."""

    layout_coverage: float = Field(..., ge=0.0, le=1.0, description="LC metric")
    layout_uniformity: float = Field(..., ge=0.0, le=1.0, description="LU metric")
    space_saving: float = Field(..., ge=0.0, le=1.0, description="SS metric")
    compactness: float = Field(..., ge=0.0)
    aspect_ratio: float = Field(..., gt=0.0, description="Target ~1.618 (golden)")
    overlap_penalty: float = Field(default=0.0, ge=0.0)
    fidelity: float = Field(..., ge=0.0, le=1.0, description="cos_sim to reference weights")
