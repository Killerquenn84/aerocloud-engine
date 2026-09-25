---
phase: 04-geometry-v1
plan: "03"
plan_id: 04-03-sdf-cache
subsystem: geometry
tags: [cache, lru, thread-safety, blake3, sdf, concurrency]
dependency_graph:
  requires: [04-02-mask-sdf]
  provides: [sdf_cache.get_or_build, sdf_cache.clear_cache, sdf_cache._make_key]
  affects: [phase-05-renderer, phase-06-inner-loop]
tech_stack:
  added: [cachetools>=7.0.0, blake3>=1.0.0]
  patterns: [bytes-bounded LRU, double-checked locking, RLock module-level guard]
key_files:
  created:
    - packages/engine/src/aerocloud/geometry/sdf_cache.py
    - packages/engine/tests/geometry/state/test_cache.py
    - packages/engine/tests/geometry/state/test_cache_threadsafe.py
  modified:
    - pyproject.toml  (added [[tool.mypy.overrides]] for cachetools)
decisions:
  - "bytes-bounded LRUCache(maxsize=_MAX_BYTES, getsizeof=lambda arr: arr.nbytes) — not entry-count-bounded (D-17)"
  - "blake3 primary hash + sha256 fallback; non-cryptographic hashes not used (D-21)"
  - "compute_sdf called OUTSIDE _CACHE_LOCK — no serialization of concurrent workers (D-22)"
  - "_rebuild_cache_for_test() internal hook allows eviction tests without module reload"
metrics:
  duration_minutes: 28
  completed_date: "2026-04-09"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
  tests_added: 9
  tests_total_geometry: 63
---

# Phase 4 Plan 3: SDF Cache Summary

**One-liner:** Thread-safe bytes-bounded LRU SDF cache (384 MiB, RLock double-checked, blake3 composite key) with 16-thread concurrency test.

## What Was Built

### `packages/engine/src/aerocloud/geometry/sdf_cache.py`

Implements D-17..D-23 from `04-CONTEXT.md`, fixing all issues Codex g-3 BLOCKED:

| BLOCKED issue | Fix applied |
|---|---|
| `maxsize=50` entry-count-bounded | `LRUCache(maxsize=_MAX_BYTES, getsizeof=lambda arr: int(arr.nbytes))` |
| Key = raw bytes only (stale cache risk) | Composite 6-tuple: blake3 digest + threshold + sign + dtype + algo_version + shape |
| `int16` quantization | `float32` values only (D-19) — no quantization |
| `xxhash64` (collision risk) | blake3 primary + sha256 fallback; non-cryptographic hashes not used |
| No thread safety | Module-level `threading.RLock` guards all cache reads/writes |
| Lock held during compute | `compute_sdf` called OUTSIDE `with _CACHE_LOCK:` block |

Key implementation details:
- `_SDF_ALGO_VERSION: Final[int] = 1` — bump to invalidate all cache entries on formula change
- `_MAX_BYTES: int = int(settings.sdf_cache_max_bytes)` — 384 MiB default, tunable via env var
- `_rebuild_cache_for_test(max_bytes)` — internal test hook for eviction tests without module reload
- `cachetools.ValueError` on oversize single entry is caught via `contextlib.suppress(ValueError)` — SDF returned uncached

### Test Files

**`tests/geometry/state/test_cache.py`** — 8 state tests (C1..C8):
- C1: cache hit returns same object on second call
- C2: different raw bytes → cache miss
- C3: `_SDF_ALGO_VERSION` bump → cache miss (composite key guard)
- C4: `_make_key` 6-tuple structure assertion (blake3 + 4 name-value tuples + shape)
- C5: bytes-budget eviction — oldest entry evicted when budget exceeded (10 KB test budget)
- C6: single SDF larger than budget → no exception, correct SDF returned uncached
- C7: `clear_cache()` empties the cache
- C8: `_CACHE_LOCK` is `threading.RLock`

**`tests/geometry/state/test_cache_threadsafe.py`** — 1 concurrency test:
- 16 threads × 1000 `get_or_build` ops, 4 rotating fixtures
- Asserts zero thread exceptions
- Asserts `float32` dtype on every result
- Asserts final cached SDFs == sequential reference `compute_sdf` output
- Thread join timeout = 30 s; actual wall clock ~1.5 s
- Deadlock check: asserts no thread is `is_alive()` after join

## RLock-Outside-Compute Invariant

The critical correctness property (D-22 / T-4-05 threat mitigation):

```
with _CACHE_LOCK:        # lock acquired
    cached = _CACHE.get(key)
    if cached: return cached
                         # lock released here

sdf = compute_sdf(mask)  # OUTSIDE lock — may take seconds on 4K masks

with _CACHE_LOCK:        # lock reacquired for write
    if key not in _CACHE:
        _CACHE[key] = sdf
```

Verified by:
1. Grep: `compute_sdf` does not appear inside any `with _CACHE_LOCK:` block
2. Concurrency test: 16-thread × 1000-op test completes in ~1.5 s (not serialized)

## Test Results

```
tests/geometry/state/test_cache.py          8 passed
tests/geometry/state/test_cache_threadsafe.py  1 passed
tests/geometry/ (full suite)               63 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] autouse fixture also restores cache budget**
- **Found during:** Task 1 Test C7 failure
- **Issue:** C5 called `_rebuild_cache_for_test(10_000)` which mutated module-level `_CACHE`. The autouse `_reset_cache` fixture only called `clear_cache()`, leaving subsequent tests with a 10 KB budget — `get_or_build` for a 64x64 SDF (16 KB) would silently skip caching, causing C7 to fail.
- **Fix:** Changed `_reset_cache` fixture to call `_rebuild_cache_for_test(original_max)` (save + restore `_MAX_BYTES`) instead of just `clear_cache()`.
- **Files modified:** `tests/geometry/state/test_cache.py`
- **Commit:** da4825e

**2. [Rule 1 - Bug] pyproject.toml mypy override for cachetools**
- **Found during:** Task 1 REFACTOR phase
- **Issue:** `cachetools` lacks bundled type stubs; mypy `--strict` emitted `[import-untyped]` error. Adding `type: ignore[import-untyped]` then caused `[unused-ignore]` errors because `ignore_missing_imports = true` in the root config made the annotation redundant.
- **Fix:** Added `[[tool.mypy.overrides]] module = "cachetools.*"` to root `pyproject.toml`; removed the `type: ignore` comment from the import line.
- **Files modified:** `pyproject.toml`
- **Commit:** da4825e

**3. [Rule 1 - Bug] xxhash in module docstring failed hallucination guard**
- **Found during:** Completion checks
- **Issue:** The module docstring referenced "xxhash BLOCKED" for documentation purposes, causing `! grep -q "xxhash" sdf_cache.py` guard to fail.
- **Fix:** Replaced with "non-cryptographic hashes blocked" — preserves intent without triggering the guard.
- **Files modified:** `packages/engine/src/aerocloud/geometry/sdf_cache.py`
- **Commit:** d51135f

## Hallucination Guards — PASSED

```
! grep -q "xxhash" packages/engine/src/aerocloud/geometry/sdf_cache.py  → PASS
grep -q "getsizeof" packages/engine/src/aerocloud/geometry/sdf_cache.py → PASS
```

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan is purely in-memory caching with no external surface.

| Threat Mitigated | Location |
|---|---|
| T-4-04: DoS via OOM | `getsizeof` bytes ceiling + `ValueError` suppression for oversize single entry |
| T-4-05: Deadlock | `compute_sdf` outside `_CACHE_LOCK`; concurrency test validates |
| T-4-02: Hash collision | blake3 (64-char hex) + sha256 fallback; xxhash not used |
| T-4-C1: Stale cache | Composite key includes all preprocessing params + algo version |

## Self-Check: PASSED

All files created, all commits present, all tests green.
