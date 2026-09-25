"""AeroCloud export module — Phase 12 Production-v1.

Provides:
    - Seam carving (PROD-01, PROD-02): energy map + DP seam + seam removal
    - PNG export (PROD-05): tensor-to-PNG conversion
    - Boolean union (PROD-06): Bezier glyph polygon merging via Shapely
    - SVG export (PROD-03): BezierGlyph to SVG document via lxml
    - PDF export (PROD-04): BezierGlyph to PDF bytes via ReportLab at 300 DPI

Imports are explicit per submodule to avoid transitive dependency issues
(e.g. boolean_union requires shapely + cv2/geometry extras).
"""

from __future__ import annotations

from aerocloud.export.boolean_union import bezier_curve_to_points, glyph_to_polygon, union_glyphs
from aerocloud.export.pdf_export import DPI, PX_TO_PT, export_pdf
from aerocloud.export.png_export import export_png
from aerocloud.export.seam_carving import (
    build_energy_map,
    find_vertical_seam,
    remove_vertical_seam,
)
from aerocloud.export.svg_export import export_svg, glyph_to_svg_path

__all__ = [
    "DPI",
    "PX_TO_PT",
    "bezier_curve_to_points",
    "build_energy_map",
    "export_pdf",
    "export_png",
    "export_svg",
    "find_vertical_seam",
    "glyph_to_polygon",
    "glyph_to_svg_path",
    "remove_vertical_seam",
    "union_glyphs",
]
