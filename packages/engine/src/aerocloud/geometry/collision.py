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

Phase 7 extensions (D-05, D-07, D-11):
    - Stage 2 BVH broadphase: build_bvh, bvh_query_overlap, get_or_build_bvh
    - BVH LRU cache: blake3 key + cachetools.LRUCache + RLock (mirrors sdf_cache.py)
"""

from __future__ import annotations

import contextlib
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
