"""End-to-end integration: PNG bytes -> PlacementResult.

Exercises mask -> sdf_cache -> placement against all four conftest shape
fixtures (circle, square, C-shape, crescent) and the empty-mask error path.

Compliance:
    - D-51: NO mocking of Pillow, scipy, or numpy. All deps are real.
    - D-38: Per-word adaptive POI verified via concave (C-shape) placement.
    - D-43: Structured DropReason values in dropped_words (never exceptions).
    - D-08: EmptyMaskError raised for all-white mask before any SDF work.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.errors import EmptyMaskError
from aerocloud.geometry.placement import place_words
from aerocloud.geometry.sdf_cache import clear_cache
from aerocloud.models.geometry import DropReason, PlacementRequest


@pytest.fixture(autouse=True)
def _clear_sdf_cache() -> object:
    """Clear SDF cache before and after each integration test for isolation."""
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Circle — convex shape, should place multiple small words without drops
# ---------------------------------------------------------------------------

def test_circle_places_words(circle_mask_bytes: bytes) -> None:
    """10 small words on a 64x64 circle — at least 1 must be placed."""
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[(f"w{i}", 4, 6) for i in range(10)],
        seed=42,
    )
    result = place_words(req)

    assert result.stats.total_words == 10
    assert result.stats.placed + result.stats.dropped == 10
    assert result.stats.placed >= 1, (
        f"Expected at least 1 placed on circle, got 0. "
        f"dropped={[d.reason for d in result.dropped_words]}"
    )

    # All placed words must be strictly inside canvas bounds
    for pw in result.placements:
        assert pw.bbox.y_min >= 0
        assert pw.bbox.x_min >= 0
        assert pw.bbox.y_max <= 64
        assert pw.bbox.x_max <= 64

    # Dropped words (if any) must carry valid DropReason values
    valid_reasons = set(DropReason)
    for dw in result.dropped_words:
        assert dw.reason in valid_reasons


# ---------------------------------------------------------------------------
# Square — convex, should place 2 moderate-sized words
# ---------------------------------------------------------------------------

def test_square_places_words(square_mask_bytes: bytes) -> None:
    """2 words on 64x64 square — at least 1 must be placed."""
    req = PlacementRequest(
        raw_png_bytes=square_mask_bytes,
        words=[("hello", 6, 12), ("world", 6, 14)],
        seed=0,
    )
    result = place_words(req)

    assert result.stats.total_words == 2
    assert result.stats.placed >= 1, (
        f"Expected at least 1 placed on square. "
        f"dropped={[d.reason for d in result.dropped_words]}"
    )


# ---------------------------------------------------------------------------
# C-shape — CONCAVE mask, per-word adaptive POI must handle this (D-38)
# ---------------------------------------------------------------------------

def test_c_shape_concave_produces_placements(c_shape_mask_bytes: bytes) -> None:
    """Concave C-mask must produce valid placements (D-38 per-word adaptive POI)."""
    req = PlacementRequest(
        raw_png_bytes=c_shape_mask_bytes,
        words=[("a", 3, 5), ("b", 3, 5), ("c", 3, 5)],
        seed=0,
    )
    result = place_words(req)

    assert result.stats.total_words == 3
    assert result.stats.placed >= 1, (
        f"Concave C-shape must place at least 1 word. "
        f"dropped={[d.reason for d in result.dropped_words]}"
    )

    # All placed word centers must be within canvas bounds
    for pw in result.placements:
        assert 0 <= pw.y < 64, f"Placed word y={pw.y} out of range"
        assert 0 <= pw.x < 64, f"Placed word x={pw.x} out of range"

    # Dropped words must carry structured DropReason values (NOT exceptions)
    valid_reasons = set(DropReason)
    for dw in result.dropped_words:
        assert dw.reason in valid_reasons, f"Invalid drop reason: {dw.reason!r}"


# ---------------------------------------------------------------------------
# Crescent — thin concave shape; accept 1 placed or 1 dropped with valid reason
# ---------------------------------------------------------------------------

def test_crescent_concave(crescent_mask_bytes: bytes) -> None:
    """Crescent is thin: accept placed OR dropped with valid structured reason."""
    req = PlacementRequest(
        raw_png_bytes=crescent_mask_bytes,
        words=[("x", 3, 4)],
        seed=0,
    )
    result = place_words(req)

    assert result.stats.total_words == 1
    assert result.stats.placed + result.stats.dropped == 1, (
        "placed + dropped must equal total_words"
    )

    if result.stats.dropped == 1:
        dw = result.dropped_words[0]
        assert dw.reason in (
            DropReason.NO_FEASIBLE_ANCHOR,
            DropReason.ITERATION_BUDGET_EXCEEDED,
            DropReason.TOO_LARGE_FOR_MASK,
            DropReason.WALL_CLOCK_EXCEEDED,
        ), f"Unexpected drop reason: {dw.reason!r}"


# ---------------------------------------------------------------------------
# Empty mask — all-True mask must raise EmptyMaskError BEFORE any SDF work
# ---------------------------------------------------------------------------

def test_all_true_mask_raises_empty_mask_error() -> None:
    """All-white PNG -> EmptyMaskError raised at mask_from_bytes (D-08)."""
    img = Image.fromarray(np.full((16, 16), 255, dtype=np.uint8), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    req = PlacementRequest(
        raw_png_bytes=buf.getvalue(),
        words=[("x", 3, 3)],
        seed=0,
    )
    with pytest.raises(EmptyMaskError):
        place_words(req)


# ---------------------------------------------------------------------------
# Regression: PlacementResult is JSON-serialisable (Pydantic contract)
# ---------------------------------------------------------------------------

def test_placement_result_json_serialisable(circle_mask_bytes: bytes) -> None:
    """PlacementResult must round-trip through model_dump_json without error."""
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[("hi", 5, 8)],
        seed=1,
    )
    result = place_words(req)
    json_str = result.model_dump_json()
    assert len(json_str) > 0

    from aerocloud.models.geometry import PlacementResult

    restored = PlacementResult.model_validate_json(json_str)
    assert restored.stats.total_words == result.stats.total_words
    assert restored.stats.placed == result.stats.placed
