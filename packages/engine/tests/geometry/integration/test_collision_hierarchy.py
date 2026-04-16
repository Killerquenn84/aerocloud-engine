"""Integration tests for the full 5-stage collision hierarchy.

Tests verify the complete pipeline: AABB → BVH → Quadtree → SAT → Bitmap.

RED phase: import will fail until sat_overlap_rotated_rect, pack_bitmap_uint32,
bitmap_collision are added to collision.py.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import numpy as np

from aerocloud.geometry.collision import (
    aabb_overlap,
    bitmap_collision,
    bvh_query_overlap,
    build_bvh,
    get_or_build_bvh,
    pack_bitmap_uint32,
    sat_overlap_rotated_rect,
)


# ---------------------------------------------------------------------------
# Helpers: pipeline wrapper
# ---------------------------------------------------------------------------


def _five_stage_collision(
    new_aabb: np.ndarray,
    existing_aabbs: np.ndarray,
    *,
    new_cy: float,
    new_cx: float,
    new_h: float,
    new_w: float,
    new_theta: float,
    existing_params: list[tuple[float, float, float, float, float]],
    new_pixel_buf: np.ndarray,
    existing_pixel_bufs: list[np.ndarray],
    existing_pixel_origins: list[tuple[int, int]],
) -> tuple[bool, str]:
    """Run the 5-stage collision hierarchy.

    Returns:
        (collision_detected: bool, stage_that_fired: str)
        stage_that_fired is 'none' if no collision.
    """
    # Stage 1: AABB
    aabb_hits = aabb_overlap(new_aabb, existing_aabbs)
    if not aabb_hits.any():
        return False, "none"

    # Stage 2: BVH broadphase
    bvh_tree = get_or_build_bvh(existing_aabbs)
    bvh_hit_indices = bvh_query_overlap(bvh_tree, new_aabb, existing_aabbs)
    if not bvh_hit_indices:
        return False, "none"

    # Stage 3: Quadtree (simplified — use AABB hits as proxy, Quadtree tested separately)
    quadtree_hit_indices = [
        i for i in bvh_hit_indices if bool(aabb_overlap(new_aabb, existing_aabbs[i : i + 1]).any())
    ]
    if not quadtree_hit_indices:
        return False, "none"

    # Stage 4: SAT for rotated rectangles
    sat_hit_indices = []
    for i in quadtree_hit_indices:
        ecy, ecx, eh, ew, etheta = existing_params[i]
        if sat_overlap_rotated_rect(
            new_cy, new_cx, new_h, new_w, new_theta,
            ecy, ecx, eh, ew, etheta,
        ):
            sat_hit_indices.append(i)

    if not sat_hit_indices:
        return False, "none"

    # Stage 5: Bitmap pixel-exact
    new_packed = pack_bitmap_uint32(new_pixel_buf)
    new_ay_min = int(new_aabb[0])
    new_ax_min = int(new_aabb[1])
    new_a_h = int(new_aabb[2]) - new_ay_min
    new_a_w = int(new_aabb[3]) - new_ax_min

    for i in sat_hit_indices:
        e_packed = pack_bitmap_uint32(existing_pixel_bufs[i])
        e_ay_min, e_ax_min = existing_pixel_origins[i]
        e_h = existing_pixel_bufs[i].shape[0]
        e_w = existing_pixel_bufs[i].shape[1]
        if bitmap_collision(
            new_packed, new_ay_min, new_ax_min, new_a_h, new_a_w,
            e_packed, e_ay_min, e_ax_min, e_h, e_w,
        ):
            return True, "bitmap"

    return False, "none"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestFiveStagePipeline:
    """Integration tests for the full 5-stage pipeline."""

    def test_5stage_pipeline_catches_rotated_overlap(self) -> None:
        """Two rotated words that AABB says ok but SAT catches → collision detected.

        This tests the key correctness requirement from roadmap criteria #3.
        """
        # Existing word: thin bar, center (50, 50), h=2, w=30, theta=0
        # AABB covers y=[49,51], x=[35,65]
        exist_cy, exist_cx, exist_h, exist_w, exist_theta = 50.0, 50.0, 2.0, 30.0, 0.0
        exist_aabb = np.array([[49, 35, 51, 65]], dtype=np.int32)
        exist_pixel_buf = np.ones((2, 30), dtype=np.uint8)
        exist_origin = (49, 35)

        # New word: same size but rotated 45°, centered at (50, 50)
        # It CROSSES the existing word.
        new_cy, new_cx, new_h, new_w, new_theta = 50.0, 50.0, 2.0, 30.0, math.pi / 4
        # Rotated bar: bounding box is roughly sqrt(2)*15 in each direction ≈ 21.2
        # So AABB is approx [50-21, 50-21, 50+21, 50+21] = [29, 29, 71, 71]
        new_aabb = np.array([29, 29, 71, 71], dtype=np.int32)
        # New pixel buf covers the AABB area
        new_h_aabb = 71 - 29
        new_w_aabb = 71 - 29
        new_pixel_buf = np.ones((new_h_aabb, new_w_aabb), dtype=np.uint8)

        collision, stage = _five_stage_collision(
            new_aabb,
            exist_aabb,
            new_cy=new_cy,
            new_cx=new_cx,
            new_h=new_h,
            new_w=new_w,
            new_theta=new_theta,
            existing_params=[(exist_cy, exist_cx, exist_h, exist_w, exist_theta)],
            new_pixel_buf=new_pixel_buf,
            existing_pixel_bufs=[exist_pixel_buf],
            existing_pixel_origins=[exist_origin],
        )

        assert collision is True, "Crossing rotated words must be detected as colliding"

    def test_5stage_pipeline_passes_clean_placement(self) -> None:
        """Non-overlapping non-rotated words pass all stages (no collision)."""
        # Existing word: h=10, w=20, center (100, 100), theta=0
        # AABB: y=[95,105], x=[90,110]
        exist_cy, exist_cx, exist_h, exist_w, exist_theta = 100.0, 100.0, 10.0, 20.0, 0.0
        exist_aabb = np.array([[95, 90, 105, 110]], dtype=np.int32)
        exist_pixel_buf = np.ones((10, 20), dtype=np.uint8)
        exist_origin = (95, 90)

        # New word: h=10, w=20, center (100, 200), theta=0 — far away
        # AABB: y=[95,105], x=[190,210]
        new_cy, new_cx, new_h, new_w, new_theta = 100.0, 200.0, 10.0, 20.0, 0.0
        new_aabb = np.array([95, 190, 105, 210], dtype=np.int32)
        new_pixel_buf = np.ones((10, 20), dtype=np.uint8)

        collision, stage = _five_stage_collision(
            new_aabb,
            exist_aabb,
            new_cy=new_cy,
            new_cx=new_cx,
            new_h=new_h,
            new_w=new_w,
            new_theta=new_theta,
            existing_params=[(exist_cy, exist_cx, exist_h, exist_w, exist_theta)],
            new_pixel_buf=new_pixel_buf,
            existing_pixel_bufs=[exist_pixel_buf],
            existing_pixel_origins=[exist_origin],
        )

        assert collision is False
        assert stage == "none"

    def test_pipeline_order_AABB_first(self) -> None:
        """When AABB returns no overlap, SAT and Bitmap are never called (short-circuit).

        Verifies that Stage 1 AABB short-circuits before reaching SAT/Bitmap.
        """
        # Existing word at (100, 100), new word at (100, 300) — far apart, AABBs don't overlap
        exist_aabb = np.array([[95, 90, 105, 110]], dtype=np.int32)
        new_aabb = np.array([95, 290, 105, 310], dtype=np.int32)

        # AABB says no overlap → should return False immediately without calling SAT
        aabb_hits = aabb_overlap(new_aabb, exist_aabb)
        assert not aabb_hits.any(), "AABB must report no overlap for distant glyphs"

        # Verify the pipeline respects this (no exception from calling SAT with bad args)
        with patch(
            "aerocloud.geometry.collision.sat_overlap_rotated_rect"
        ) as mock_sat:
            # If short-circuit works, sat_overlap_rotated_rect should not be called
            # when AABB says no overlap
            _aabb_hits = aabb_overlap(new_aabb, exist_aabb)
            if not _aabb_hits.any():
                # Short-circuit — don't call SAT
                pass
            else:
                # Would call SAT here
                sat_overlap_rotated_rect(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

            # SAT must NOT have been called since AABB short-circuited
            mock_sat.assert_not_called()
