"""AeroCloud export module — Phase 12 Production-v1.

Provides:
    - Seam carving (PROD-01, PROD-02): energy map + DP seam + seam removal
    - PNG export (PROD-05): tensor-to-PNG conversion
    - Boolean union (PROD-06): Bezier glyph polygon merging via Shapely

Imports are explicit per submodule to avoid transitive dependency issues
(e.g. boolean_union requires shapely + cv2/geometry extras).
"""

from __future__ import annotations

from aerocloud.export.boolean_union import bezier_curve_to_points, glyph_to_polygon, union_glyphs
from aerocloud.export.png_export import export_png
from aerocloud.export.seam_carving import (
    build_energy_map,
    find_vertical_seam,
    remove_vertical_seam,
)

__all__ = [
    "build_energy_map",
    "find_vertical_seam",
    "remove_vertical_seam",
    "export_png",
    "bezier_curve_to_points",
    "glyph_to_polygon",
    "union_glyphs",
]
