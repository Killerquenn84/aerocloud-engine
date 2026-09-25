"""Unit tests for geometry/mask.py — mask_from_bytes decoder.

TDD: Tests written BEFORE implementation (RED phase).
Tests M1..M9 cover D-04..D-08, D-14 from 04-CONTEXT.md.
No mocking of Pillow (D-51 — tests use real Pillow dependencies).
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.errors import EmptyMaskError, MaskFormatError
from aerocloud.geometry.mask import mask_from_bytes


def _png(mask_u8: np.ndarray, mode: str = "L") -> bytes:
    """Encode a uint8 ndarray as a PNG in the given mode."""
    img = Image.fromarray(mask_u8, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(mask_u8: np.ndarray) -> bytes:
    """Encode a uint8 ndarray as JPEG (for format rejection tests)."""
    img = Image.fromarray(mask_u8, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# M1: L-mode PNG → bool ndarray shape (H, W), True where pixel > 127
# ---------------------------------------------------------------------------


def test_m1_l_mode_png_to_bool_array() -> None:
    """M1: L-mode PNG decodes to bool ndarray shape (H, W), True where pixel > 127."""
    arr = np.zeros((8, 8), dtype=np.uint8)
    arr[2:6, 2:6] = 200  # set a 4x4 block to 200 (>127 → True)
    raw = _png(arr)
    mask = mask_from_bytes(raw)
    assert mask.dtype == np.dtype("bool"), f"expected bool, got {mask.dtype}"
    assert mask.shape == (8, 8), f"expected (8, 8), got {mask.shape}"
    assert mask[4, 4], "interior pixel (200) should be True"
    assert not mask[0, 0], "exterior pixel (0) should be False"


# ---------------------------------------------------------------------------
# M2: RGB PNG → convert to luminance then threshold at 127
# ---------------------------------------------------------------------------


def test_m2_rgb_png_to_bool_via_luminance() -> None:
    """M2: RGB PNG bytes → convert to luminance then threshold at 127."""
    # Create an RGB image: white center, black border
    arr_rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    arr_rgb[4:12, 4:12] = [200, 200, 200]  # light grey block
    img = Image.fromarray(arr_rgb, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    mask = mask_from_bytes(raw)
    assert mask.dtype == np.dtype("bool")
    assert mask.shape == (16, 16)
    assert mask[8, 8], "light grey pixel should be True (luminance > 127)"
    assert not mask[0, 0], "black pixel should be False"


# ---------------------------------------------------------------------------
# M3: RGBA PNG → use alpha channel (D-05), alpha > 127 = inside
# ---------------------------------------------------------------------------


def test_m3_rgba_png_uses_alpha_channel() -> None:
    """M3: RGBA PNG bytes → use alpha channel (D-05), alpha > 127 = inside."""
    arr_rgba = np.zeros((16, 16, 4), dtype=np.uint8)
    # Set some pixels with low RGB but high alpha (should be True)
    arr_rgba[4:12, 4:12] = [10, 10, 10, 200]  # dark color, high alpha
    # Set border pixels with high RGB but zero alpha (should be False)
    arr_rgba[0, 0] = [255, 255, 255, 0]
    img = Image.fromarray(arr_rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    mask = mask_from_bytes(raw)
    assert mask.dtype == np.dtype("bool")
    assert mask[8, 8], "high-alpha pixel should be True (alpha=200 > 127)"
    assert not mask[0, 0], "zero-alpha pixel should be False"


# ---------------------------------------------------------------------------
# M4: JPEG bytes raise MaskFormatError (only PNG allowed in v1, D-04)
# ---------------------------------------------------------------------------


def test_m4_jpeg_raises_mask_format_error() -> None:
    """M4: JPEG bytes raise MaskFormatError — only PNG supported in v1 (D-04)."""
    arr = np.full((8, 8), 200, dtype=np.uint8)
    raw = _jpeg(arr)
    with pytest.raises(MaskFormatError):
        mask_from_bytes(raw)


# ---------------------------------------------------------------------------
# M5: All-True mask raises EmptyMaskError("no outside")
# ---------------------------------------------------------------------------


def test_m5_all_true_mask_raises_empty_no_outside() -> None:
    """M5: All-True mask (all pixels 255) raises EmptyMaskError with 'no outside'."""
    arr = np.full((8, 8), 255, dtype=np.uint8)
    raw = _png(arr)
    with pytest.raises(EmptyMaskError, match="no outside"):
        mask_from_bytes(raw)


# ---------------------------------------------------------------------------
# M6: All-False mask raises EmptyMaskError("no inside")
# ---------------------------------------------------------------------------


def test_m6_all_false_mask_raises_empty_no_inside() -> None:
    """M6: All-zero mask raises EmptyMaskError with 'no inside'."""
    arr = np.zeros((8, 8), dtype=np.uint8)
    raw = _png(arr)
    with pytest.raises(EmptyMaskError, match="no inside"):
        mask_from_bytes(raw)


# ---------------------------------------------------------------------------
# M7: Result ordering is (y, x) row-major per D-07/D-14
# ---------------------------------------------------------------------------


def test_m7_shape_is_height_width_row_major() -> None:
    """M7: Decoded mask shape is (H, W) = (height, width) row-major, D-07/D-14."""
    # Use a non-square image to verify H ≠ W ordering
    arr = np.zeros((12, 20), dtype=np.uint8)  # 12 rows (height), 20 cols (width)
    arr[4:8, 2:18] = 200  # horizontal band: inside
    raw = _png(arr)
    mask = mask_from_bytes(raw)
    # shape should be (12, 20) — (height, width) = (y, x)
    assert mask.shape == (12, 20), (
        f"expected (12, 20) = (H, W), got {mask.shape}. "
        f"If (20, 12), coordinate ordering is wrong (x, y instead of y, x)."
    )
    # Verify a known asymmetric access: row 6, col 10 should be True
    assert mask[6, 10], "mask[row=6, col=10] should be True (inside band)"
    # Row 0, col 10 should be False
    assert not mask[0, 10], "mask[row=0, col=10] should be False (outside band)"


# ---------------------------------------------------------------------------
# M8: circle_mask_bytes fixture decodes to a valid non-degenerate mask
# ---------------------------------------------------------------------------


def test_m8_circle_fixture_is_nontrivial(circle_mask_bytes: bytes) -> None:
    """M8: circle_mask_bytes fixture decodes to mask with sum > 0 and sum < size."""
    mask = mask_from_bytes(circle_mask_bytes)
    assert mask.sum() > 0, "circle mask should have True pixels"
    assert mask.sum() < mask.size, "circle mask should have False pixels (outside circle)"


# ---------------------------------------------------------------------------
# M9: Threshold is EXACTLY 127 — pixel value 127 is OUTSIDE (> 127, not >= 127)
# ---------------------------------------------------------------------------


def test_m9_threshold_exactly_127_is_outside() -> None:
    """M9: A pixel with value exactly 127 is OUTSIDE (threshold is > 127, not >= 127)."""
    # Create image with one pixel at 127 (should be False) and one at 128 (should be True)
    arr = np.zeros((4, 4), dtype=np.uint8)
    arr[1, 1] = 127  # exactly threshold — should be OUTSIDE (False)
    arr[2, 2] = 128  # one above threshold — should be INSIDE (True)
    raw = _png(arr)
    mask = mask_from_bytes(raw)
    assert not mask[1, 1], "pixel=127 should be False (threshold is > 127, exclusive)"
    assert mask[2, 2], "pixel=128 should be True (128 > 127)"
