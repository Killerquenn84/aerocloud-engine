"""Vectorized integer AABB collision (D-35..D-37).

Axis-aligned only. Half-open intervals: [y_min, y_max) x [x_min, x_max).
Integer arithmetic only — no FP comparisons, no rotation (rotation deferred
to Phase 7 Geometry-v2).

References:
    - D-35: Stage-1 AABB collision; numpy (N, 4) int32 hot-loop array.
    - D-36: Vectorized ``aabb_overlap`` signature.
    - D-37: Axis-aligned only, no rotation in v1.
    - D-14: (y, x) ordering; columns are (y_min, x_min, y_max, x_max).
    - D-16: Half-open intervals — adjacent boxes do NOT overlap.
"""

from __future__ import annotations

import numpy as np


def aabb_overlap(new: np.ndarray, existing: np.ndarray) -> np.ndarray:
    """Return bool[N] mask of which existing AABBs overlap ``new``.

    Half-open semantics: box covers pixels in [y_min, y_max) x [x_min, x_max).
    Two adjacent boxes that share only an edge do NOT overlap.

    Args:
        new: Shape ``(4,)`` integer array — ``(y_min, x_min, y_max, x_max)``.
        existing: Shape ``(N, 4)`` integer array, same column ordering.

    Returns:
        Boolean ndarray of length ``N``. ``True`` means the corresponding
        existing box overlaps ``new``.
    """
    if existing.shape[0] == 0:
        return np.zeros(0, dtype=bool)

    # Cast to int64 to avoid any signed-overflow edge cases with large coords.
    ny0, nx0, ny1, nx1 = new.astype(np.int64, copy=False)
    ey0 = existing[:, 0].astype(np.int64, copy=False)
    ex0 = existing[:, 1].astype(np.int64, copy=False)
    ey1 = existing[:, 2].astype(np.int64, copy=False)
    ex1 = existing[:, 3].astype(np.int64, copy=False)

    # Two half-open intervals [a, b) and [c, d) overlap iff a < d AND c < b.
    overlap_y: np.ndarray = (ey0 < ny1) & (ny0 < ey1)
    overlap_x: np.ndarray = (ex0 < nx1) & (nx0 < ex1)
    return np.asarray(overlap_y & overlap_x, dtype=bool)


def has_any_collision(new: np.ndarray, existing: np.ndarray) -> bool:
    """Return ``True`` iff ``new`` overlaps at least one entry in ``existing``.

    Convenience reducer on top of ``aabb_overlap``.

    Args:
        new: Shape ``(4,)`` integer array — ``(y_min, x_min, y_max, x_max)``.
        existing: Shape ``(N, 4)`` integer array, same column ordering.

    Returns:
        Python ``bool`` — ``True`` if any collision exists.
    """
    return bool(aabb_overlap(new, existing).any())
