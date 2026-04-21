"""Boolean union stub — implemented in Task 2."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry

from aerocloud.geometry.bezier import BezierGlyph


def union_glyphs(glyphs: list[BezierGlyph]) -> BaseGeometry:
    """Boolean union of BezierGlyph polygons (stub — implemented in Task 2)."""
    raise NotImplementedError("Implemented in Task 2")
