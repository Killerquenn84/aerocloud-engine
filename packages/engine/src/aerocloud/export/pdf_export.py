"""PDF export from BezierGlyph (PROD-04).

Converts BezierGlyph contours to PDF bytes using ReportLab.

Coordinate convention:
    All internal BezierCurve control points are (y, x).
    The coordinate flip (y,x) → (x,y) happens EXACTLY ONCE in
    _build_glyph_path when extracting control points.
    Do NOT flip anywhere else.

Precision:
    DPI = 300 — print-quality resolution.
    PX_TO_PT = 72.0 / DPI = 0.24 pt/px — sub-millimeter precision.
    float64 control points are preserved through the conversion.

Key decisions:
    - ReportLab pdfgen.canvas via BytesIO
    - Page size = (width_px * PX_TO_PT, height_px * PX_TO_PT)
    - Each glyph: beginPath → moveTo → bezierCurveTo per segment → closePath → drawPath
    - Colors: optional hex fill per glyph; default fill is black (0,0,0)
"""

from __future__ import annotations

import io

from reportlab.lib.colors import HexColor, black
from reportlab.pdfgen import canvas as rl_canvas

from aerocloud.geometry.bezier import BezierGlyph

DPI: int = 300
PX_TO_PT: float = 72.0 / DPI  # 0.24 pt/px


def _hex_to_color(hex_str: str) -> HexColor:
    """Convert hex color string to ReportLab Color object."""
    return HexColor(hex_str)


def _build_glyph_path(
    c: rl_canvas.Canvas,
    glyph: BezierGlyph,
    fill_color: object | None = None,
) -> None:
    """Draw all contours of a BezierGlyph onto a ReportLab Canvas.

    Coordinate flip (y,x) → (x,y) happens here, ONCE per control point.
    Coordinates are scaled from pixels to points via PX_TO_PT.

    Args:
        c: ReportLab Canvas to draw on.
        glyph: BezierGlyph with (y,x) control points.
        fill_color: ReportLab Color or None (defaults to black).
    """
    if not glyph.contours:
        return

    if fill_color is not None:
        c.setFillColor(fill_color)
    else:
        c.setFillColor(black)

    c.setStrokeAlpha(0)  # no stroke

    for contour in glyph.contours:
        if not contour:
            continue

        # Begin path and move to start of first curve (p0 is (y, x))
        start = contour[0].p0
        start_x_pt = start[1] * PX_TO_PT  # x = p0[1]
        start_y_pt = start[0] * PX_TO_PT  # y = p0[0]

        p = c.beginPath()
        p.moveTo(start_x_pt, start_y_pt)

        for curve in contour:
            # p1, p2, p3 are (y, x) → flip to (x, y) for SVG/PDF
            x1 = curve.p1[1] * PX_TO_PT
            y1 = curve.p1[0] * PX_TO_PT
            x2 = curve.p2[1] * PX_TO_PT
            y2 = curve.p2[0] * PX_TO_PT
            x3 = curve.p3[1] * PX_TO_PT
            y3 = curve.p3[0] * PX_TO_PT
            p.curveTo(x1, y1, x2, y2, x3, y3)

        p.close()
        c.drawPath(p, fill=1, stroke=0)


def export_pdf(
    placed_glyphs: list[BezierGlyph],
    width_px: int,
    height_px: int,
    colors: list[str] | None = None,
) -> bytes:
    """Export a list of BezierGlyphs to PDF bytes.

    Creates a single-page PDF at 300 DPI with sub-millimeter precision.
    Page dimensions: (width_px * 0.24 pt, height_px * 0.24 pt).
    Empty glyphs (no contours) are silently skipped.

    Args:
        placed_glyphs: List of BezierGlyph objects to export.
        width_px: Canvas width in pixels.
        height_px: Canvas height in pixels.
        colors: Optional list of fill colors (hex strings) per glyph.
                Applied in glyph order. Skipped glyphs still consume a color slot.

    Returns:
        PDF document as bytes (starts with b'%PDF').
    """
    buf = io.BytesIO()
    page_w_pt = width_px * PX_TO_PT
    page_h_pt = height_px * PX_TO_PT

    c = rl_canvas.Canvas(buf, pagesize=(page_w_pt, page_h_pt))

    for idx, glyph in enumerate(placed_glyphs):
        fill_color = None
        if colors is not None and idx < len(colors):
            fill_color = _hex_to_color(colors[idx])

        _build_glyph_path(c, glyph, fill_color=fill_color)

    c.save()

    buf.seek(0)
    return buf.read()
