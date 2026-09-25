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

Phase 7 extensions (D-05, D-07, D-09, D-10, D-11):
    - Stage 2 BVH broadphase: build_bvh, bvh_query_overlap, get_or_build_bvh
    - BVH LRU cache: blake3 key + cachetools.LRUCache + RLock (mirrors sdf_cache.py)
    - Stage 4 SAT: sat_overlap_rotated_rect (D-09 — hard reject, not differentiable)
    - Stage 5 Bitmap: pack_bitmap_uint32, bitmap_collision (D-10 — uint32 packing)
"""

from __future__ import annotations

import contextlib
import math
import threading
from typing import Any, Final, TypedDict

import numpy as np
from cachetools import LRUCache

try:
    from blake3 import blake3 as _blake3_hasher

    def _bvh_digest(data: bytes) -> str:
        """Compute a hex digest using blake3 (D-11 / D-21)."""
        return str(_blake3_hasher(data).hexdigest())

except ImportError:  # pragma: no cover — sha256 fallback
    from hashlib import sha256 as _sha256_hasher

    def _bvh_digest(data: bytes) -> str:
        """Compute a hex digest using sha256 (D-21 fallback)."""
        return _sha256_hasher(data).hexdigest()


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


# ---------------------------------------------------------------------------
# Phase 7: Stage 2 BVH broadphase (D-05, D-07, D-11)
# ---------------------------------------------------------------------------


class BVHNode(TypedDict):
    """A node in a Bounding Volume Hierarchy binary tree.

    Internal nodes have ``left`` and ``right`` children and ``indices=None``.
    Leaf nodes have ``left=None``, ``right=None`` and a non-empty ``indices``
    list that indexes into the original ``aabbs`` array passed to
    ``build_bvh``.

    Columns follow the canonical (y, x) ordering (D-14):
    ``aabb = (y_min, x_min, y_max, x_max)``.
    """

    aabb: np.ndarray  # shape (4,) int32 — merged AABB for this subtree
    left: BVHNode | None
    right: BVHNode | None
    indices: list[int] | None  # leaf only — indices into original aabbs


def build_bvh(
    aabbs: np.ndarray,
    depth: int = 0,
    max_depth: int = 20,
) -> BVHNode:
    """Build a BVH binary tree over ``aabbs``.

    Split heuristic: longest axis, split at median centroid (EdWordle /
    RESEARCH.md Pattern 3). Base case: ``len(aabbs) <= 1`` OR
    ``depth >= max_depth`` → create a leaf node.

    Addresses T-07-02-01 (DoS via recursion): ``max_depth=20`` hard cap
    prevents unbounded recursion on degenerate input.

    Args:
        aabbs: Shape ``(N, 4)`` int32 AABB array. Columns: y_min, x_min,
            y_max, x_max (D-14). Must have at least one row.
        depth: Current recursion depth (internal — callers pass ``depth=0``).
        max_depth: Hard recursion cap. Nodes at this depth become leaves
            regardless of item count.

    Returns:
        Root ``BVHNode`` whose ``aabb`` covers all input AABBs.
    """
    merged = np.array(
        [
            int(aabbs[:, 0].min()),
            int(aabbs[:, 1].min()),
            int(aabbs[:, 2].max()),
            int(aabbs[:, 3].max()),
        ],
        dtype=np.int32,
    )

    # Base cases: single item or depth cap → leaf node
    if len(aabbs) <= 1 or depth >= max_depth:
        return {
            "aabb": merged,
            "left": None,
            "right": None,
            "indices": list(range(len(aabbs))),
        }

    # Longest-axis split heuristic
    height = int(merged[2]) - int(merged[0])
    width = int(merged[3]) - int(merged[1])
    if height >= width:
        centroids = (aabbs[:, 0].astype(np.float64) + aabbs[:, 2].astype(np.float64)) / 2.0
    else:
        centroids = (aabbs[:, 1].astype(np.float64) + aabbs[:, 3].astype(np.float64)) / 2.0

    mid = float(np.median(centroids))
    left_mask = centroids <= mid
    right_mask = ~left_mask

    # Degenerate split (all items on one side) → leaf to prevent infinite recursion
    if left_mask.sum() == 0 or right_mask.sum() == 0:
        return {
            "aabb": merged,
            "left": None,
            "right": None,
            "indices": list(range(len(aabbs))),
        }

    # Track original indices through the split
    all_indices = np.arange(len(aabbs), dtype=np.int64)

    def _remap(child_tree: BVHNode, original_indices: np.ndarray) -> BVHNode:
        """Re-map leaf indices back to the original aabbs coordinate space."""
        if child_tree["indices"] is not None:
            child_tree["indices"] = [int(original_indices[i]) for i in child_tree["indices"]]
        if child_tree["left"] is not None:
            _remap(child_tree["left"], original_indices)
        if child_tree["right"] is not None:
            _remap(child_tree["right"], original_indices)
        return child_tree

    left_indices = all_indices[left_mask]
    right_indices = all_indices[right_mask]

    left_child = build_bvh(aabbs[left_mask], depth + 1, max_depth)
    right_child = build_bvh(aabbs[right_mask], depth + 1, max_depth)

    # Remap child leaf indices to original coordinate space
    _remap(left_child, left_indices)
    _remap(right_child, right_indices)

    return {
        "aabb": merged,
        "left": left_child,
        "right": right_child,
        "indices": None,
    }


def _aabbs_overlap_half_open(a: np.ndarray, b: np.ndarray) -> bool:
    """Return True iff two (4,) AABBs overlap under half-open semantics."""
    ay0, ax0, ay1, ax1 = int(a[0]), int(a[1]), int(a[2]), int(a[3])
    by0, bx0, by1, bx1 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
    return ay0 < by1 and by0 < ay1 and ax0 < bx1 and bx0 < ax1


def bvh_query_overlap(
    tree: BVHNode,
    query_aabb: np.ndarray,
    aabbs: np.ndarray,
) -> list[int]:
    """Return indices of AABBs in ``aabbs`` that overlap ``query_aabb``.

    Recursive BVH traversal: prune subtrees whose merged AABB does not
    overlap the query. At leaf nodes, verify each stored index against
    ``aabbs`` using ``aabb_overlap`` (no false negatives guarantee).

    Args:
        tree: BVH tree built by ``build_bvh``.
        query_aabb: Shape ``(4,)`` int32 — ``(y_min, x_min, y_max, x_max)``.
        aabbs: The original ``(N, 4)`` int32 array passed to ``build_bvh``.

    Returns:
        List of integer indices into ``aabbs`` of overlapping items.
        May contain duplicates if the same index appears in multiple leaves
        (rare with correct BVH construction).
    """
    # Prune: if query does not overlap this node's bounding box, skip subtree
    if not _aabbs_overlap_half_open(query_aabb, tree["aabb"]):
        return []

    # Leaf node: verify each stored index against the original aabbs
    if tree["indices"] is not None:
        result: list[int] = []
        for idx in tree["indices"]:
            if _aabbs_overlap_half_open(query_aabb, aabbs[idx]):
                result.append(idx)
        return result

    # Internal node: recurse into children
    left_hits: list[int] = []
    right_hits: list[int] = []
    if tree["left"] is not None:
        left_hits = bvh_query_overlap(tree["left"], query_aabb, aabbs)
    if tree["right"] is not None:
        right_hits = bvh_query_overlap(tree["right"], query_aabb, aabbs)
    return left_hits + right_hits


# ---------------------------------------------------------------------------
# Phase 7: BVH LRU cache (D-11, T-07-02-02)
# ---------------------------------------------------------------------------

# Algorithm version salt — bump to invalidate all existing cache entries (D-11).
_BVH_ALGO_VERSION: Final[int] = 1

# Bytes budget for the BVH cache (mirrors sdf_cache.py D-18).
# BVH trees are small Python dicts; bound by entry count (maxsize=128 trees).
_BVH_CACHE: Any = LRUCache(maxsize=128)

# Module-level reentrant lock — guards ALL cache reads and writes (D-22 pattern).
_BVH_CACHE_LOCK: threading.RLock = threading.RLock()


def _make_bvh_key(aabbs: np.ndarray) -> tuple[Any, ...]:
    """Build a composite cache key for BVH (D-11, T-07-02-02).

    Includes blake3 digest + shape + algorithm version so that any change in
    content, word count, or algorithm version busts the cache.

    Args:
        aabbs: The ``(N, 4)`` int32 AABB array to key on.

    Returns:
        A 3-element tuple: ``(hex_digest, shape, ("bvh_algo_version", N))``.
    """
    return (
        _bvh_digest(aabbs.tobytes()),
        aabbs.shape,
        ("bvh_algo_version", _BVH_ALGO_VERSION),
    )


def get_or_build_bvh(aabbs: np.ndarray) -> BVHNode:
    """Return a cached BVH or build, cache, and return a new one.

    Thread-safe via double-checked locking (mirrors sdf_cache.py D-22).
    The lock is NOT held while ``build_bvh`` runs.

    Args:
        aabbs: Shape ``(N, 4)`` int32 AABB array — same as ``build_bvh``.

    Returns:
        A ``BVHNode`` tree rooted at the merged AABB of all inputs.
    """
    key = _make_bvh_key(aabbs)

    # Fast path: check under lock
    with _BVH_CACHE_LOCK:
        cached: BVHNode | None = _BVH_CACHE.get(key)
        if cached is not None:
            return cached

    # Slow path: build OUTSIDE the lock
    tree = build_bvh(aabbs)

    with _BVH_CACHE_LOCK:
        # Re-check in case a competing thread populated the entry
        existing: BVHNode | None = _BVH_CACHE.get(key)
        if existing is not None:
            return existing
        with contextlib.suppress(ValueError):
            _BVH_CACHE[key] = tree

    return tree


# ---------------------------------------------------------------------------
# Phase 7: Stage 4 SAT — Separating Axis Theorem for rotated rectangles (D-09)
# ---------------------------------------------------------------------------


def sat_overlap_rotated_rect(
    cy1: float,
    cx1: float,
    h1: float,
    w1: float,
    theta1: float,
    cy2: float,
    cx2: float,
    h2: float,
    w2: float,
    theta2: float,
) -> bool:
    """Return True iff two rotated rectangles overlap (SAT — Stage 4 collision).

    Coordinate convention: (y, x) per D-14. ``theta`` in radians, measured from
    the y-axis (rotation is counter-clockwise in image space). This function is
    purely a hard-reject predicate — it is NOT differentiable (D-09).

    The algorithm:
    1. Compute 4 corners for each rectangle by rotating local half-extents.
    2. Collect edge-normal axes from both rectangles (up to 4 unique axes total).
       Skip degenerate edges with length < 1e-10 (T-07-03-01 DoS mitigation).
    3. For each axis, project all 8 corners onto it and check if the intervals
       [min(proj_A), max(proj_A)] and [min(proj_B), max(proj_B)] have a gap.
    4. Any separating axis found → return False.
    5. No separating axis on any of the 4 axes → return True (overlap).

    Args:
        cy1: Y-center of rectangle 1.
        cx1: X-center of rectangle 1.
        h1: Height of rectangle 1 (extent along y-axis before rotation).
        w1: Width of rectangle 1 (extent along x-axis before rotation).
        theta1: Rotation angle of rectangle 1 in radians (counter-clockwise).
        cy2: Y-center of rectangle 2.
        cx2: X-center of rectangle 2.
        h2: Height of rectangle 2.
        w2: Width of rectangle 2.
        theta2: Rotation angle of rectangle 2 in radians.

    Returns:
        Python ``bool`` — ``True`` if the rectangles overlap or touch,
        ``False`` if a separating axis exists.
    """

    def _corners(cy: float, cx: float, h: float, w: float, theta: float) -> np.ndarray:
        """Compute the 4 corners of a rotated rectangle as a (4, 2) float64 array.

        Local coordinate frame: (y, x) with half-extents (h/2, w/2).
        Four local corners (before rotation):
            (-hh, -hw), (-hh, +hw), (+hh, +hw), (+hh, -hw)
        Rotation matrix (row-major, right-hand (y,x) space):
            [[cos, -sin], [sin, cos]]
        """
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        hh = h / 2.0
        hw = w / 2.0
        # Local corners: shape (4, 2) in (y, x) order
        local = np.array(
            [[-hh, -hw], [-hh, hw], [hh, hw], [hh, -hw]],
            dtype=np.float64,
        )
        # 2D rotation matrix in (y, x) convention
        rot = np.array([[cos_t, -sin_t], [sin_t, cos_t]], dtype=np.float64)
        # Apply rotation and translate to world coords
        return local @ rot.T + np.array([cy, cx], dtype=np.float64)

    def _edge_normal_axes(c: np.ndarray) -> list[np.ndarray]:
        """Return normalised edge-normal axes for a rectangle given its 4 corners.

        For a rectangle, only 2 unique edge directions exist (the other two are
        parallel). We compute all 4 edges and skip near-zero-length ones
        (degenerate case guard — T-07-03-01).

        Args:
            c: Shape (4, 2) array of corners.

        Returns:
            List of normalised (2,) float64 axis vectors (0-4 entries).
        """
        axes: list[np.ndarray] = []
        for i in range(4):
            edge = c[(i + 1) % 4] - c[i]
            n = float(np.linalg.norm(edge))
            if n > 1e-10:
                # Perpendicular to edge = normal axis
                axes.append(np.array([-edge[1], edge[0]], dtype=np.float64) / n)
        return axes

    c1 = _corners(cy1, cx1, h1, w1, theta1)
    c2 = _corners(cy2, cx2, h2, w2, theta2)

    for ax in _edge_normal_axes(c1) + _edge_normal_axes(c2):
        proj1: np.ndarray = c1 @ ax
        proj2: np.ndarray = c2 @ ax
        # Separating axis found if the projections don't overlap
        # Use strict inequality: if they merely touch (max(A) == min(B)),
        # we consider it a collision (touching = True per plan spec).
        if float(proj1.max()) < float(proj2.min()) or float(proj2.max()) < float(proj1.min()):
            return False  # separating axis found → no collision

    return True  # no separating axis found → overlap


# ---------------------------------------------------------------------------
# Phase 7: Stage 5 Bitmap — uint32 pixel-exact collision (D-10)
# ---------------------------------------------------------------------------


def pack_bitmap_uint32(pixel_buffer: np.ndarray) -> np.ndarray:
    """Pack a (H, W) uint8 pixel buffer into a (H, ceil(W/32)) uint32 bitmask.

    Encoding: pixel column ``col`` is placed in word ``col // 32``, at bit
    position ``31 - (col % 32)`` — i.e., MSB-first (leftmost pixel = highest bit).
    This convention ensures that two packed rows can be compared with bitwise AND
    after alignment-correcting bit shifts.

    Args:
        pixel_buffer: Shape ``(H, W)`` uint8 array. Any pixel ``> 0`` is treated
            as ink; zero pixels are transparent.

    Returns:
        Shape ``(H, ceil(W/32))`` uint32 ndarray where each bit represents one pixel.
    """
    h, w = pixel_buffer.shape
    w32 = (w + 31) // 32
    packed = np.zeros((h, w32), dtype=np.uint32)
    ink = (pixel_buffer > 0).astype(np.uint32)

    for col in range(w):
        word_idx = col // 32
        bit_idx = 31 - (col % 32)
        packed[:, word_idx] |= ink[:, col] << np.uint32(bit_idx)

    return packed


def bitmap_collision(
    packed_a: np.ndarray,
    ay_min: int,
    ax_min: int,
    a_h: int,
    a_w: int,
    packed_b: np.ndarray,
    by_min: int,
    bx_min: int,
    b_h: int,
    b_w: int,
) -> bool:
    """Return True iff two packed-bitmap glyphs have any pixel-exact overlap.

    Computes the intersection region in pixel space, then checks for overlapping
    ink using uint32 bitwise AND with bit-shift alignment correction.

    The CRITICAL implementation detail (RESEARCH.md Pitfall 3 / D-10):
    When two glyphs have different ``ax_min % 32`` values, their uint32 word
    boundaries do not align. A naive AND without shifting produces false
    negatives. This implementation computes:

        ``bit_shift = (ax_min % 32) - (bx_min % 32)``

    and shifts the appropriate packed row before the AND:
    - ``bit_shift > 0``: shift B's extracted words RIGHT by ``bit_shift``
    - ``bit_shift < 0``: shift A's extracted words RIGHT by ``-bit_shift``
    - ``bit_shift == 0``: no shift needed (32-pixel-aligned pair)

    Args:
        packed_a: Shape ``(H_a, ceil(W_a/32))`` uint32 — glyph A's packed bitmap.
        ay_min: Top pixel row of glyph A in canvas coordinates.
        ax_min: Left pixel column of glyph A in canvas coordinates.
        a_h: Height of glyph A in pixels.
        a_w: Width of glyph A in pixels.
        packed_b: Shape ``(H_b, ceil(W_b/32))`` uint32 — glyph B's packed bitmap.
        by_min: Top pixel row of glyph B in canvas coordinates.
        bx_min: Left pixel column of glyph B in canvas coordinates.
        b_h: Height of glyph B in pixels.
        b_w: Width of glyph B in pixels.

    Returns:
        Python ``bool`` — ``True`` if at least one pixel position has ink in
        both glyphs simultaneously (pixel-exact overlap).
    """
    # Compute intersection rectangle in global pixel coordinates
    oy0 = max(ay_min, by_min)
    ox0 = max(ax_min, bx_min)
    oy1 = min(ay_min + a_h, by_min + b_h)
    ox1 = min(ax_min + a_w, bx_min + b_w)

    if oy0 >= oy1 or ox0 >= ox1:
        return False  # no geometric overlap

    # Bit-shift alignment (Pitfall 3 / D-10):
    # shift_a = which bit in A's first word corresponds to global pixel ox0
    # shift_b = which bit in B's first word corresponds to global pixel ox0
    # net bit_shift corrects for misaligned 32-pixel word boundaries
    bit_shift = (ax_min % 32) - (bx_min % 32)

    # Width of overlap region in pixels
    overlap_w = ox1 - ox0

    # Overlap region local coordinates within each glyph's packed array
    # For glyph A: local x range = [ox0 - ax_min, ox1 - ax_min)
    a_local_x0 = ox0 - ax_min
    a_local_x1 = ox1 - ax_min
    # For glyph B: local x range = [ox0 - bx_min, ox1 - bx_min)
    b_local_x0 = ox0 - bx_min
    b_local_x1 = ox1 - bx_min  # noqa: F841 — kept for documentation clarity

    # Word-index ranges (inclusive start, exclusive end rounded up)
    a_word0 = a_local_x0 // 32
    a_word1 = (a_local_x1 + 31) // 32
    b_word0 = b_local_x0 // 32
    b_word1 = (b_local_x0 + overlap_w + 31) // 32

    for y in range(oy0, oy1):
        row_a = packed_a[y - ay_min, a_word0:a_word1].astype(np.uint64)
        row_b = packed_b[y - by_min, b_word0:b_word1].astype(np.uint64)

        # Align B's bits to match A's bit positions by applying the net shift
        if bit_shift > 0:
            # A starts at a higher bit position → shift B right to align with A
            row_b_aligned = _shift_packed_row_right(row_b, bit_shift)
            # Truncate to A's length for AND
            min_len = min(len(row_a), len(row_b_aligned))
            if min_len > 0 and int(np.any(row_a[:min_len] & row_b_aligned[:min_len])):
                return True
        elif bit_shift < 0:
            # B starts at a higher bit position → shift A right to align with B
            row_a_aligned = _shift_packed_row_right(row_a, -bit_shift)
            min_len = min(len(row_a_aligned), len(row_b))
            if min_len > 0 and int(np.any(row_a_aligned[:min_len] & row_b[:min_len])):
                return True
        else:
            # No shift needed — directly AND the overlap words
            min_len = min(len(row_a), len(row_b))
            if min_len > 0 and int(np.any(row_a[:min_len] & row_b[:min_len])):
                return True

    return False


def _shift_packed_row_right(row: np.ndarray, shift: int) -> np.ndarray:
    """Shift a packed uint64 row right by ``shift`` bits across word boundaries.

    This implements a multi-word right shift: bits shifted out of the LSB of
    word[i] flow into the MSB of word[i+1]. This is required when two glyphs'
    uint32 word boundaries do not align (D-10 / Pitfall 3).

    Args:
        row: 1D uint64 array representing consecutive packed words.
        shift: Number of bits to shift right (0 ≤ shift < 64).

    Returns:
        1D uint64 array of the same length with bits shifted right by ``shift``.
    """
    if shift == 0 or len(row) == 0:
        return row.copy()

    result = np.zeros_like(row, dtype=np.uint64)
    carry_mask = np.uint64((1 << shift) - 1)
    shift_u64 = np.uint64(shift)
    carry_shift = np.uint64(64 - shift)

    for i in range(len(row)):
        result[i] = row[i] >> shift_u64
        if i > 0:
            # Carry bits from the previous word into the MSB of this word
            carry = (row[i - 1] & carry_mask) << carry_shift
            result[i] |= carry

    return result
