"""Unit tests for aerocloud.geometry.quadtree.

Tests for:
  - build_quadtree(): create empty QuadtreeNode covering given bounds
  - insert_aabb(): insert AABB into quadtree
  - query_region(): return indices of AABBs overlapping query region

RED phase: import will fail until quadtree.py is created.
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.geometry.quadtree import (
    QuadtreeNode,
    build_quadtree,
    insert_aabb,
    query_region,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def box(*args: int) -> np.ndarray:
    """Build a shape-(4,) int32 AABB: y_min, x_min, y_max, x_max."""
    return np.array(args, dtype=np.int32)


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


def test_build_quadtree_empty() -> None:
    """Empty bounds -> QuadtreeNode with no items and no children."""
    canvas_bounds = (0, 0, 100, 100)  # y0, x0, y1, x1
    node = build_quadtree(canvas_bounds)
    assert isinstance(node, QuadtreeNode)
    assert len(node.items) == 0
    assert node.children is None


# ---------------------------------------------------------------------------
# Insert tests
# ---------------------------------------------------------------------------


def test_insert_single_aabb() -> None:
    """Insert one AABB -> found when querying full canvas region."""
    canvas_bounds = (0, 0, 100, 100)
    node = build_quadtree(canvas_bounds)
    aabb = box(10, 10, 20, 20)
    insert_aabb(node, 0, aabb)

    # Query the full canvas should return index 0
    full_region = box(0, 0, 100, 100)
    result = query_region(node, full_region)
    assert 0 in result


def test_query_region_returns_overlapping() -> None:
    """Insert 10 AABBs, query sub-region -> only overlapping indices returned."""
    canvas_bounds = (0, 0, 200, 200)
    node = build_quadtree(canvas_bounds)

    # Insert 10 AABBs spread across the canvas
    for i in range(10):
        y0 = i * 15
        aabb = box(y0, 0, y0 + 10, 10)
        insert_aabb(node, i, aabb)

    # Query a narrow region that should only overlap first few
    query = box(0, 0, 25, 10)  # y from 0 to 25 -> overlaps indices 0 (0-10) and 1 (15-25)
    result = query_region(node, query)

    assert 0 in result  # box(0,0,10,10) overlaps query
    assert 1 in result  # box(15,0,25,10) overlaps query


def test_query_region_no_false_negatives() -> None:
    """All items in the query region must be returned (no misses)."""
    canvas_bounds = (0, 0, 500, 500)
    node = build_quadtree(canvas_bounds)

    rng = np.random.default_rng(7)
    n = 50
    y_mins = rng.integers(0, 400, n).astype(int)
    x_mins = rng.integers(0, 400, n).astype(int)
    heights = rng.integers(5, 40, n).astype(int)
    widths = rng.integers(5, 40, n).astype(int)

    aabbs = []
    for i in range(n):
        ab = box(int(y_mins[i]), int(x_mins[i]),
                 int(y_mins[i] + heights[i]), int(x_mins[i] + widths[i]))
        aabbs.append(ab)
        insert_aabb(node, i, ab)

    query = box(100, 100, 300, 300)

    # Brute-force expected set
    expected = set()
    qy0, qx0, qy1, qx1 = int(query[0]), int(query[1]), int(query[2]), int(query[3])
    for i, ab in enumerate(aabbs):
        ay0, ax0, ay1, ax1 = int(ab[0]), int(ab[1]), int(ab[2]), int(ab[3])
        if ay0 < qy1 and qy0 < ay1 and ax0 < qx1 and qx0 < ax1:
            expected.add(i)

    result = set(query_region(node, query))
    missing = expected - result
    assert not missing, f"Quadtree missed {len(missing)} items: {missing}"


# ---------------------------------------------------------------------------
# Max depth / stress tests
# ---------------------------------------------------------------------------


def test_max_depth_prevents_infinite_split() -> None:
    """1000 identical AABBs inserted -> no RecursionError."""
    canvas_bounds = (0, 0, 1000, 1000)
    node = build_quadtree(canvas_bounds, max_depth=8, split_threshold=8)
    aabb = box(100, 100, 200, 200)  # same AABB for all

    try:
        for i in range(1000):
            insert_aabb(node, i, aabb, max_depth=8, split_threshold=8)
    except RecursionError:  # pragma: no cover
        pytest.fail("insert_aabb raised RecursionError on 1000 identical AABBs")


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


def test_quadtree_deterministic() -> None:
    """Same AABBs inserted in same order -> same query results."""
    canvas_bounds = (0, 0, 200, 200)

    def build_and_query() -> list[int]:
        node = build_quadtree(canvas_bounds)
        aabbs = [
            box(0, 0, 20, 20),
            box(50, 50, 70, 70),
            box(100, 0, 120, 20),
            box(0, 100, 20, 120),
        ]
        for i, ab in enumerate(aabbs):
            insert_aabb(node, i, ab)
        query = box(0, 0, 200, 200)
        return sorted(query_region(node, query))

    r1 = build_and_query()
    r2 = build_and_query()
    assert r1 == r2
