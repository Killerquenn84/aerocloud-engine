"""Bezier path representation for glyph boundaries (GEO2-09).

Bridges Phase 4 GlyphBBox pixel buffers to cubic Bezier curve models for
Phase 12 SVG/PDF export (D-19). Uses OpenCV cv2.findContours +
cv2.approxPolyDP (Douglas-Peucker) per decision D-16.

Key design decisions:
- D-14: All internal coordinates are (y, x) — cv2 returns (x, y) and is
  flipped at the boundary (T-07-05-01 mitigation).
- D-17: BezierGlyph is a sibling model, NOT a subclass of frozen GlyphBBox.
- D-18: opencv-python-headless already installed.
- D-19: Bezier is per-glyph only, not per-silhouette.

Coordinate convention (D-14):
  All BezierCurve control points are (y, x) float64 tuples.
  cv2 returns contour points as shape (N, 1, 2) with columns [x, y].
  The flip ``pts[:, ::-1]`` converts [x, y] columns → [y, x] columns.
"""

from __future__ import annotations

import cv2
import numpy as np

from aerocloud.models.base import AeroCloudBase
from aerocloud.models.geometry import GlyphBBox


class BezierCurve(AeroCloudBase):
    """One cubic Bezier segment with four control points in (y, x) ordering.

    All coordinates are float64 for sub-millimeter precision in SVG/PDF export
    (D-19, T-07-05-03). Points follow Catmull-Rom → cubic Bezier conversion:
      P0 = start, P1 = control 1, P2 = control 2, P3 = end.

    Coordinate convention: (y, x) — row-major, D-14.
    """

    p0: tuple[float, float]  # (y, x) start
    p1: tuple[float, float]  # (y, x) control 1
    p2: tuple[float, float]  # (y, x) control 2
    p3: tuple[float, float]  # (y, x) end


class BezierGlyph(AeroCloudBase):
    """Bezier representation of a glyph's boundary contours (D-17).

    Sibling to GlyphBBox — stores Bezier paths for the same glyph.
    NOT a subclass of GlyphBBox (frozen Pydantic constraint prevents it).

    Attributes:
        font_family: Font family name (matches source GlyphBBox).
        size_pt: Point size (matches source GlyphBBox).
        codepoint: Unicode codepoint (matches source GlyphBBox).
        contours: Nested tuple — outer tuple = multiple contours (including
            holes), inner tuple = BezierCurve segments per contour.
        tolerance: Douglas-Peucker epsilon used (for reproducibility).
    """

    font_family: str
    size_pt: int
    codepoint: int
    contours: tuple[tuple[BezierCurve, ...], ...]
    tolerance: float


def _catmull_rom_to_bezier(pts: np.ndarray) -> list[BezierCurve]:
    """Convert simplified polygon points to cubic Bezier segments via Catmull-Rom.

    For each consecutive group of 4 points (with wrap-around), compute the
    two interior control points using the Catmull-Rom formula:
      P1_ctrl = P1 + (P2 - P0) / 6
      P2_ctrl = P2 - (P3 - P1) / 6

    This gives C1-continuous curves that pass through the polygon vertices.

    Args:
        pts: (N, 2) float64 array of polygon points in (y, x) order.

    Returns:
        List of BezierCurve segments. Returns empty list if fewer than 2 points.
    """
    n = len(pts)
    if n < 2:
        return []

    curves: list[BezierCurve] = []
    for i in range(n):
        # Indices wrap around for closed polygon
        i0 = (i - 1) % n
        i1 = i
        i2 = (i + 1) % n
        i3 = (i + 2) % n

        p0 = pts[i0]
        p1 = pts[i1]
        p2 = pts[i2]
        p3 = pts[i3]

        # Catmull-Rom → cubic Bezier control points
        ctrl1 = p1 + (p2 - p0) / 6.0
        ctrl2 = p2 - (p3 - p1) / 6.0

        curve = BezierCurve(
            p0=(float(p1[0]), float(p1[1])),
            p1=(float(ctrl1[0]), float(ctrl1[1])),
            p2=(float(ctrl2[0]), float(ctrl2[1])),
            p3=(float(p2[0]), float(p2[1])),
        )
        curves.append(curve)

    return curves


def glyph_to_bezier(glyph: GlyphBBox, tolerance: float = 1.0) -> BezierGlyph:
    """Extract Bezier path representation from a GlyphBBox pixel buffer.

    Pipeline (D-16):
    1. Handle empty pixel_buffer: if max == 0 → return BezierGlyph with empty contours.
    2. Binarize ink pixels: (pixel_buffer > 0).astype(uint8) * 255.
    3. cv2.findContours(RETR_LIST, CHAIN_APPROX_SIMPLE) → raw contours.
    4. For each contour: cv2.approxPolyDP(epsilon=tolerance) → simplified polygon.
    5. Flip cv2 (x, y) columns → (y, x) for D-14 coordinate convention (T-07-05-01).
    6. Fit cubic Bezier curves via Catmull-Rom conversion.
    7. Return BezierGlyph with identity fields copied from source GlyphBBox.

    Args:
        glyph: Source GlyphBBox with uint8 pixel_buffer.
        tolerance: Douglas-Peucker epsilon (pixels). Higher → fewer curves.
            Default 1.0 gives sub-millimeter precision per GEO2-09 research.

    Returns:
        BezierGlyph with Bezier-approximated contours and recorded tolerance.
    """
    # Handle empty pixel_buffer (whitespace glyphs, zero ink)
    if glyph.pixel_buffer.max() == 0:
        return BezierGlyph(
            font_family=glyph.font_family,
            size_pt=glyph.size_pt,
            codepoint=glyph.codepoint,
            contours=(),
            tolerance=tolerance,
        )

    # Binarize: ink pixels → 255, background → 0
    ink: np.ndarray = (glyph.pixel_buffer > 0).astype(np.uint8) * 255

    # Extract contours (RETR_LIST returns ALL contours, including holes)
    contours_raw, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    contours_out: list[tuple[BezierCurve, ...]] = []

    for contour in contours_raw:
        # Simplify polygon with Douglas-Peucker
        approx = cv2.approxPolyDP(contour, epsilon=tolerance, closed=True)
        # approx shape: (M, 1, 2) — cv2 convention with columns [x, y]
        pts_xy = approx.squeeze(1)  # shape (M, 2), columns [x, y]

        if len(pts_xy) < 2:
            continue

        # D-14 coordinate flip: cv2 (x, y) → (y, x) for numpy row-major (T-07-05-01)
        pts_yx: np.ndarray = pts_xy[:, ::-1].astype(np.float64)

        # Fit cubic Bezier curves via Catmull-Rom conversion
        curves = _catmull_rom_to_bezier(pts_yx)
        if curves:
            contours_out.append(tuple(curves))

    return BezierGlyph(
        font_family=glyph.font_family,
        size_pt=glyph.size_pt,
        codepoint=glyph.codepoint,
        contours=tuple(contours_out),
        tolerance=tolerance,
    )
