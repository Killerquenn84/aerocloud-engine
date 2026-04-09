"""Bytes-bounded LRU cache for SDF arrays (D-17..D-23).

Thread-safe via module-level ``threading.RLock``. Composite cache key guards
against preprocessing drift: any change in threshold, sign convention, dtype,
or the SDF formula bumps ``_SDF_ALGO_VERSION`` and invalidates every entry.

Pattern mirrors ``aerocloud.nlp.tokenize``: double-check get/put around the
lock, compute heavy work OUTSIDE the lock so concurrent workers do not
serialize on one mutex.

Design rationale (ADR references):
- D-17: cachetools.LRUCache with getsizeof=lambda arr: arr.nbytes (bytes-bounded)
- D-18: 384 MiB default budget per worker process
- D-19: float32 values — no int16/float16 quantization
- D-20: composite key includes blake3 digest + preprocessing params + algo version + shape
- D-21: blake3 primary, sha256 fallback if blake3 unavailable; xxhash BLOCKED
- D-22: module-level RLock; compute_sdf MUST be called OUTSIDE the lock
- D-23: in-memory only; disk persistence deferred to Phase 12
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Final

import numpy as np
from cachetools import LRUCache

from aerocloud.config import settings
from aerocloud.geometry.sdf import compute_sdf

try:
    from blake3 import blake3 as _blake3_hasher

    def _digest(data: bytes) -> str:
        """Compute a 64-character hex digest using blake3 (D-21)."""
        return str(_blake3_hasher(data).hexdigest())

except ImportError:  # pragma: no cover — sha256 fallback for envs without blake3
    from hashlib import sha256 as _sha256_hasher

    def _digest(data: bytes) -> str:
        """Compute a 64-character hex digest using sha256 (D-21 fallback)."""
        return _sha256_hasher(data).hexdigest()


# Algorithm version salt — bump this integer whenever the SDF formula changes.
# Any increment invalidates all existing cache entries (D-20).
_SDF_ALGO_VERSION: Final[int] = 1

# Bytes budget for the in-process LRU cache (D-18).
# Initialized from Pydantic settings so ops can tune without code changes.
# NOT Final so _rebuild_cache_for_test() can temporarily override it in tests.
_MAX_BYTES: int = int(settings.sdf_cache_max_bytes)

# The LRU cache itself, bounded by bytes (not entry count) via getsizeof (D-17).
_CACHE: Any = LRUCache(
    maxsize=_MAX_BYTES,
    getsizeof=lambda arr: int(arr.nbytes),
)

# Module-level reentrant lock — guards ALL cache reads and writes (D-22).
# compute_sdf is NEVER called inside a `with _CACHE_LOCK:` block.
_CACHE_LOCK: threading.RLock = threading.RLock()


def _make_key(raw_mask_bytes: bytes, shape: tuple[int, ...]) -> tuple[Any, ...]:
    """Build a composite cache key (D-20).

    Every preprocessing knob MUST appear here so that a change in any
    parameter causes a cache miss rather than a stale hit.

    Args:
        raw_mask_bytes: The raw file bytes of the mask image (before decoding).
        shape: The decoded boolean mask shape ``(H, W)``.

    Returns:
        A 6-element tuple:
            0. blake3 (or sha256) hex digest of ``raw_mask_bytes``
            1. ``("threshold", 127)``  — D-06
            2. ``("sign", "positive_inside")``  — D-09 / ADR-0004
            3. ``("dtype", "float32")``  — D-10
            4. ``("sdf_algo_version", _SDF_ALGO_VERSION)``  — algorithm salt
            5. ``shape`` tuple  — output dimensions
    """
    return (
        _digest(raw_mask_bytes),
        ("threshold", 127),
        ("sign", "positive_inside"),
        ("dtype", "float32"),
        ("sdf_algo_version", _SDF_ALGO_VERSION),
        tuple(shape),
    )


def get_or_build(raw_mask_bytes: bytes, mask: np.ndarray) -> np.ndarray:
    """Return a cached SDF or compute, cache, and return.

    Thread-safe via double-checked locking (D-22). The lock is NEVER held
    while ``compute_sdf`` runs — that would serialize every concurrent worker
    behind a single mutex for up to several seconds on a 4096x4096 mask.

    If the resulting SDF is larger than the entire cache budget, it is
    returned without caching (ValueError from cachetools is swallowed).

    Args:
        raw_mask_bytes: Raw file bytes of the mask image; used as the basis
            for the content hash in the cache key.
        mask: Decoded boolean mask array ``(H, W)``.  Must match the mask
            that ``raw_mask_bytes`` decodes to — callers are responsible for
            decoding before calling this function.

    Returns:
        Float32 SDF of shape ``mask.shape``, positive inside, negative outside.
    """
    key = _make_key(raw_mask_bytes, mask.shape)

    # Fast path: check under lock (avoids compute on hit)
    with _CACHE_LOCK:
        cached: np.ndarray | None = _CACHE.get(key)
        if cached is not None:
            return cached

    # Slow path: compute OUTSIDE the lock (D-22 invariant — NEVER inside with block)
    sdf = compute_sdf(mask)

    with _CACHE_LOCK:
        # Re-check in case a competing thread populated the entry while we computed.
        # First writer wins; second writer's array is discarded (safe — both arrays
        # are content-identical since compute_sdf is deterministic).
        existing: np.ndarray | None = _CACHE.get(key)
        if existing is not None:
            return existing
        # cachetools raises ValueError when a single item's getsizeof exceeds
        # the entire maxsize budget. Suppress it — return the SDF without caching.
        with contextlib.suppress(ValueError):
            _CACHE[key] = sdf

    return sdf


def clear_cache() -> None:
    """Empty the SDF cache.

    Test-only helper. Production code must not call this — it defeats the
    purpose of the cache and is not concurrency-safe from the caller's
    perspective (a clear between a miss and an insert would cause the insert
    to repopulate an effectively-cleared cache, which is fine but unexpected).
    """
    with _CACHE_LOCK:
        _CACHE.clear()


def _rebuild_cache_for_test(max_bytes: int) -> None:
    """Replace the module-level cache with a new instance of the given budget.

    This is an INTERNAL TEST HOOK only. Production code must not call this.
    It is intentionally not exported from ``geometry/__init__.py``.

    Args:
        max_bytes: New byte budget for the replacement cache.
    """
    global _CACHE, _MAX_BYTES  # noqa: PLW0603 — intentional test hook
    with _CACHE_LOCK:
        _MAX_BYTES = max_bytes
        _CACHE = LRUCache(
            maxsize=max_bytes,
            getsizeof=lambda arr: int(arr.nbytes),
        )
