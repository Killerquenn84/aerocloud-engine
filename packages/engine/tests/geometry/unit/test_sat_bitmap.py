"""Unit tests for SAT rotated-rectangle collision and Bitmap pixel-exact collision.

Tests for:
  - sat_overlap_rotated_rect(): SAT collision for rotated rectangles (Stage 4)
  - pack_bitmap_uint32(): pack (H, W) uint8 pixel buffer into (H, ceil(W/32)) uint32
  - bitmap_collision(): pixel-exact collision via uint32 AND (Stage 5)

RED phase: import will fail until sat_overlap_rotated_rect, pack_bitmap_uint32,
bitmap_collision are added to collision.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from aerocloud.geometry.collision import (
    aabb_overlap,
    bitmap_collision,
    pack_bitmap_uint32,
    sat_overlap_rotated_rect,
)


# ---------------------------------------------------------------------------
# SAT tests
# ---------------------------------------------------------------------------


class TestSatAlignedRects:
    """Tests for axis-aligned rectangles (theta=0)."""

    def test_sat_aligned_rects_overlap(self) -> None:
        """Two axis-aligned overlapping rects (theta=0) → True."""
        # rect 1: center (10, 10), h=6, w=6
        # rect 2: center (12, 12), h=6, w=6
        # overlap region is 4x4
        assert sat_overlap_rotated_rect(10, 10, 6, 6, 0.0, 12, 12, 6, 6, 0.0) is True

    def test_sat_aligned_rects_no_overlap(self) -> None:
        """Two separated axis-aligned rects → False."""
        # rect 1: center (10, 10), h=4, w=4 → covers y [8,12), x [8,12)
        # rect 2: center (10, 20), h=4, w=4 → covers y [8,12), x [18,22)
        assert sat_overlap_rotated_rect(10, 10, 4, 4, 0.0, 10, 20, 4, 4, 0.0) is False

    def test_sat_same_position(self) -> None:
        """Two identical rects at same position → True."""
        assert sat_overlap_rotated_rect(5, 5, 4, 8, 0.0, 5, 5, 4, 8, 0.0) is True

    def test_sat_touching_edge(self) -> None:
        """Rects sharing an edge → True (touching counts as collision in SAT).

        Note: SAT with half-open semantics is ambiguous, but the plan spec says
        touching = True. We use >= in projection check.
        """
        # rect 1: center (5, 5), h=4, w=4 — right edge at x=7
        # rect 2: center (5, 9), h=4, w=4 — left edge at x=7
        # Corners touch at x=7 boundary
        result = sat_overlap_rotated_rect(5, 5, 4, 4, 0.0, 5, 9, 4, 4, 0.0)
        assert result is True

    def test_sat_large_and_small(self) -> None:
        """Large rect completely contains small → True."""
        # Large: center (50, 50), h=40, w=40
        # Small: center (50, 50), h=4, w=4
        assert sat_overlap_rotated_rect(50, 50, 40, 40, 0.0, 50, 50, 4, 4, 0.0) is True

    def test_sat_theta_zero_matches_aabb(self) -> None:
        """At theta=0 SAT result matches AABB overlap for axis-aligned rects."""
        # Overlapping pair — AABB and SAT should both return True
        cy1, cx1, h1, w1 = 10.0, 10.0, 6.0, 8.0
        cy2, cx2, h2, w2 = 12.0, 14.0, 6.0, 8.0

        sat_result = sat_overlap_rotated_rect(cy1, cx1, h1, w1, 0.0, cy2, cx2, h2, w2, 0.0)

        # Build AABB arrays for aabb_overlap comparison
        aabb1 = np.array(
            [cy1 - h1 / 2, cx1 - w1 / 2, cy1 + h1 / 2, cx1 + w1 / 2], dtype=np.int32
        )
        aabb2 = np.array(
            [[cy2 - h2 / 2, cx2 - w2 / 2, cy2 + h2 / 2, cx2 + w2 / 2]], dtype=np.int32
        )
        aabb_result = bool(aabb_overlap(aabb1, aabb2).any())
        assert sat_result == aabb_result


class TestSatRotatedRects:
    """Tests for rotated rectangles — the critical correctness cases."""

    def test_sat_rotated_detects_what_aabb_misses(self) -> None:
        """Two thin rects at 45° that DO collide: SAT=True.

        AND: two thin rects at 45° that do NOT touch despite AABB overlap: SAT=False.

        This is the key correctness requirement (roadmap criteria #3).
        """
        # Case A: Two thin rects crossing in an X shape — they do collide
        # rect1: horizontal thin bar, h=2, w=30, center (50, 50), theta=0
        # rect2: same but rotated 45° — they cross in the middle
        result_overlap = sat_overlap_rotated_rect(
            50, 50, 2, 30, 0.0,
            50, 50, 2, 30, math.pi / 4,
        )
        assert result_overlap is True, "Crossing thin rects should be detected as overlapping"

        # Case B: Two thin rects at 45° that are close but NOT touching.
        # rect1: thin bar h=2, w=10, center at (50, 50), theta=+pi/4
        # rect2: thin bar h=2, w=10, center at (50, 50), theta=-pi/4
        # — these share center so they MUST overlap. Use a separated version instead.
        # rect1: thin diagonal bar at center (50, 50), theta=45°
        # rect2: thin diagonal bar at center (50, 75), theta=45°
        # Far enough apart that even AABBs might overlap but SAT sees no collision.
        # rect1 AABB: ~[50-5, 50-5, 50+5, 50+5] = [45,45,55,55]
        # rect2 AABB: ~[50-5, 75-5, 50+5, 75+5] = [45,70,55,80]
        # These AABBs do NOT overlap (x-gap between 55 and 70).
        # For a trickier test: very thin rects close but not touching:
        # rect1: h=2, w=20, center (50, 50), theta=pi/4
        #   corners: (50±10*cos45±1*sin45, 50±10*sin45∓1*cos45) ≈ (50±7.07±0.707, ...)
        #   AABB approx: y=[42.3, 57.7], x=[42.3, 57.7]
        # rect2: h=2, w=20, center (50, 63), theta=pi/4
        #   AABB approx: y=[55.3, 70.7], x=[55.3, 70.7]
        # AABBs overlap slightly (y: 55.3 < 57.7). SAT should say no collision.
        result_no_overlap = sat_overlap_rotated_rect(
            50, 50, 2, 20, math.pi / 4,
            50, 63, 2, 20, math.pi / 4,
        )
        assert result_no_overlap is False, (
            "Parallel thin rects with AABB overlap but no actual contact: SAT must return False"
        )


# ---------------------------------------------------------------------------
# Bitmap: pack_bitmap_uint32 tests
# ---------------------------------------------------------------------------


class TestPackBitmapUint32:
    """Tests for pack_bitmap_uint32()."""

    def test_pack_bitmap_uint32_shape(self) -> None:
        """(H, W) array → output shape (H, ceil(W/32))."""
        buf = np.zeros((10, 64), dtype=np.uint8)
        packed = pack_bitmap_uint32(buf)
        assert packed.shape == (10, 2)
        assert packed.dtype == np.uint32

    def test_pack_bitmap_uint32_shape_non_multiple(self) -> None:
        """Width not multiple of 32 → ceil(W/32) words."""
        buf = np.zeros((5, 50), dtype=np.uint8)
        packed = pack_bitmap_uint32(buf)
        assert packed.shape == (5, 2)  # ceil(50/32) = 2

    def test_pack_bitmap_uint32_all_ink(self) -> None:
        """All-pixel array → all bits set."""
        buf = np.ones((4, 32), dtype=np.uint8) * 255
        packed = pack_bitmap_uint32(buf)
        assert packed.shape == (4, 1)
        # All bits set = 0xFFFFFFFF
        assert np.all(packed == 0xFFFFFFFF)

    def test_pack_bitmap_uint32_no_ink(self) -> None:
        """Zero array → all bits zero."""
        buf = np.zeros((4, 32), dtype=np.uint8)
        packed = pack_bitmap_uint32(buf)
        assert np.all(packed == 0)

    def test_pack_bitmap_uint32_single_pixel(self) -> None:
        """Single ink pixel at column 0 → MSB (bit 31) set in word 0."""
        buf = np.zeros((1, 32), dtype=np.uint8)
        buf[0, 0] = 1  # leftmost pixel
        packed = pack_bitmap_uint32(buf)
        assert packed.shape == (1, 1)
        # Column 0: word_idx=0, bit_idx=31 → 1<<31 = 0x80000000
        assert packed[0, 0] == 0x80000000

    def test_pack_bitmap_uint32_last_pixel(self) -> None:
        """Single ink pixel at column 31 → LSB (bit 0) set in word 0."""
        buf = np.zeros((1, 32), dtype=np.uint8)
        buf[0, 31] = 1  # rightmost pixel in first word
        packed = pack_bitmap_uint32(buf)
        assert packed[0, 0] == 0x00000001


# ---------------------------------------------------------------------------
# Bitmap: bitmap_collision tests
# ---------------------------------------------------------------------------


def _make_solid_glyph(h: int, w: int) -> np.ndarray:
    """Return a packed uint32 array for a solid h×w glyph."""
    buf = np.ones((h, w), dtype=np.uint8)
    return pack_bitmap_uint32(buf)


class TestBitmapCollision:
    """Tests for bitmap_collision()."""

    def test_bitmap_collision_exact_overlap(self) -> None:
        """Two identical 8x8 solid glyphs at same position → True."""
        packed = _make_solid_glyph(8, 8)
        result = bitmap_collision(packed, 0, 0, 8, 8, packed, 0, 0, 8, 8)
        assert result is True

    def test_bitmap_collision_adjacent_no_overlap(self) -> None:
        """Two glyphs placed side by side with 1px gap → False."""
        # glyph A at x=0..7 (w=8), glyph B at x=9..16 (x_min=9, w=8)
        packed_a = _make_solid_glyph(8, 8)
        packed_b = _make_solid_glyph(8, 8)
        # A occupies x=[0,8), B occupies x=[9,17) — 1px gap at x=8
        result = bitmap_collision(packed_a, 0, 0, 8, 8, packed_b, 0, 9, 8, 8)
        assert result is False

    def test_bitmap_collision_no_overlap_y(self) -> None:
        """Two glyphs separated in y → False."""
        packed_a = _make_solid_glyph(8, 8)
        packed_b = _make_solid_glyph(8, 8)
        # A at y=[0,8), B at y=[10,18)
        result = bitmap_collision(packed_a, 0, 0, 8, 8, packed_b, 10, 0, 8, 8)
        assert result is False

    def test_bitmap_collision_bit_shift_alignment(self) -> None:
        """Glyph A at x=17, glyph B at x=25 (8px offset, not 32-aligned) → correct result.

        This is the critical Pitfall 3 test (RESEARCH.md §Pitfall 3).
        Both glyphs are solid and their pixel ranges overlap at x=[25,25+w).
        """
        h, w = 4, 8

        # Glyph A: solid 4x8, placed at (ay_min=0, ax_min=17)
        packed_a = _make_solid_glyph(h, w)
        # Glyph B: solid 4x8, placed at (by_min=0, bx_min=25)
        packed_b = _make_solid_glyph(h, w)

        # A covers x=[17, 25), B covers x=[25, 33)
        # They share edge at x=25 only — this is touching, SAT spec says True
        # But pixel-exact: A's last pixel is x=24, B's first pixel is x=25 → no overlap
        result_touching = bitmap_collision(packed_a, 0, 17, h, w, packed_b, 0, 25, h, w)
        # No pixel-exact overlap (A ends at 24, B starts at 25)
        assert result_touching is False

        # Now test with actual overlap: B at x=24 → overlaps by 1 pixel
        result_overlap = bitmap_collision(packed_a, 0, 17, h, w, packed_b, 0, 24, h, w)
        assert result_overlap is True, (
            "Solid glyphs at x=17 and x=24 (1px overlap at x=24) must detect collision "
            "despite non-32-aligned placement (Pitfall 3: bit-shift alignment)"
        )

    def test_bitmap_collision_no_false_negative(self) -> None:
        """Single ink pixel at boundary of overlap region → True."""
        h, w = 1, 1
        # A 1x1 glyph at position (5, 10) — single ink pixel
        packed_a = _make_solid_glyph(h, w)
        # Exact same position → must detect
        packed_b = _make_solid_glyph(h, w)
        result = bitmap_collision(packed_a, 5, 10, h, w, packed_b, 5, 10, h, w)
        assert result is True

    def test_bitmap_collision_no_false_positive(self) -> None:
        """Glyphs that touch diagonally but have no pixel overlap → False.

        Create an L-shaped situation: glyph A is only in top-left quadrant,
        glyph B is only in bottom-right quadrant of the AABB. AABB overlaps,
        pixel-exact does not.
        """
        # 4x4 glyph A: ink only in top-left 2x2 (rows 0-1, cols 0-1)
        buf_a = np.zeros((4, 4), dtype=np.uint8)
        buf_a[0:2, 0:2] = 1
        packed_a = pack_bitmap_uint32(buf_a)

        # 4x4 glyph B: ink only in bottom-right 2x2 (rows 2-3, cols 2-3)
        buf_b = np.zeros((4, 4), dtype=np.uint8)
        buf_b[2:4, 2:4] = 1
        packed_b = pack_bitmap_uint32(buf_b)

        # Place them at same position — AABB says same spot, but pixels don't overlap
        # because A has ink only at rows 0-1 cols 0-1 and B has ink only at rows 2-3 cols 2-3
        result = bitmap_collision(packed_a, 0, 0, 4, 4, packed_b, 0, 0, 4, 4)
        assert result is False
