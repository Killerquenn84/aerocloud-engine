"""aerocloud.geometry — Phase 4 Geometry-v1.

Wave 0 stub: exposes error types only. `_assert_freetype()` and the (y, x)
boundary adapters land in Wave 1 (ADR-0005, ADR-0006).

Sign convention: sdf > 0 inside, sdf == 0 on boundary, sdf < 0 outside (ADR-0004).
Coordinate system: (y, x) canonical internally, (x, y) only at Pydantic boundary (ADR-0005).
"""

from __future__ import annotations

from aerocloud.geometry.errors import (
    EmptyMaskError,
    GeometryEnvironmentError,
    GeometryError,
    MaskFormatError,
    PlacementFailedError,
)

__all__ = [
    "EmptyMaskError",
    "GeometryEnvironmentError",
    "GeometryError",
    "MaskFormatError",
    "PlacementFailedError",
]
