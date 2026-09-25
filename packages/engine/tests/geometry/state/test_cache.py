"""State tests for geometry/sdf_cache.py (TDD — D-17..D-23).

Tests C1..C8 cover:
  C1: cache hit returns same data on second call
  C2: different raw_bytes → cache miss
  C3: _SDF_ALGO_VERSION change invalidates entries (composite key guard)
  C4: _make_key contains exactly 6 components: blake3 digest + 4 name-value
      tuples + shape
  C5: bytes-budget eviction — oldest entry evicted when budget exceeded
  C6: single SDF larger than budget → no exception, correct SDF returned uncached
  C7: clear_cache() empties the cache
  C8: _CACHE_LOCK is an RLock instance (D-22)

No mocking of Pillow / scipy / numpy (D-51).  All tests use real compute_sdf
output via real mask fixtures.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from aerocloud.geometry import sdf_cache
from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf import compute_sdf
from aerocloud.geometry.sdf_cache import (
    _make_key,
    clear_cache,
    get_or_build,
)

# ---------------------------------------------------------------------------
# Shared autouse fixture: reset cache between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache():
    """Wipe cache and restore default budget before and after every test.

    Some tests (C5, C6) call _rebuild_cache_for_test() with a tiny budget.
    This fixture ensures subsequent tests see the original full budget.
    """
    original_max = sdf_cache._MAX_BYTES
    sdf_cache._rebuild_cache_for_test(original_max)
    yield
    sdf_cache._rebuild_cache_for_test(original_max)


# ---------------------------------------------------------------------------
# C1: Cache hit — second call returns cached array
# ---------------------------------------------------------------------------


def test_c1_cache_hit_returns_cached_array(circle_mask_bytes: bytes) -> None:
    """C1: get_or_build called twice with same raw_bytes returns the same data."""
    mask = mask_from_bytes(circle_mask_bytes)
    result1 = get_or_build(circle_mask_bytes, mask)
    result2 = get_or_build(circle_mask_bytes, mask)
    # Same content
    assert np.array_equal(result1, result2)
    # Same object (was cached, not recomputed)
    assert result1 is result2


# ---------------------------------------------------------------------------
# C2: Cache miss on different raw_bytes
# ---------------------------------------------------------------------------


def test_c2_different_bytes_produces_cache_miss(
    circle_mask_bytes: bytes, square_mask_bytes: bytes
) -> None:
    """C2: Different raw_bytes produce distinct cache misses."""
    circle_mask = mask_from_bytes(circle_mask_bytes)
    square_mask = mask_from_bytes(square_mask_bytes)
    r_circle = get_or_build(circle_mask_bytes, circle_mask)
    r_square = get_or_build(square_mask_bytes, square_mask)
    # Both are correct SDFs, not the same object
    assert r_circle is not r_square
    assert not np.array_equal(r_circle, r_square)


# ---------------------------------------------------------------------------
# C3: _SDF_ALGO_VERSION change invalidates all existing entries
# ---------------------------------------------------------------------------


def test_c3_algo_version_change_invalidates_cache(
    circle_mask_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C3: Bumping _SDF_ALGO_VERSION causes a cache miss for the same raw bytes."""
    mask = mask_from_bytes(circle_mask_bytes)

    # Populate cache at version 1
    original_version = sdf_cache._SDF_ALGO_VERSION
    r1 = get_or_build(circle_mask_bytes, mask)

    # Bump version via monkeypatch
    monkeypatch.setattr(sdf_cache, "_SDF_ALGO_VERSION", original_version + 1)

    # Now the same raw_bytes should produce a different key → cache miss → new array
    r2 = get_or_build(circle_mask_bytes, mask)

    # Different objects (r2 was recomputed, not served from cache)
    assert r1 is not r2
    # Both should have the same content (same mask → same SDF regardless of version)
    assert np.array_equal(r1, r2)


# ---------------------------------------------------------------------------
# C4: _make_key returns a 6-tuple with the right components
# ---------------------------------------------------------------------------


def test_c4_make_key_has_all_six_components(circle_mask_bytes: bytes) -> None:
    """C4: _make_key includes blake3 digest + 4 name-value tuples + shape."""
    mask = mask_from_bytes(circle_mask_bytes)
    key = _make_key(circle_mask_bytes, mask.shape)

    assert len(key) == 6, f"Expected 6-tuple, got len={len(key)}"
    digest, thr, sign, dtype, algo, shape = key

    # blake3 returns a 64-char hex string
    assert isinstance(digest, str), f"digest should be str, got {type(digest)}"
    assert len(digest) == 64, f"Expected 64-char hex digest, got len={len(digest)}"

    assert thr == ("threshold", 127), f"threshold tuple mismatch: {thr}"
    assert sign == ("sign", "positive_inside"), f"sign tuple mismatch: {sign}"
    assert dtype == ("dtype", "float32"), f"dtype tuple mismatch: {dtype}"

    assert isinstance(algo, tuple) and len(algo) == 2, f"algo should be 2-tuple, got {algo}"
    assert algo[0] == "sdf_algo_version", f"algo key mismatch: {algo[0]}"
    assert isinstance(algo[1], int), f"algo version should be int, got {type(algo[1])}"

    assert shape == mask.shape, f"shape mismatch: {shape} vs {mask.shape}"


# ---------------------------------------------------------------------------
# C5: Bytes-budget eviction — oldest entry evicted when budget exceeded
# ---------------------------------------------------------------------------


def test_c5_bytes_budget_eviction_evicts_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    """C5: When total SDF bytes exceed _MAX_BYTES, oldest entries are evicted.

    Override _MAX_BYTES to a tiny value so eviction happens with small 32x32
    masks (SDF ~4KB each, budget 10KB → at most 2 fit).
    """
    import io

    from PIL import Image

    def _make_small_mask(offset: int = 0) -> tuple[bytes, np.ndarray]:
        """Create a distinct 32x32 circle mask PNG."""
        y, x = np.ogrid[:32, :32]
        mask_arr: np.ndarray = (y - 16) ** 2 + (x - (16 + offset)) ** 2 <= 10**2
        # Force at least one True + one False pixel
        if not mask_arr.any():
            mask_arr[0, 0] = True
        if mask_arr.all():
            mask_arr[0, 0] = False
        img = Image.fromarray(mask_arr.astype(np.uint8) * 255, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), mask_arr

    # A 32x32 float32 array = 32*32*4 = 4096 bytes per SDF.
    # Set budget to 10_000 bytes → at most 2 entries fit.
    small_budget = 10_000
    sdf_cache._rebuild_cache_for_test(small_budget)

    # Insert 4 distinct SDFs — only the 2 newest should survive
    masks: list[tuple[bytes, np.ndarray]] = [_make_small_mask(i * 2) for i in range(4)]

    for raw, m in masks:
        get_or_build(raw, m)

    # Cache size in bytes must not exceed small_budget
    assert sdf_cache._CACHE.currsize <= small_budget, (
        f"Cache currsize {sdf_cache._CACHE.currsize} exceeds budget {small_budget}"
    )

    # The last inserted mask must be present
    last_raw, last_mask = masks[-1]
    last_key = _make_key(last_raw, last_mask.shape)
    assert last_key in sdf_cache._CACHE, "Last inserted entry should be present (newest)"

    # The first inserted mask must have been evicted
    first_raw, first_mask = masks[0]
    first_key = _make_key(first_raw, first_mask.shape)
    assert first_key not in sdf_cache._CACHE, "First inserted entry should be evicted (oldest)"


# ---------------------------------------------------------------------------
# C6: Single SDF larger than entire budget → no exception, correct SDF returned
# ---------------------------------------------------------------------------


def test_c6_single_sdf_exceeds_budget_no_exception(
    circle_mask_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C6: Inserting a SDF larger than the entire cache budget is handled gracefully."""
    mask = mask_from_bytes(circle_mask_bytes)
    sdf_size = mask.shape[0] * mask.shape[1] * 4  # float32 bytes

    # Set budget to less than one SDF
    tiny_budget = sdf_size - 1
    sdf_cache._rebuild_cache_for_test(tiny_budget)

    # Must not raise; result must be a valid SDF
    result = get_or_build(circle_mask_bytes, mask)

    assert isinstance(result, np.ndarray), "Result should be ndarray"
    assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"
    assert result.shape == mask.shape, f"Shape mismatch: {result.shape} vs {mask.shape}"

    reference = compute_sdf(mask)
    assert np.array_equal(result, reference), "Returned SDF must match reference compute_sdf"


# ---------------------------------------------------------------------------
# C7: clear_cache() empties the cache
# ---------------------------------------------------------------------------


def test_c7_clear_cache_empties_cache(circle_mask_bytes: bytes) -> None:
    """C7: clear_cache() resets cache length to 0."""
    mask = mask_from_bytes(circle_mask_bytes)
    get_or_build(circle_mask_bytes, mask)
    assert len(sdf_cache._CACHE) > 0, "Cache should be non-empty after get_or_build"

    clear_cache()
    assert len(sdf_cache._CACHE) == 0, "Cache should be empty after clear_cache()"


# ---------------------------------------------------------------------------
# C8: _CACHE_LOCK is an RLock (D-22)
# ---------------------------------------------------------------------------


def test_c8_cache_lock_is_rlock() -> None:
    """C8: _CACHE_LOCK is a reentrant lock (threading.RLock or _RLock)."""
    lock = sdf_cache._CACHE_LOCK
    # threading.RLock() returns an _RLock internal type; check via isinstance or repr
    # The most portable way is to check it has acquire/release and is reentrant
    rlock_type = type(threading.RLock())
    assert isinstance(lock, rlock_type), (
        f"_CACHE_LOCK should be threading.RLock, got {type(lock)}"
    )
