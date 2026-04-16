"""aerocloud.geometry — Phase 4 Geometry-v1 public package.

On import this module enforces the FreeType 2.14.3 runtime pin (ADR-0006 v2 /
D-28). If the pin fails the whole geometry package refuses to load and callers
get a GeometryEnvironmentError with a documented remediation path.

Sign convention: sdf > 0 inside, sdf == 0 on boundary, sdf < 0 outside (ADR-0004).
Coordinate system: (y, x) canonical internally, (x, y) only at Pydantic boundary
(ADR-0005). Boundary adapters: ``xy_to_yx`` and ``yx_to_xy``.
"""

from __future__ import annotations

from typing import Final

from PIL import features

from aerocloud.geometry.errors import (
    EmptyMaskError,
    GeometryEnvironmentError,
    GeometryError,
    MaskFormatError,
    PlacementFailedError,
)

_EXPECTED_FREETYPE: Final[str] = "2.14.3"


def _assert_freetype() -> None:
    """Enforce D-28 / ADR-0006 v2 at import time.

    Calls ``PIL.features.version("freetype2")`` (the documented check per
    ADR-0006; NOT ``freetype.__version__`` which reads the Python binding
    version, NOT the native library version — Codex g-4 finding).

    Pin updated from 2.13.2 to 2.14.3 in Wave 5 3-KI review (2026-04-09)
    to align ADR, runtime, and golden corpus fixtures on one version.
    The AEROCLOUD_SKIP_FREETYPE_CHECK bypass has been removed — it was a
    transitional measure that is no longer needed. See ADR-0006 v2.

    Raises:
        GeometryEnvironmentError: If the runtime FreeType version differs from
            the pinned 2.14.3. Homebrew Pillow is explicitly unsupported
            for geometry generation. Use the pinned Docker image or the
            uv-pinned wheel. See ADR-0006.
    """
    actual = features.version("freetype2")
    if actual != _EXPECTED_FREETYPE:
        raise GeometryEnvironmentError(
            f"FreeType version mismatch: expected {_EXPECTED_FREETYPE!r}, "
            f"got {actual!r}. "
            "macOS Homebrew Pillow is NOT supported for geometry generation; "
            "use the pinned Docker image or the uv-pinned wheel. "
            "See ADR-0006."
        )


def xy_to_yx(point: tuple[int, int]) -> tuple[int, int]:
    """Convert a Pillow-style (x, y) tuple to numpy-native (y, x) (D-15).

    Used at the Pydantic boundary to translate user-facing (x, y) coordinates
    into the canonical internal (y, x) ordering (D-14 / ADR-0005).

    Args:
        point: An ``(x, y)`` tuple in Pillow/screen convention.

    Returns:
        ``(y, x)`` tuple in numpy row-major canonical order.
    """
    x, y = point
    return int(y), int(x)


def yx_to_xy(point: tuple[int, int]) -> tuple[int, int]:
    """Convert numpy-native (y, x) back to Pillow-style (x, y) (D-15).

    Used at the Pydantic boundary to translate internal (y, x) coordinates
    back to user-facing (x, y) ordering (D-14 / ADR-0005).

    Args:
        point: A ``(y, x)`` tuple in numpy row-major canonical order.

    Returns:
        ``(x, y)`` tuple in Pillow/screen convention.
    """
    y, x = point
    return int(x), int(y)


# Enforce the FreeType pin at import time. Subsequent imports are cached by
# the interpreter, so there is no per-call overhead after the first import.
# On non-pinned environments (e.g., Homebrew macOS, this server with 2.14.3),
# this raises GeometryEnvironmentError immediately.
_assert_freetype()

__all__ = [
    "_EXPECTED_FREETYPE",
    "EmptyMaskError",
    "GeometryEnvironmentError",
    "GeometryError",
    "MaskFormatError",
    "PlacementFailedError",
    "_assert_freetype",
    "xy_to_yx",
    "yx_to_xy",
    # Phase 7 MAT exports
    "extract_mat",
    "MATResult",
    "MATBranch",
    "get_or_build_mat",
    # Phase 7 BVH exports (GEO2-04, GEO2-08)
    "BVHNode",
    "build_bvh",
    "bvh_query_overlap",
    "get_or_build_bvh",
    # Phase 7 Quadtree exports (GEO2-05)
    "QuadtreeNode",
    "build_quadtree",
    "insert_aabb",
    "query_region",
    # Phase 7 SAT + Bitmap exports (GEO2-06, GEO2-07)
    "sat_overlap_rotated_rect",
    "pack_bitmap_uint32",
    "bitmap_collision",
    # Phase 7 Bezier exports (GEO2-09)
    "BezierCurve",
    "BezierGlyph",
    "glyph_to_bezier",
]


# Phase 7: MAT skeleton extraction + cache
from aerocloud.geometry.mat import MATBranch, MATResult, extract_mat  # noqa: E402
from aerocloud.geometry.mat_cache import get_or_build_mat  # noqa: E402

# Phase 7: BVH broadphase collision + SAT + Bitmap (GEO2-04, GEO2-06, GEO2-07, GEO2-08)
from aerocloud.geometry.collision import (  # noqa: E402
    BVHNode,
    bitmap_collision,
    build_bvh,
    bvh_query_overlap,
    get_or_build_bvh,
    pack_bitmap_uint32,
    sat_overlap_rotated_rect,
)

# Phase 7: Quadtree spatial index (GEO2-05)
from aerocloud.geometry.quadtree import (  # noqa: E402
    QuadtreeNode,
    build_quadtree,
    insert_aabb,
    query_region,
)

# Phase 7: Bezier path representation (GEO2-09)
from aerocloud.geometry.bezier import BezierCurve, BezierGlyph, glyph_to_bezier  # noqa: E402
