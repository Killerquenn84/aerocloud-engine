"""Shape (silhouette) models — Phase 4 Geometry input types."""

from __future__ import annotations

from pydantic import Field

from aerocloud.models.base import AeroCloudBase


class ShapeMetadata(AeroCloudBase):
    """Metadata about a decoded silhouette mask."""

    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    bbox_area_pixels: int = Field(..., ge=0, description="Pixels inside the shape bbox")
    fill_ratio: float = Field(..., ge=0.0, le=1.0, description="Filled pixels / total pixels")


class Shape(AeroCloudBase):
    """A silhouette shape for word placement.

    The mask payload is stored separately (Phase 4 will use numpy arrays
    cached by sha256 hash). This model only carries metadata + a reference.
    """

    shape_hash: str = Field(..., min_length=64, max_length=64, description="sha256 of mask bytes")
    metadata: ShapeMetadata
    source_format: str = Field(default="png", description="png | svg | raw")
