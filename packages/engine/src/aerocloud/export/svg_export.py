"""SVG export from BezierGlyph (PROD-03).

Converts BezierGlyph contours to an SVG document using lxml.etree.

Coordinate convention:
    All internal BezierCurve control points are (y, x).
    The coordinate flip (y,x) → (x,y) happens EXACTLY ONCE in
    _bezier_curve_to_svg_cmd and in the M moveto in glyph_to_svg_path.
    Do NOT flip anywhere else.

Key decisions:
    - lxml.etree for SVG document generation (more reliable than svgelements API)
    - 6 decimal places for sub-pixel precision (D-03)
    - viewBox="0 0 {width} {height}" per SVG spec
    - Empty glyphs (no contours) are silently skipped
"""

from __future__ import annotations

from lxml import etree

from aerocloud.geometry.bezier import BezierCurve, BezierGlyph

SVG_NS = "http://www.w3.org/2000/svg"


def _bezier_curve_to_svg_cmd(curve: BezierCurve) -> str:
    """Convert one cubic Bezier segment to an SVG C command string.

    The ONLY place where internal (y, x) → SVG (x, y) flip occurs for curve points.
    p0 is NOT included in the output (it is the implicit current point, set by M).
    p1, p2, p3 are the three coordinate pairs of the C command.

    Format: "C x1,y1 x2,y2 x3,y3" with 6 decimal places.

    Args:
        curve: BezierCurve with (y, x) control points.

    Returns:
        SVG C command string.
    """
    # (y, x) → (x, y) flip: each point is (y, x), so SVG x = point[1], SVG y = point[0]
    def fmt(point: tuple[float, float]) -> str:
        svg_x = point[1]
        svg_y = point[0]
        return f"{svg_x:.6f},{svg_y:.6f}"

    return f"C {fmt(curve.p1)} {fmt(curve.p2)} {fmt(curve.p3)}"


def glyph_to_svg_path(glyph: BezierGlyph) -> str:
    """Convert a BezierGlyph to an SVG path d-attribute string.

    For each contour:
      - M x,y  — move to first point of first curve (p0, flipped)
      - C ...  — cubic bezier commands for remaining curves
      - Z      — close contour

    Multiple contours are joined with a space.

    Args:
        glyph: BezierGlyph with contours in (y, x) coordinate space.

    Returns:
        SVG path d-attribute string, or "" for empty glyphs.
    """
    if not glyph.contours:
        return ""

    parts: list[str] = []

    for contour in glyph.contours:
        if not contour:
            continue

        # Move to start point of the contour (first curve's p0)
        # p0 is (y, x) → flip to SVG (x, y)
        start = contour[0].p0
        svg_x0 = start[1]
        svg_y0 = start[0]
        segment_parts: list[str] = [f"M {svg_x0:.6f} {svg_y0:.6f}"]

        # Add C commands for each curve in the contour
        for curve in contour:
            segment_parts.append(_bezier_curve_to_svg_cmd(curve))

        segment_parts.append("Z")
        parts.append(" ".join(segment_parts))

    return " ".join(parts)


def export_svg(
    placed_glyphs: list[BezierGlyph],
    width: int,
    height: int,
    colors: list[str] | None = None,
) -> str:
    """Export a list of BezierGlyphs to an SVG document string.

    Creates an <svg> root element with width/height/viewBox attributes.
    Each non-empty glyph becomes a <path> child element. Empty glyphs
    (no contours) are silently skipped.

    Args:
        placed_glyphs: List of BezierGlyph objects to export.
        width: Canvas width in pixels (used as SVG viewBox width).
        height: Canvas height in pixels (used as SVG viewBox height).
        colors: Optional list of fill colors (hex strings) per glyph.
                If provided, len(colors) must be >= len(placed_glyphs).
                Colors are applied in glyph order, skipping empty glyphs.

    Returns:
        SVG document as a UTF-8 string.
    """
    root = etree.Element(
        f"{{{SVG_NS}}}svg",
        attrib={
            "xmlns": SVG_NS,
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        },
    )

    for idx, glyph in enumerate(placed_glyphs):
        d = glyph_to_svg_path(glyph)
        if not d:
            continue

        attrib: dict[str, str] = {"d": d}
        if colors is not None and idx < len(colors):
            attrib["fill"] = colors[idx]

        etree.SubElement(root, f"{{{SVG_NS}}}path", attrib=attrib)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)
