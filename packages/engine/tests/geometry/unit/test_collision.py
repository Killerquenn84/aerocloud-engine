"""Unit tests for geometry/collision.py — vectorized integer AABB overlap.

Test IDs: CL1..CL8 (from 04-05-PLAN.md Task 1 behavior spec).

Half-open interval semantics:
  Box covers rows [y_min, y_max) and cols [x_min, x_max).
  Adjacent boxes do NOT overlap.

RED phase: these tests are written BEFORE collision.py exists — they will fail.
"""

from __future__ import annotations

import numpy as np

from aerocloud.geometry.collision import aabb_overlap, has_any_collision

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
# CL1 — empty existing array → returns bool[0]
# ---------------------------------------------------------------------------

def test_cl1_empty_existing() -> None:
    new = box(0, 0, 4, 4)
    existing = np.zeros((0, 4), dtype=np.int32)
    result = aabb_overlap(new, existing)
    assert result.dtype == bool
    assert result.shape == (0,)
    assert list(result) == []


# ---------------------------------------------------------------------------
# CL2 — non-overlapping boxes (completely separate in both axes) → all False
# ---------------------------------------------------------------------------

def test_cl2_non_overlapping() -> None:
    new = box(0, 0, 4, 4)
    existing = boxes(
        (10, 10, 14, 14),  # far away
        (0, 10, 4, 14),    # same y-range, different x
        (10, 0, 14, 4),    # same x-range, different y
    )
    result = aabb_overlap(new, existing)
    assert result.shape == (3,)
    assert not result.any()


# ---------------------------------------------------------------------------
# CL3 — touching boxes (adjacent — half-open means NO overlap)
# ---------------------------------------------------------------------------

def test_cl3_touching_adjacent_no_overlap() -> None:
    """Adjacent boxes: new=[0,0,4,4), existing=[4,0,8,4) — share edge at y=4."""
    new = box(0, 0, 4, 4)
    existing = boxes(
        (4, 0, 8, 4),   # touches new's bottom edge: new.y_max == existing.y_min
        (0, 4, 4, 8),   # touches new's right edge: new.x_max == existing.x_min
    )
    result = aabb_overlap(new, existing)
    assert result.shape == (2,)
    assert not result.any(), f"Adjacent boxes must NOT overlap, got {result}"


# ---------------------------------------------------------------------------
# CL4 — fully-contained box → True
# ---------------------------------------------------------------------------

def test_cl4_fully_contained() -> None:
    new = box(0, 0, 10, 10)
    existing = boxes(
        (2, 2, 6, 6),    # fully inside new
        (20, 20, 30, 30),  # far outside
    )
    result = aabb_overlap(new, existing)
    assert result.shape == (2,)
    assert result[0] is np.bool_(True)
    assert result[1] is np.bool_(False)


# ---------------------------------------------------------------------------
# CL5 — partial overlap on Y only → False (needs both axes to overlap)
# ---------------------------------------------------------------------------

def test_cl5_partial_y_only_no_overlap() -> None:
    """Same y interval, completely separate x interval → no overlap."""
    new = box(0, 0, 4, 4)
    existing = boxes((0, 10, 4, 14))  # y overlaps, x does not
    result = aabb_overlap(new, existing)
    assert not result[0]


# ---------------------------------------------------------------------------
# CL6 — partial overlap on X only → False
# ---------------------------------------------------------------------------

def test_cl6_partial_x_only_no_overlap() -> None:
    """Same x interval, completely separate y interval → no overlap."""
    new = box(0, 0, 4, 4)
    existing = boxes((10, 0, 14, 4))  # x overlaps, y does not
    result = aabb_overlap(new, existing)
    assert not result[0]


# ---------------------------------------------------------------------------
# CL7 — mix of 100 random boxes → has_any_collision agrees with aabb_overlap
# ---------------------------------------------------------------------------

def test_cl7_random_mix() -> None:
    rng = np.random.default_rng(0)
    new = box(20, 20, 40, 40)
    # Generate 100 random boxes; some will overlap with new, some will not.
    y_mins = rng.integers(0, 60, 100)
    x_mins = rng.integers(0, 60, 100)
    heights = rng.integers(2, 20, 100)
    widths = rng.integers(2, 20, 100)
    existing = np.column_stack([
        y_mins, x_mins, y_mins + heights, x_mins + widths
    ]).astype(np.int32)

    per_box = aabb_overlap(new, existing)
    any_collision = has_any_collision(new, existing)

    assert per_box.shape == (100,)
    assert any_collision == bool(per_box.any())


# ---------------------------------------------------------------------------
# CL8 — dtype: int32 and int64 inputs both accepted
# ---------------------------------------------------------------------------

def test_cl8_int32_and_int64_inputs() -> None:
    new_i32 = box(0, 0, 5, 5)  # int32
    new_i64 = new_i32.astype(np.int64)
    existing_i32 = boxes((1, 1, 3, 3))
    existing_i64 = existing_i32.astype(np.int64)

    # Both dtypes must work without raising
    r1 = aabb_overlap(new_i32, existing_i32)
    r2 = aabb_overlap(new_i64, existing_i64)
    r3 = aabb_overlap(new_i32, existing_i64)
    r4 = aabb_overlap(new_i64, existing_i32)

    # box [1,1,3,3) overlaps with [0,0,5,5) — should be True in all cases
    assert r1[0] and r2[0] and r3[0] and r4[0]
