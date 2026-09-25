"""Unit tests for BVH collision functions in aerocloud.geometry.collision.

Tests for:
  - build_bvh(): construct BVH tree from (N, 4) int32 AABB array
  - bvh_query_overlap(): query BVH for overlapping AABBs
  - get_or_build_bvh(): LRU-cached BVH construction

RED phase: import will fail until build_bvh, bvh_query_overlap, get_or_build_bvh
are added to collision.py.
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.geometry.collision import (
    aabb_overlap,
    build_bvh,
    bvh_query_overlap,
    get_or_build_bvh,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def box(*args: int) -> np.ndarray:
    """Build a shape-(4,) int32 AABB: y_min, x_min, y_max, x_max."""
    return np.array(args, dtype=np.int32)


def boxes(*rows: tuple[int, int, int, int]) -> np.ndarray:
    """Build an (N, 4) int32 array from a sequence of (y0, x0, y1, x1) tuples."""
    return np.array(rows, dtype=np.int32)


# ---------------------------------------------------------------------------
# BVH construction tests
# ---------------------------------------------------------------------------


def test_build_bvh_single_aabb() -> None:
    """Single AABB -> leaf node: indices=[0], no children."""
    aabbs = boxes((0, 0, 10, 10))
    tree = build_bvh(aabbs)
    assert tree["indices"] is not None
    assert list(tree["indices"]) == [0]
    assert tree["left"] is None
    assert tree["right"] is None


def test_build_bvh_two_aabbs_splits() -> None:
    """Two well-separated AABBs -> root has left and right children."""
    aabbs = boxes(
        (0, 0, 10, 10),
        (100, 100, 110, 110),
    )
    tree = build_bvh(aabbs)
    # Root must have children (split must occur)
    assert tree["left"] is not None or tree["right"] is not None


def test_build_bvh_merged_aabb_covers_all() -> None:
    """Merged AABB at root must cover ALL input AABBs."""
    aabbs = boxes(
        (0, 0, 10, 10),
        (5, 5, 20, 20),
        (15, 0, 30, 15),
    )
    tree = build_bvh(aabbs)
    merged = tree["aabb"]
    # merged must contain all points
    assert int(merged[0]) <= 0   # y_min
    assert int(merged[1]) <= 0   # x_min
    assert int(merged[2]) >= 30  # y_max
    assert int(merged[3]) >= 20  # x_max


# ---------------------------------------------------------------------------
# BVH query tests
# ---------------------------------------------------------------------------


def test_bvh_query_overlap_finds_collision() -> None:
    """BVH query detects actual overlap that brute-force also detects."""
    aabbs = boxes(
        (0, 0, 10, 10),
        (20, 20, 30, 30),
        (40, 40, 50, 50),
    )
    tree = build_bvh(aabbs)
    query = box(5, 5, 15, 15)  # overlaps index 0
    result = bvh_query_overlap(tree, query, aabbs)
    assert 0 in result


def test_bvh_query_no_false_negatives() -> None:
    """BVH query must find all overlaps that brute-force aabb_overlap finds.

    No false negatives: every index returned by aabb_overlap must appear in
    bvh_query_overlap result.
    """
    rng = np.random.default_rng(42)
    y_mins = rng.integers(0, 80, 30).astype(np.int32)
    x_mins = rng.integers(0, 80, 30).astype(np.int32)
    heights = rng.integers(5, 25, 30).astype(np.int32)
    widths = rng.integers(5, 25, 30).astype(np.int32)
    aabbs = np.column_stack([y_mins, x_mins, y_mins + heights, x_mins + widths]).astype(np.int32)

    query = box(30, 30, 60, 60)
    brute_force = set(int(i) for i, v in enumerate(aabb_overlap(query, aabbs)) if v)
    tree = build_bvh(aabbs)
    bvh_result = set(bvh_query_overlap(tree, query, aabbs))

    # No false negatives: brute_force subset of bvh_result
    assert brute_force <= bvh_result, (
        f"BVH missed: {brute_force - bvh_result}"
    )


def test_bvh_query_returns_empty_for_no_collision() -> None:
    """Non-overlapping query AABB returns empty list."""
    aabbs = boxes(
        (0, 0, 10, 10),
        (20, 20, 30, 30),
    )
    tree = build_bvh(aabbs)
    # Query far away from all placed words
    query = box(100, 100, 110, 110)
    result = bvh_query_overlap(tree, query, aabbs)
    assert result == []


def test_bvh_max_depth_terminates() -> None:
    """1000 random AABBs -> build_bvh completes without RecursionError."""
    rng = np.random.default_rng(0)
    y_mins = rng.integers(0, 500, 1000).astype(np.int32)
    x_mins = rng.integers(0, 500, 1000).astype(np.int32)
    heights = rng.integers(5, 30, 1000).astype(np.int32)
    widths = rng.integers(5, 30, 1000).astype(np.int32)
    aabbs = np.column_stack([y_mins, x_mins, y_mins + heights, x_mins + widths]).astype(np.int32)

    try:
        tree = build_bvh(aabbs)
    except RecursionError:  # pragma: no cover
        pytest.fail("build_bvh raised RecursionError on 1000 random AABBs")

    assert tree is not None
    assert tree["aabb"].shape == (4,)


# ---------------------------------------------------------------------------
# BVH cache tests
# ---------------------------------------------------------------------------


def test_get_or_build_bvh_cache_hit() -> None:
    """Same aabbs array called twice: second call returns cached tree."""
    aabbs = boxes(
        (0, 0, 10, 10),
        (20, 20, 30, 30),
        (40, 40, 50, 50),
    )
    tree1 = get_or_build_bvh(aabbs)
    tree2 = get_or_build_bvh(aabbs)
    # Cache hit: same object (identity) or structurally identical root AABB
    assert np.array_equal(tree1["aabb"], tree2["aabb"])


def test_get_or_build_bvh_cache_miss_on_change() -> None:
    """Different aabbs content -> different tree (cache miss)."""
    aabbs_a = boxes(
        (0, 0, 10, 10),
        (20, 20, 30, 30),
    )
    aabbs_b = boxes(
        (50, 50, 60, 60),
        (70, 70, 80, 80),
    )
    tree_a = get_or_build_bvh(aabbs_a)
    tree_b = get_or_build_bvh(aabbs_b)
    # Different content -> different merged root AABB
    assert not np.array_equal(tree_a["aabb"], tree_b["aabb"])
