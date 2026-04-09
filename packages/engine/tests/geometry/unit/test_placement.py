"""Unit tests for geometry/placement.py — adaptive POI spiral placement.

Test IDs: PL1..PL12 (from 04-05-PLAN.md Task 2 behavior spec).

RED phase: these tests are written BEFORE placement.py exists — they will fail
on import. After placement.py is implemented they must all turn GREEN.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from aerocloud.models.geometry import (
    DroppedWord,
    DropReason,
    PlacedWord,
    PlacementRequest,
    PlacementResult,
    PlacementStats,
)

# ---------------------------------------------------------------------------
# PL1 — DropReason enum has exactly 4 values
# ---------------------------------------------------------------------------

def test_pl1_drop_reason_four_values() -> None:
    values = set(DropReason)
    assert len(values) == 4
    assert DropReason.NO_FEASIBLE_ANCHOR in values
    assert DropReason.ITERATION_BUDGET_EXCEEDED in values
    assert DropReason.TOO_LARGE_FOR_MASK in values
    assert DropReason.WALL_CLOCK_EXCEEDED in values


# ---------------------------------------------------------------------------
# PL2 — All Pydantic models round-trip via JSON
# ---------------------------------------------------------------------------

def test_pl2_pydantic_models_json_roundtrip() -> None:
    from aerocloud.models.geometry import AABB

    bbox = AABB(y_min=0, x_min=0, y_max=4, x_max=6)
    pw = PlacedWord(word="hello", y=2, x=3, bbox=bbox, size_pt=12)
    dw = DroppedWord(word="world", reason=DropReason.NO_FEASIBLE_ANCHOR)
    stats = PlacementStats(
        total_words=2, placed=1, dropped=1,
        total_iterations=100, wall_clock_ms=12.5,
    )
    result = PlacementResult(placements=[pw], dropped_words=[dw], stats=stats)

    # Round-trip through JSON
    raw = result.model_dump_json()
    restored = PlacementResult.model_validate_json(raw)

    assert restored.placements[0].word == "hello"
    assert restored.dropped_words[0].reason == DropReason.NO_FEASIBLE_ANCHOR
    assert restored.stats.total_words == 2


# ---------------------------------------------------------------------------
# PL3 — archimedean_offsets determinism + first entry is (0, 0) + deduped
# ---------------------------------------------------------------------------

def test_pl3_archimedean_offsets_deterministic_first_zero() -> None:
    from aerocloud.geometry.placement import archimedean_offsets

    offsets_a = archimedean_offsets(step=4, max_iters=100)
    offsets_b = archimedean_offsets(step=4, max_iters=100)

    assert offsets_a == offsets_b, "archimedean_offsets must be deterministic"
    assert len(offsets_a) <= 100
    assert offsets_a[0] == (0, 0), f"First offset must be (0, 0), got {offsets_a[0]}"

    # All entries are (int, int)
    for dy, dx in offsets_a:
        assert isinstance(dy, int)
        assert isinstance(dx, int)


# ---------------------------------------------------------------------------
# PL4 — archimedean_offsets contains no duplicates
# ---------------------------------------------------------------------------

def test_pl4_archimedean_offsets_no_duplicates() -> None:
    from aerocloud.geometry.placement import archimedean_offsets

    offsets = archimedean_offsets(step=4, max_iters=200)
    as_set = set(offsets)
    assert len(offsets) == len(as_set), (
        f"archimedean_offsets contains duplicates: "
        f"{len(offsets)} total but {len(as_set)} unique"
    )


# ---------------------------------------------------------------------------
# PL5 — feasibility_field returns float32 (H, W) with expected structure
# ---------------------------------------------------------------------------

def test_pl5_feasibility_field_structure(square_mask_bytes: bytes) -> None:
    from aerocloud.geometry.mask import mask_from_bytes
    from aerocloud.geometry.placement import feasibility_field
    from aerocloud.geometry.sdf_cache import clear_cache, get_or_build

    clear_cache()
    mask = mask_from_bytes(square_mask_bytes)
    sdf = get_or_build(square_mask_bytes, mask)
    canvas_h, canvas_w = mask.shape

    h, w = 4, 6
    occupied = np.zeros((canvas_h, canvas_w), dtype=bool)
    ff = feasibility_field(sdf, occupied, h, w)

    assert ff.dtype == np.float32, f"Expected float32, got {ff.dtype}"
    assert ff.shape == (canvas_h, canvas_w), f"Expected ({canvas_h}, {canvas_w}), got {ff.shape}"

    # Edge pixels (AABB would poke outside) must be -inf
    assert not np.isfinite(ff[0, 0]), "Top-left corner must be -inf (AABB pokes outside)"
    assert not np.isfinite(ff[canvas_h - 1, canvas_w - 1]), "Bottom-right corner must be -inf"

    # Interior deep pixels inside the square should be finite and positive
    # The square occupies rows 12:52 cols 12:52 — center is at (32, 32)
    center_val = ff[32, 32]
    assert np.isfinite(center_val), f"Center pixel must be finite, got {center_val}"
    assert center_val > 0, f"Center of square must have positive feasibility, got {center_val}"


# ---------------------------------------------------------------------------
# PL6 — select_origin on circle returns center (unique global max)
# ---------------------------------------------------------------------------

def test_pl6_select_origin_circle_center(circle_mask_bytes: bytes) -> None:
    from aerocloud.geometry.mask import mask_from_bytes
    from aerocloud.geometry.placement import feasibility_field, select_origin
    from aerocloud.geometry.sdf_cache import clear_cache, get_or_build

    clear_cache()
    mask = mask_from_bytes(circle_mask_bytes)
    sdf = get_or_build(circle_mask_bytes, mask)
    canvas_h, canvas_w = mask.shape

    h, w = 4, 6
    occupied = np.zeros((canvas_h, canvas_w), dtype=bool)
    ff = feasibility_field(sdf, occupied, h, w)

    centroid_y = int(np.mean(np.where(mask)[0]))
    centroid_x = int(np.mean(np.where(mask)[1]))
    centroid = (centroid_y, centroid_x)

    origin = select_origin(ff, centroid)
    assert origin is not None, "select_origin must return a valid point for a circle"
    oy, ox = origin

    # The circle is centered at (32, 32); origin should be near center
    # Allow up to 5 px deviation — the exact peak depends on AABB size
    assert abs(oy - 32) <= 10, f"Origin y={oy} is too far from circle center 32"
    assert abs(ox - 32) <= 10, f"Origin x={ox} is too far from circle center 32"

    # Return type must be Python int (not np.int64) — Pydantic strict rejects numpy ints
    assert isinstance(oy, int) and not isinstance(oy, np.integer)
    assert isinstance(ox, int) and not isinstance(ox, np.integer)


# ---------------------------------------------------------------------------
# PL7 — select_origin returns None when all feasible_sdf <= 0
# ---------------------------------------------------------------------------

def test_pl7_select_origin_returns_none_when_infeasible() -> None:
    from aerocloud.geometry.placement import select_origin

    # All -inf feasibility field — no valid anchor
    ff = np.full((16, 16), -np.inf, dtype=np.float32)
    result = select_origin(ff, (8, 8))
    assert result is None

    # All zeros — not positive, so also no valid anchor
    ff_zeros = np.zeros((16, 16), dtype=np.float32)
    result_zeros = select_origin(ff_zeros, (8, 8))
    assert result_zeros is None


# ---------------------------------------------------------------------------
# PL8 — place_words on circle returns 1 placement inside the circle
# ---------------------------------------------------------------------------

def test_pl8_place_words_circle_one_word(circle_mask_bytes: bytes) -> None:
    from aerocloud.geometry.mask import mask_from_bytes
    from aerocloud.geometry.placement import place_words
    from aerocloud.geometry.sdf_cache import clear_cache

    clear_cache()
    mask = mask_from_bytes(circle_mask_bytes)

    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[("hello", 8, 40)],
        seed=42,
    )
    result = place_words(req)

    assert result.stats.placed == 1, (
        f"Expected 1 placed, got {result.stats.placed}; "
        f"dropped={result.dropped_words}"
    )
    pw = result.placements[0]
    assert pw.word == "hello"
    assert pw.bbox.y_min >= 0
    assert pw.bbox.x_min >= 0

    # Verify the placement is inside the circle mask
    canvas_h, canvas_w = mask.shape
    assert pw.bbox.y_max <= canvas_h
    assert pw.bbox.x_max <= canvas_w
    # Center pixel must be inside the mask (sdf > 0)
    assert mask[pw.y, pw.x], f"Placed word center ({pw.y}, {pw.x}) is outside mask"


# ---------------------------------------------------------------------------
# PL9 — Word with AABB larger than mask → dropped with TOO_LARGE_FOR_MASK
# ---------------------------------------------------------------------------

def test_pl9_too_large_for_mask(circle_mask_bytes: bytes) -> None:
    from aerocloud.geometry.placement import place_words
    from aerocloud.geometry.sdf_cache import clear_cache

    clear_cache()
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        # 64x64 circle mask — word taller than mask
        words=[("giant", 100, 200)],
        seed=0,
    )
    result = place_words(req)

    assert result.stats.dropped == 1
    assert result.stats.placed == 0
    dw = result.dropped_words[0]
    assert dw.word == "giant"
    assert dw.reason == DropReason.TOO_LARGE_FOR_MASK


# ---------------------------------------------------------------------------
# PL10 — 100 word stress on small square → no exceptions, valid DropReasons
# ---------------------------------------------------------------------------

def test_pl10_stress_small_square_no_exceptions(square_mask_bytes: bytes) -> None:
    from aerocloud.geometry.placement import place_words
    from aerocloud.geometry.sdf_cache import clear_cache

    clear_cache()
    # 100 tiny words on a 64x64 square — most will be dropped
    words = [(f"w{i}", 4, 8) for i in range(100)]
    req = PlacementRequest(raw_png_bytes=square_mask_bytes, words=words, seed=7)
    result = place_words(req)

    assert result.stats.total_words == 100
    assert result.stats.placed + result.stats.dropped == 100

    valid_reasons = set(DropReason)
    for dw in result.dropped_words:
        assert dw.reason in valid_reasons, f"Unknown drop reason: {dw.reason!r}"


# ---------------------------------------------------------------------------
# PL11 — NaN injected into SDF → PlacementFailedError (contract violation)
# ---------------------------------------------------------------------------

def test_pl11_nan_sdf_raises_placement_failed_error(
    circle_mask_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aerocloud.geometry.errors import PlacementFailedError
    from aerocloud.geometry.placement import place_words

    # Inject a NaN-bearing SDF via the cache
    nan_sdf = np.full((64, 64), np.nan, dtype=np.float32)

    def _bad_get_or_build(raw: bytes, mask: np.ndarray) -> np.ndarray:
        return nan_sdf

    # Patch the name in the placement module (that's where it's used)
    import aerocloud.geometry.placement as _placement_mod
    monkeypatch.setattr(_placement_mod, "get_or_build", _bad_get_or_build)

    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[("x", 4, 6)],
        seed=0,
    )
    with pytest.raises(PlacementFailedError):
        place_words(req)


# ---------------------------------------------------------------------------
# PL12 — Determinism: 2 sequential runs produce byte-identical JSON
# ---------------------------------------------------------------------------

def test_pl12_determinism_two_runs(circle_mask_bytes: bytes) -> None:
    from aerocloud.geometry.placement import place_words
    from aerocloud.geometry.sdf_cache import clear_cache

    clear_cache()
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[(f"word{i}", 5, 10) for i in range(5)],
        seed=99,
    )

    result1 = place_words(req)
    result2 = place_words(req)

    # Compare without wall_clock_ms (timing varies)
    dump1 = json.loads(result1.model_dump_json())
    dump2 = json.loads(result2.model_dump_json())
    dump1["stats"].pop("wall_clock_ms", None)
    dump2["stats"].pop("wall_clock_ms", None)

    assert dump1 == dump2, (
        "Two runs on the same input must produce identical PlacementResult\n"
        f"Run 1: {dump1}\nRun 2: {dump2}"
    )
