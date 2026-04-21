"""AeroCloud export module — Phase 12 Production-v1.

Provides:
    - Seam carving (PROD-01, PROD-02): energy map + DP seam + seam removal
    - PNG export (PROD-05): tensor-to-PNG conversion
    - Boolean union (PROD-06): Bezier glyph polygon merging via Shapely

Imports are explicit per submodule to avoid transitive dependency issues
(e.g. boolean_union requires shapely + cv2/geometry extras).
"""

from __future__ import annotations

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
    "union_glyphs",
]


def export_png(tensor: object, mode: str = "RGB") -> bytes:  # type: ignore[return]
    """Lazy import wrapper for export_png (requires torch)."""
    from aerocloud.export.png_export import export_png as _export_png

    return _export_png(tensor, mode)  # type: ignore[arg-type]


def union_glyphs(glyphs: object) -> object:
    """Lazy import wrapper for union_glyphs (requires shapely + geometry extras)."""
    from aerocloud.export.boolean_union import union_glyphs as _union_glyphs

    return _union_glyphs(glyphs)  # type: ignore[arg-type]
