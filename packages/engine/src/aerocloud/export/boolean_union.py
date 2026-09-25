"""Boolean union export module for AeroCloud Bezier glyph merging (PROD-06).

Converts BezierGlyph contour trees to Shapely polygons and computes their
boolean union via shapely.ops.unary_union. The result is a Shapely geometry
(Polygon, MultiPolygon, or GeometryCollection) — it is NOT converted back to
BezierGlyph (anti-pattern: lossy round-trip per research).

References:
    - PROD-06: Boolean union via Shapely — Blueprint Teil X
    - T-12-01-03: DoS mitigation — tessellation point count capped at n=50

Design decisions:
    - De Casteljau tessellation (not adaptive subdivision) for determinism
    - (y, x) → (x, y) flip at Shapely boundary (D-14 coordinate convention)
    - First contour = outer ring, subsequent = holes (standard SVG winding)
    - Returns BaseGeometry — callers handle Polygon / MultiPolygon dispatch
"""

from __future__ import annotations

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from aerocloud.geometry.bezier import BezierCurve, BezierGlyph

_MAX_TESSELLATION_N = 50  # T-12-01-03: cap point count to prevent memory explosion


def bezier_curve_to_points(
    curve: BezierCurve,
    n: int = 20,
) -> list[tuple[float, float]]:
    """Tessellate a cubic Bezier curve into n+1 (x, y) Shapely-order points.

    Uses De Casteljau algorithm evaluated at t = 0, 1/n, 2/n, ..., 1.
    Coordinates are flipped from engine (y, x) convention to Shapely (x, y).

    Args:
        curve: BezierCurve with control points in (y, x) order (D-14).
        n: Number of segments (produces n+1 points). Capped at 50 (T-12-01-03).

    Returns:
        List of n+1 (x, y) float tuples suitable for Shapely geometry construction.
    """
    # T-12-01-03: DoS guard — cap tessellation granularity
    n = min(n, _MAX_TESSELLATION_N)

    # Unpack control points from (y, x) to separate y and x arrays
    p0y, p0x = curve.p0
    p1y, p1x = curve.p1
    p2y, p2x = curve.p2
    p3y, p3x = curve.p3

    points: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = i / n
        s = 1.0 - t
        # Cubic Bernstein basis (De Casteljau closed-form)
        b0 = s * s * s
        b1 = 3.0 * s * s * t
        b2 = 3.0 * s * t * t
        b3 = t * t * t
        # Evaluate in (y, x) space, then flip to (x, y) for Shapely (D-14)
        py = b0 * p0y + b1 * p1y + b2 * p2y + b3 * p3y
        px = b0 * p0x + b1 * p1x + b2 * p2x + b3 * p3x
        points.append((px, py))  # Shapely uses (x, y)

    return points


def glyph_to_polygon(glyph: BezierGlyph) -> Polygon | None:
    """Convert a BezierGlyph to a Shapely Polygon.

    The first contour in the glyph is treated as the outer ring.
    Subsequent contours are treated as interior holes (standard SVG convention).

    Args:
        glyph: BezierGlyph with one or more contours in (y, x) order (D-14).

    Returns:
        Shapely Polygon, or None if the glyph has no contours.
    """
    if not glyph.contours:
        return None

    def contour_to_ring(curves: tuple[BezierCurve, ...]) -> list[tuple[float, float]]:
        """Concatenate tessellated curve segments into a closed ring."""
        ring: list[tuple[float, float]] = []
        for curve in curves:
            pts = bezier_curve_to_points(curve, n=20)
            # Skip last point to avoid duplication at segment joins
            ring.extend(pts[:-1])
        return ring

    outer_ring = contour_to_ring(glyph.contours[0])
    holes = [contour_to_ring(c) for c in glyph.contours[1:]]

    return Polygon(outer_ring, holes)


def union_glyphs(glyphs: list[BezierGlyph]) -> BaseGeometry:
    """Compute the boolean union of a list of BezierGlyph polygons.

    Each glyph is tessellated to a Shapely Polygon via glyph_to_polygon().
    Glyphs with degenerate geometry (None polygon) are skipped.
    The union is computed via shapely.ops.unary_union.

    Per research anti-pattern: the result is NOT converted back to BezierGlyph.
    Callers receive a raw Shapely geometry (Polygon or MultiPolygon).

    Args:
        glyphs: List of BezierGlyph objects to union.

    Returns:
        Shapely BaseGeometry (Polygon, MultiPolygon, GeometryCollection, or
        empty geometry if input list is empty or all glyphs are degenerate).

    References:
        PROD-06: union_glyphs via shapely.ops.unary_union — Blueprint Teil X
    """
    if not glyphs:
        return Polygon()  # empty geometry

    polygons = [poly for g in glyphs if (poly := glyph_to_polygon(g)) is not None]

    if not polygons:
        return Polygon()  # all glyphs were degenerate

    return unary_union(polygons)
