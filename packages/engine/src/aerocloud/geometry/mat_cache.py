"""Bytes-bounded LRU cache for MATResult objects (D-17/D-22 pattern from sdf_cache.py).

Thread-safe via module-level ``threading.RLock``. Composite cache key includes
the blake3 digest of SDF bytes, min_branch_radius, algorithm version, and shape.
Changing ANY parameter produces a distinct cache key (T-07-01-01).

Design rationale (mirrors sdf_cache.py):
- D-17: cachetools.LRUCache with getsizeof=_mat_result_size (bytes-bounded)
- D-20: Composite key includes blake3 digest + all params + algo version + shape
- D-21: blake3 primary, sha256 fallback if blake3 unavailable
- D-22: module-level RLock; extract_mat NEVER called inside the lock
- T-07-01-01: min_branch_radius MUST be in the key to prevent stale hits
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Final

import numpy as np
from cachetools import LRUCache

from aerocloud.config import settings
from aerocloud.geometry.mat import MATResult, extract_mat

try:
    from blake3 import blake3 as _blake3_hasher

    def _digest(data: bytes) -> str:
        """Compute a hex digest using blake3 (D-21)."""
        return str(_blake3_hasher(data).hexdigest())

except ImportError:  # pragma: no cover — sha256 fallback for envs without blake3
    from hashlib import sha256 as _sha256_hasher

    def _digest(data: bytes) -> str:
        """Compute a hex digest using sha256 (D-21 fallback)."""
        return _sha256_hasher(data).hexdigest()


# Algorithm version salt — bump whenever extract_mat logic changes.
# Any increment invalidates all existing cache entries (D-20).
_MAT_ALGO_VERSION: Final[int] = 1


def _mat_result_size(result: MATResult) -> int:
    """Estimate bytes consumed by a MATResult (branch_map + travel_time arrays)."""
    return int(result.branch_map.nbytes + result.travel_time.nbytes)


def _make_key(
    sdf_bytes: bytes,
    shape: tuple[int, ...],
    min_branch_radius: float,
) -> tuple[Any, ...]:
    """Build a composite cache key (D-20 / T-07-01-01).

    Every parameter that affects the result MUST appear here.

    Args:
        sdf_bytes: The raw bytes of sdf.tobytes() (content-addressed).
        shape: The SDF shape (H, W).
        min_branch_radius: The min_branch_radius parameter.

    Returns:
        A 4-element tuple used as the cachetools key.
    """
    return (
        _digest(sdf_bytes),
        ("min_branch_radius", min_branch_radius),
        ("mat_algo_version", _MAT_ALGO_VERSION),
        tuple(shape),
    )


# Module-level LRU cache bounded by bytes (not entry count) via getsizeof (D-17).
# 128 MiB default budget from settings.mat_cache_max_bytes.
_MAT_CACHE: Any = LRUCache(
    maxsize=int(settings.mat_cache_max_bytes),
    getsizeof=_mat_result_size,
)

# Module-level reentrant lock — guards ALL cache reads and writes (D-22).
_MAT_CACHE_LOCK: threading.RLock = threading.RLock()


def get_or_build_mat(sdf: np.ndarray, min_branch_radius: float = 3.0) -> MATResult:
    """Return a cached MATResult or compute, cache, and return it.

    Thread-safe via double-checked locking (D-22). The lock is NEVER held while
    ``extract_mat`` runs — that would serialize every concurrent worker behind one
    mutex for potentially several seconds on large SDFs.

    If the resulting MATResult is larger than the entire cache budget, it is
    returned without caching (ValueError from cachetools is swallowed).

    Args:
        sdf: Float32 SDF of shape (H, W), positive inside, negative outside.
        min_branch_radius: Minimum inscribed-circle radius for branch inclusion.

    Returns:
        MATResult for the given SDF and parameters.
    """
    key = _make_key(sdf.tobytes(), sdf.shape, min_branch_radius)

    # Fast path: check under lock
    with _MAT_CACHE_LOCK:
        cached: MATResult | None = _MAT_CACHE.get(key)
        if cached is not None:
            return cached

    # Slow path: compute OUTSIDE the lock (D-22 invariant)
    result = extract_mat(sdf, min_branch_radius)

    with _MAT_CACHE_LOCK:
        # Re-check in case a competing thread populated the entry while we computed
        existing: MATResult | None = _MAT_CACHE.get(key)
        if existing is not None:
            return existing
        # Suppress ValueError when a single item's size exceeds the budget
        with contextlib.suppress(ValueError):
            _MAT_CACHE[key] = result

    return result


def clear_mat_cache() -> None:
    """Empty the MAT cache. Test-only helper."""
    with _MAT_CACHE_LOCK:
        _MAT_CACHE.clear()
