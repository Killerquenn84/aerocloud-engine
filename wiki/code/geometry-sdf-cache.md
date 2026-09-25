# geometry/sdf_cache.py

**Module:** `aerocloud.geometry.sdf_cache`
**Phase:** 04-geometry-v1
**Decisions:** D-17, D-18, D-19, D-20, D-21, D-22, D-23
**ADRs:** ADR-0004 (sign salt in cache key)

## Purpose

Bytes-bounded LRU cache for float32 SDF arrays. One SDF per unique mask content
+ preprocessing parameters. Prevents re-computing expensive EDT on repeated
requests for the same mask. Guarded by a module-level `threading.RLock` for
concurrency safety (D-22).

## Public API

```python
def get_or_build(raw_mask_bytes: bytes, mask: np.ndarray) -> np.ndarray:
    """Return cached SDF or compute via compute_sdf(mask). Thread-safe (D-22)."""

def clear_cache() -> None:
    """Empty the cache. Test-only helper."""

def _rebuild_cache_for_test(max_bytes: int) -> None:
    """Replace cache with new budget. Internal test hook only."""

def _make_key(raw_mask_bytes: bytes, shape: tuple) -> tuple:
    """Build 6-element composite cache key (D-20)."""
```

## Key invariants

- Cache is **bytes-bounded** at 384 MiB default (D-18) via `getsizeof=lambda arr: arr.nbytes`.
- Cache key includes: blake3/sha256 digest + threshold + sign convention + dtype + algo version + shape (D-20).
- `xxhash64` is blocked — 64-bit non-cryptographic collision risk (D-21).
- `compute_sdf` is NEVER called inside a `with _CACHE_LOCK` block (D-22).
- Disk persistence deferred to Phase 12 (D-23).
- Wired to OTel counters `aerocloud_geometry_sdf_cache_hits_total` / `_misses_total`
  and histogram `aerocloud_geometry_sdf_build_seconds` (D-49, Wave 4).

## Dependencies

- `cachetools.LRUCache` (>=7.0.0)
- `blake3` (primary) / `hashlib.sha256` (fallback)
- `threading.RLock`
- `aerocloud.geometry.sdf` (compute_sdf)
- `aerocloud.geometry.metrics` (counters/histogram)
- `aerocloud.config` (sdf_cache_max_bytes setting)

## Tests

- `tests/geometry/state/test_cache.py` — hit/miss, eviction, key composition, budget
- `tests/geometry/state/test_cache_threadsafe.py` — 16 threads × 1000 get_or_build calls

## Performance notes

Cache hit: ~microseconds (dict lookup under RLock). Cache miss: full compute_sdf
cost (0.4–0.8 s for 2048x2048). Budget default 384 MiB ≈ 24 SDFs at 2048x2048 x
float32 = 16 MiB each.

## Related

- `wiki/code/geometry-sdf.md` — compute_sdf called on miss
- `wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md` — sign salt in D-20 key
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-17 through D-23
