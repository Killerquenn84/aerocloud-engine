"""Contract tests for geometry Pydantic models (D-14, D-16, D-32).

BDD Scenario (TDD RED phase):
  Given: geometry Pydantic models are defined in aerocloud.models.geometry
  When: valid/invalid inputs are passed to AABB, GlyphBBox, MaskInput, GlyphRasterRequest
  Then: valid inputs construct successfully, invalid inputs raise ValidationError

All (y, x) ordering invariants per D-14 / D-16 are enforced.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from aerocloud.models.geometry import AABB, GlyphBBox, GlyphRasterRequest, MaskInput

# ---------------------------------------------------------------------------
# P1: AABB valid construction and extra-field rejection
# ---------------------------------------------------------------------------

def test_p1_aabb_valid_construction() -> None:
    """AABB constructs with (y_min, x_min, y_max, x_max) ordering (D-16)."""
    aabb = AABB(y_min=0, x_min=0, y_max=10, x_max=20)
    assert aabb.y_min == 0
    assert aabb.x_min == 0
    assert aabb.y_max == 10
    assert aabb.x_max == 20


def test_p1_aabb_rejects_wrong_field_names() -> None:
    """AABB rejects Pillow-style (left, top, right, bottom) — extra=forbid (D-16)."""
    with pytest.raises(ValidationError):
        AABB(left=0, top=0, right=10, bottom=20)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# P2: AABB half-open validator
# ---------------------------------------------------------------------------

def test_p2_aabb_rejects_ymin_ge_ymax() -> None:
    """AABB validator rejects y_min >= y_max (half-open invariant)."""
    with pytest.raises(ValidationError):
        AABB(y_min=10, x_min=0, y_max=10, x_max=20)  # y_min == y_max


def test_p2_aabb_rejects_xmin_ge_xmax() -> None:
    """AABB validator rejects x_min >= x_max (half-open invariant)."""
    with pytest.raises(ValidationError):
        AABB(y_min=0, x_min=5, y_max=10, x_max=5)  # x_min == x_max


# ---------------------------------------------------------------------------
# P3: AABB round-trip
# ---------------------------------------------------------------------------

def test_p3_aabb_round_trip_json() -> None:
    """AABB serialises to JSON and deserialises to equal value."""
    aabb = AABB(y_min=1, x_min=2, y_max=11, x_max=22)
    json_str = aabb.model_dump_json()
    restored = AABB.model_validate_json(json_str)
    assert restored == aabb


# ---------------------------------------------------------------------------
# P4: GlyphBBox valid construction
# ---------------------------------------------------------------------------

def test_p4_glyphbbox_valid_construction() -> None:
    """GlyphBBox constructs with numpy uint8 2-D pixel_buffer."""
    bbox = AABB(y_min=0, x_min=0, y_max=8, x_max=6)
    gb = GlyphBBox(
        bbox=bbox,
        advance_width=12,
        pixel_buffer=np.zeros((8, 6), dtype=np.uint8),
        font_family="Inter",
        size_pt=16,
        codepoint=ord("a"),
    )
    assert gb.advance_width == 12
    assert gb.font_family == "Inter"
    assert gb.codepoint == ord("a")


# ---------------------------------------------------------------------------
# P5: GlyphBBox rejects bad pixel_buffer
# ---------------------------------------------------------------------------

def test_p5_glyphbbox_rejects_non_uint8_buffer() -> None:
    """GlyphBBox raises if pixel_buffer dtype is not uint8."""
    bbox = AABB(y_min=0, x_min=0, y_max=8, x_max=6)
    with pytest.raises((ValidationError, TypeError)):
        GlyphBBox(
            bbox=bbox,
            advance_width=12,
            pixel_buffer=np.zeros((8, 6), dtype=np.float32),  # wrong dtype
            font_family="Inter",
            size_pt=16,
            codepoint=ord("a"),
        )


def test_p5_glyphbbox_rejects_non_ndarray_buffer() -> None:
    """GlyphBBox raises if pixel_buffer is not np.ndarray."""
    bbox = AABB(y_min=0, x_min=0, y_max=8, x_max=6)
    with pytest.raises((ValidationError, TypeError)):
        GlyphBBox(
            bbox=bbox,
            advance_width=12,
            pixel_buffer=[[0, 1], [2, 3]],  # type: ignore[arg-type]
            font_family="Inter",
            size_pt=16,
            codepoint=ord("a"),
        )


def test_p5_glyphbbox_rejects_1d_buffer() -> None:
    """GlyphBBox raises if pixel_buffer is 1-D instead of 2-D."""
    bbox = AABB(y_min=0, x_min=0, y_max=8, x_max=6)
    with pytest.raises((ValidationError, TypeError)):
        GlyphBBox(
            bbox=bbox,
            advance_width=12,
            pixel_buffer=np.zeros(8, dtype=np.uint8),  # 1-D
            font_family="Inter",
            size_pt=16,
            codepoint=ord("a"),
        )


# ---------------------------------------------------------------------------
# P6: xy_to_yx adapter + AABB boundary round-trip
# ---------------------------------------------------------------------------

def test_p6_xy_to_yx_adapter_with_aabb() -> None:
    """xy_to_yx converts Pillow-style (x, y) to numpy-native (y, x) (D-15)."""
    from aerocloud.geometry import xy_to_yx

    # Simulate np.argwhere output (numpy int64), convert to Python int via AABB
    yx_point = xy_to_yx((3, 5))  # x=3, y=5 → (y=5, x=3)
    assert yx_point == (5, 3)

    # Build AABB from numpy-style argwhere results
    arr = np.zeros((20, 30), dtype=np.uint8)
    arr[5:15, 3:25] = 255
    nz = np.argwhere(arr > 0)
    y_min, x_min = nz.min(axis=0)
    y_max, x_max = nz.max(axis=0) + 1
    aabb = AABB(
        y_min=int(y_min),
        x_min=int(x_min),
        y_max=int(y_max),
        x_max=int(x_max),
    )
    assert aabb.y_min == 5
    assert aabb.x_min == 3
    assert aabb.y_max == 15
    assert aabb.x_max == 25


# ---------------------------------------------------------------------------
# P7: MaskInput construction
# ---------------------------------------------------------------------------

def test_p7_maskinput_valid_construction() -> None:
    """MaskInput accepts raw PNG bytes (at least 8 bytes)."""
    # Fake 9-byte payload (not a real PNG but passes min_length=8)
    fake_png = b"\x89PNG\r\n\x1a\n\x00"  # 9 bytes
    mi = MaskInput(raw_png_bytes=fake_png)
    assert mi.raw_png_bytes == fake_png


def test_p7_maskinput_rejects_non_bytes() -> None:
    """MaskInput raises if raw_png_bytes is a string instead of bytes."""
    with pytest.raises(ValidationError):
        MaskInput(raw_png_bytes="not bytes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# P8: GlyphRasterRequest construction and validation
# ---------------------------------------------------------------------------

def test_p8_glyphrasternrequest_valid() -> None:
    """GlyphRasterRequest constructs with valid fields."""
    req = GlyphRasterRequest(font_family="Inter-Regular", codepoint=0x61, size_pt=16)
    assert req.font_family == "Inter-Regular"
    assert req.codepoint == 0x61
    assert req.size_pt == 16


def test_p8_glyphrasterrequest_rejects_nonpositive_size() -> None:
    """GlyphRasterRequest raises if size_pt <= 0."""
    with pytest.raises(ValidationError):
        GlyphRasterRequest(font_family="Inter-Regular", codepoint=0x61, size_pt=0)
