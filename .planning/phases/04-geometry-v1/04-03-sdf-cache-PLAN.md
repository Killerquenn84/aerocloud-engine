---
phase: 04-geometry-v1
plan: 03
plan_id: 04-03-sdf-cache
type: execute
wave: 2
depends_on: [04-02-mask-sdf]
autonomous: true
requirements: [GEO-04]
files_modified:
  - packages/engine/src/aerocloud/geometry/sdf_cache.py
  - packages/engine/tests/geometry/state/test_cache.py
  - packages/engine/tests/geometry/state/test_cache_threadsafe.py

must_haves:
  truths:
    - "get_or_build(raw_bytes, mask) returns cached SDF for the same raw bytes + shape"
    - "Cache is bytes-bounded at settings.sdf_cache_max_bytes (384 MiB default)"
    - "Inserting SDFs totalling > budget evicts oldest-first (LRU semantics)"
    - "Composite key includes blake3 digest + threshold + sign + dtype + sdf_algo_version + shape — any preprocessing change returns a cache miss"
    - "Inserting a single SDF larger than budget is refused gracefully (ValueError swallowed, returned array is correct)"
    - "16 concurrent threads × 1000 ops maintain cache invariants under RLock"
    - "sha256 fallback path works when blake3 is unavailable (simulated via import shim)"
    - "compute_sdf is called OUTSIDE the lock — no nested lock acquisitions"
  artifacts:
    - path: "packages/engine/src/aerocloud/geometry/sdf_cache.py"
      provides: "get_or_build(raw_bytes, mask) + clear_cache() + _make_key()"
  key_links:
    - from: "geometry/sdf_cache.py"
      to: "cachetools.LRUCache"
      via: "LRUCache(maxsize=_MAX_BYTES, getsizeof=lambda arr: arr.nbytes)"
      pattern: "LRUCache.*getsizeof"
    - from: "geometry/sdf_cache.py"
      to: "blake3"
      via: "blake3(raw_mask_bytes).hexdigest()"
      pattern: "blake3.*hexdigest"
    - from: "geometry/sdf_cache.py"
      to: "threading.RLock"
      via: "module-level _CACHE_LOCK"
      pattern: "threading.RLock"
    - from: "geometry/sdf_cache.py"
      to: "geometry/sdf.py"
      via: "compute_sdf call outside lock"
      pattern: "compute_sdf"
---

<objective>
Wave 2a: Ship the thread-safe, bytes-bounded SDF cache. Template from the
Phase 3 `nlp/tokenize.py` RLock registry pattern; use `cachetools.LRUCache`
with `getsizeof=lambda arr: arr.nbytes` to enforce the 384 MiB ceiling. The
composite key locks out correctness bugs from preprocessing drift
(threshold, sign, dtype, algo version).

Purpose: Phase 4 GEO-04 + Phase 6 Inner Loop hot-path caching. Codex g-3
BLOCKED the naive `maxsize=50` entry-count approach and the sha256/xxhash
single-hash key — this wave implements the redesigned cache.

Parallelizable with Plan 04-04 (glyph).

Output: `sdf_cache.py` + 2 test files (state + concurrency).
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md
@packages/engine/src/aerocloud/nlp/tokenize.py
@packages/engine/src/aerocloud/geometry/sdf.py
@packages/engine/src/aerocloud/config.py
</context>

<interfaces>
From 04-RESEARCH.md §3 (verbatim template):
```python
# geometry/sdf_cache.py target API
def get_or_build(raw_mask_bytes: bytes, mask: np.ndarray) -> np.ndarray: ...
def clear_cache() -> None: ...  # test-only
def _make_key(raw_mask_bytes: bytes, shape: tuple[int, int]) -> tuple: ...
```

From nlp/tokenize.py (template — copy the RLock double-check pattern):
```python
_registry: dict[str, Any] = {}
_registry_lock = threading.RLock()

def get_nlp(language):
    cached = _registry.get(language)
    if cached is not None:
        return cached
    with _registry_lock:
        cached = _registry.get(language)
        if cached is not None:
            return cached
        # ... load ...
        _registry[language] = loaded
    return loaded
```
</interfaces>

<tasks>

<task type="auto" id="04-03-T1" tdd="true">
  <name>Task 1: sdf_cache.py — LRUCache bytes-bounded (D-19 float32 value) + blake3 composite key + module-level state D-03 + RLock</name>
  <files>
    packages/engine/src/aerocloud/geometry/sdf_cache.py
    packages/engine/tests/geometry/state/test_cache.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-17..D-23 verbatim)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §3 (full reference implementation)
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md (BLOCK findings)
    - packages/engine/src/aerocloud/nlp/tokenize.py (RLock template)
    - packages/engine/src/aerocloud/geometry/sdf.py (compute_sdf signature)
  </read_first>
  <behavior>
    - Test C1 (RED): First call to `get_or_build(raw_bytes, mask)` returns an ndarray == `compute_sdf(mask)`. Second call with SAME raw_bytes returns the cached array (use `id()` check or content equality).
    - Test C2 (RED): Different raw_bytes → cache MISS, distinct array.
    - Test C3 (RED): Changing ONLY the algo_version constant invalidates all existing entries (verify via manipulating `_SDF_ALGO_VERSION` module attribute).
    - Test C4 (RED): `_make_key` includes: blake3 digest, threshold=127, sign="positive_inside", dtype="float32", sdf_algo_version, shape tuple. Assert all 6 elements present.
    - Test C5 (RED): Cache budget — insert 10 distinct masks each producing a ~5 MB SDF, total ~50 MB. Assert `len(_CACHE)` stays ≤ 10. Then insert enough until the bytes budget is exceeded; assert oldest entry was evicted and newest is present.
    - Test C6 (RED): Single SDF larger than budget — temporarily override `_MAX_BYTES` to a tiny value (e.g., 1024 bytes) via module-level test fixture; insert a 2 KB SDF; assert no exception reaches caller and the returned array is still a correct SDF (it just isn't cached).
    - Test C7 (RED): `clear_cache()` empties the cache (length 0).
    - Test C8 (RED): `RLock` is present — assert `isinstance(sdf_cache._CACHE_LOCK, (type(threading.RLock()), threading._RLock))` tolerant form.
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/state/test_cache.py`** with all 8 tests. Use real `compute_sdf` (no mocking, D-51). For C5, use small 32x32 fixtures and override `_MAX_BYTES` via monkeypatch to `10_000` bytes so eviction is provable in a fast test.

Example pattern:
```python
import threading
import numpy as np
import pytest
from aerocloud.geometry import sdf_cache
from aerocloud.geometry.sdf_cache import get_or_build, clear_cache, _make_key


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_cache()
    yield
    clear_cache()


def test_make_key_has_all_six_components(circle_mask_bytes):
    from aerocloud.geometry.mask import mask_from_bytes
    mask = mask_from_bytes(circle_mask_bytes)
    key = _make_key(circle_mask_bytes, mask.shape)
    assert len(key) == 6
    digest, thr, sign, dtype, algo, shape = key
    assert isinstance(digest, str) and len(digest) == 64  # blake3 hex
    assert thr == ("threshold", 127)
    assert sign == ("sign", "positive_inside")
    assert dtype == ("dtype", "float32")
    assert algo[0] == "sdf_algo_version" and isinstance(algo[1], int)
    assert shape == mask.shape
```

Run tests — all RED.

**Step 2 — GREEN: Implement `packages/engine/src/aerocloud/geometry/sdf_cache.py`** per 04-RESEARCH.md §3:

```python
"""Bytes-bounded LRU cache for SDF arrays (D-17..D-23).

Thread-safe via module-level `threading.RLock`. Composite cache key guards
against preprocessing drift: any change in threshold, sign convention, dtype,
or the SDF formula bumps `_SDF_ALGO_VERSION` and invalidates every entry.

Pattern mirrors `aerocloud.nlp.tokenize`: double-check get/put around the
lock, compute heavy work OUTSIDE the lock so concurrent workers do not
serialize on one mutex.
"""
from __future__ import annotations

import threading
from typing import Final

import numpy as np
from cachetools import LRUCache

from aerocloud.config import settings
from aerocloud.geometry.sdf import compute_sdf

try:
    from blake3 import blake3 as _hasher

    def _digest(data: bytes) -> str:
        return _hasher(data).hexdigest()

except ImportError:  # pragma: no cover - dev fallback only
    from hashlib import sha256

    def _digest(data: bytes) -> str:
        return sha256(data).hexdigest()


_SDF_ALGO_VERSION: Final[int] = 1

_MAX_BYTES: int = int(settings.sdf_cache_max_bytes)

_CACHE: LRUCache = LRUCache(
    maxsize=_MAX_BYTES,
    getsizeof=lambda arr: int(arr.nbytes),
)
_CACHE_LOCK: threading.RLock = threading.RLock()


def _make_key(raw_mask_bytes: bytes, shape: tuple[int, ...]) -> tuple:
    """Composite cache key (D-20). Every preprocessing knob MUST appear here."""
    return (
        _digest(raw_mask_bytes),
        ("threshold", 127),
        ("sign", "positive_inside"),
        ("dtype", "float32"),
        ("sdf_algo_version", _SDF_ALGO_VERSION),
        tuple(shape),
    )


def get_or_build(raw_mask_bytes: bytes, mask: np.ndarray) -> np.ndarray:
    """Return a cached SDF or compute + cache + return.

    The lock is NEVER held while `compute_sdf` runs — that would serialize
    every worker behind a single mutex and defeat concurrency.
    """
    key = _make_key(raw_mask_bytes, mask.shape)

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached

    sdf = compute_sdf(mask)

    with _CACHE_LOCK:
        existing = _CACHE.get(key)
        if existing is not None:
            return existing
        try:
            _CACHE[key] = sdf
        except ValueError:
            # SDF exceeds entire cache budget — return without caching.
            pass
    return sdf


def clear_cache() -> None:
    """Test-only helper. Production must not call this."""
    with _CACHE_LOCK:
        _CACHE.clear()
```

**Step 3 — GREEN: Run tests until green.** Note for C5: you may need to patch `sdf_cache._MAX_BYTES` directly and recreate `_CACHE` via a helper in the test — add an internal `_rebuild_cache_for_test(max_bytes: int) -> None` test hook to `sdf_cache.py` that tests can call; it replaces `_CACHE` under the lock.

**Step 4 — REFACTOR:** mypy --strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/state/test_cache.py -x -q && uv run mypy --strict src/aerocloud/geometry/sdf_cache.py && uv run ruff check src/aerocloud/geometry/sdf_cache.py tests/geometry/state/test_cache.py</automated>
  </verify>
  <acceptance_criteria>
    - `sdf_cache.py` contains `LRUCache(maxsize=_MAX_BYTES, getsizeof=lambda arr: int(arr.nbytes))`
    - `sdf_cache.py` contains `_CACHE_LOCK: threading.RLock`
    - `sdf_cache.py` contains `_SDF_ALGO_VERSION: Final[int] = 1`
    - `_make_key` returns a 6-tuple with blake3 digest + 4 name-value tuples + shape
    - `compute_sdf` is called OUTSIDE the lock (grep: `with _CACHE_LOCK` blocks do NOT contain `compute_sdf(`)
    - All 8 state tests pass
    - mypy --strict clean
    - ruff clean
  </acceptance_criteria>
  <done>Cache module green with all state tests</done>
</task>

<task type="auto" id="04-03-T2">
  <name>Task 2: Concurrency test — 16 threads × 1000 ops under RLock</name>
  <files>
    packages/engine/tests/geometry/state/test_cache_threadsafe.py
  </files>
  <read_first>
    - packages/engine/src/aerocloud/geometry/sdf_cache.py (from Task 1)
    - packages/engine/src/aerocloud/nlp/tokenize.py (RLock template reference)
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-22)
  </read_first>
  <action>
Write a threading stress test that spawns 16 threads, each performing 1000
`get_or_build` calls using a rotating set of 4 distinct mask byte fixtures
(circle, square, c_shape, crescent). After all threads join, assert:

1. No exceptions were raised from any thread (use a shared `list` of exceptions
   protected by a `threading.Lock`).
2. The cache contains at most 4 entries (one per distinct mask).
3. For each of the 4 masks, `get_or_build(raw, mask)` returns an array
   `np.array_equal` with the sequential reference computed via
   `compute_sdf(mask)` directly.
4. No RLock deadlock — the whole test must complete in < 30 seconds.

```python
import threading
import numpy as np
import pytest
from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf import compute_sdf
from aerocloud.geometry.sdf_cache import get_or_build, clear_cache


@pytest.mark.timeout(60)  # if pytest-timeout is available; otherwise trust < 30 s wall
def test_concurrent_16_threads(
    circle_mask_bytes: bytes,
    square_mask_bytes: bytes,
    c_shape_mask_bytes: bytes,
    crescent_mask_bytes: bytes,
) -> None:
    clear_cache()
    fixtures = [
        (circle_mask_bytes, mask_from_bytes(circle_mask_bytes)),
        (square_mask_bytes, mask_from_bytes(square_mask_bytes)),
        (c_shape_mask_bytes, mask_from_bytes(c_shape_mask_bytes)),
        (crescent_mask_bytes, mask_from_bytes(crescent_mask_bytes)),
    ]
    references = {i: compute_sdf(m) for i, (_, m) in enumerate(fixtures)}

    errors: list[Exception] = []
    err_lock = threading.Lock()

    def worker() -> None:
        try:
            for i in range(1000):
                raw, mask = fixtures[i % 4]
                sdf = get_or_build(raw, mask)
                assert sdf.dtype == np.float32
        except Exception as e:
            with err_lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"threads raised: {errors}"
    for i, (raw, mask) in enumerate(fixtures):
        final = get_or_build(raw, mask)
        assert np.array_equal(final, references[i])
```

Run the test. If `pytest-timeout` is not installed, drop the `@pytest.mark.timeout` line but document that wall clock should be < 30 s.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/state/test_cache_threadsafe.py -x -q && uv run ruff check tests/geometry/state/test_cache_threadsafe.py</automated>
  </verify>
  <acceptance_criteria>
    - Test file spawns 16 threads × 1000 ops
    - Uses all 4 concave/convex fixtures from conftest
    - Asserts zero thread exceptions
    - Asserts final cached SDFs match reference `compute_sdf` output
    - Test completes in < 30 seconds on CI
    - No deadlock
  </acceptance_criteria>
  <done>Concurrency invariant proven under 16 threads</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Cache memory → worker RSS | Budget controls DoS surface |
| blake3 availability → hash collision risk | Supply chain trust |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-04 | DoS | sdf_cache OOM via crafted masks | mitigate | `cachetools.LRUCache(maxsize=_MAX_BYTES, getsizeof=...)` enforces hard bytes ceiling; `ValueError` on oversize-single-entry is caught and SDF returned uncached (Task 1 C6) |
| T-4-05 | DoS (deadlock) | Nested compute_sdf via cache lock | mitigate | Code invariant: `compute_sdf` is invoked OUTSIDE `with _CACHE_LOCK:` blocks (grep-verifiable); concurrency Task 2 catches any regression |
| T-4-02 | Tampering | blake3 downgrade to sha256 hash collision | mitigate | Both hash paths tested; sha256 is a safe crypto fallback (not xxhash which was BLOCKED per D-21) |
| T-4-C1 | Tampering (stale cache) | Preprocessing drift returns wrong SDF | mitigate | Composite key includes threshold + sign + dtype + sdf_algo_version + shape (Test C3, C4) |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry/state -x -q` exits 0 (8 + 1 = 9 tests)
- `uv run mypy --strict src/aerocloud/geometry/sdf_cache.py` exits 0
- `uv run ruff check src/aerocloud/geometry/sdf_cache.py tests/geometry/state/` exits 0
- grep assertion: `with _CACHE_LOCK:` block does NOT contain `compute_sdf(` (correctness invariant)
</verification>

<success_criteria>
1. `sdf_cache.get_or_build` returns cached SDF for repeated calls
2. Bytes-bounded eviction proven under a 10 KB test budget
3. Composite key rejects preprocessing drift
4. 16-thread concurrency test passes without deadlock or corruption
5. blake3 primary + sha256 fallback both functional
6. mypy --strict + ruff clean
</success_criteria>

<output>
Create `.planning/phases/04-geometry-v1/04-03-SUMMARY.md` with:
- Module shipped (sdf_cache.py)
- Test counts (state + concurrency)
- Any eviction behavior observations
- Confirmation that the RLock-outside-compute invariant holds
</output>
