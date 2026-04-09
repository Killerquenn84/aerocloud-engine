"""aerocloud.geometry — Phase 4 Geometry-v1 public package.

On import this module enforces the FreeType 2.13.2 runtime pin (ADR-0006 /
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

_EXPECTED_FREETYPE: Final[str] = "2.13.2"


def _assert_freetype() -> None:
    """Enforce D-28 / ADR-0006 at import time.

    Calls ``PIL.features.version("freetype2")`` (the documented check per
    ADR-0006; NOT ``freetype.__version__`` which reads the Python binding
    version, NOT the native library version — Codex g-4 finding).

    Raises:
        GeometryEnvironmentError: If the runtime FreeType version differs from
            the pinned 2.13.2 (e.g., Homebrew Pillow ships 2.14.2, this
            server may have 2.14.3). Homebrew Pillow is explicitly unsupported
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
]
