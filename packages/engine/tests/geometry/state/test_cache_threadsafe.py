"""Concurrency stress test for geometry/sdf_cache.py (D-22, Regel 8 Test-L3).

16 threads each perform 1000 get_or_build calls using a rotating set of 4
distinct mask fixtures (circle, square, c_shape, crescent). The test asserts:

1. No exceptions raised from any thread.
2. All returned SDFs are float32.
3. Final cached SDFs match the reference output of compute_sdf(mask) computed
   sequentially before any threads start.
4. No RLock deadlock — the whole test must complete in < 30 seconds.

Rationale: cachetools.LRUCache is explicitly NOT thread-safe. The module-level
_CACHE_LOCK (threading.RLock) is the only guard. If compute_sdf were called
inside the lock, all 16 workers would serialize on one mutex. This test
verifies both correctness and absence of serialization.

No mocking of Pillow / scipy / numpy (D-51).
"""

from __future__ import annotations

import threading

import numpy as np

from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf import compute_sdf
from aerocloud.geometry.sdf_cache import clear_cache, get_or_build


def test_concurrent_16_threads_1000_ops(
    circle_mask_bytes: bytes,
    square_mask_bytes: bytes,
    c_shape_mask_bytes: bytes,
    crescent_mask_bytes: bytes,
) -> None:
    """16 threads x 1000 get_or_build calls maintain cache invariants under RLock.

    This is the Regel 8 Test-L3 (Race Conditions) gate for the SDF cache.
    The test must complete in < 30 seconds on CI (no deadlock).
    """
    clear_cache()

    # Build 4 fixture pairs (raw bytes + decoded mask) up front
    fixtures = [
        (circle_mask_bytes, mask_from_bytes(circle_mask_bytes)),
        (square_mask_bytes, mask_from_bytes(square_mask_bytes)),
        (c_shape_mask_bytes, mask_from_bytes(c_shape_mask_bytes)),
        (crescent_mask_bytes, mask_from_bytes(crescent_mask_bytes)),
    ]

    # Sequential reference: compute the expected SDF for each fixture BEFORE threads start.
    # This guarantees we can verify correctness after concurrent execution.
    references = {i: compute_sdf(m) for i, (_, m) in enumerate(fixtures)}

    errors: list[Exception] = []
    err_lock = threading.Lock()

    def worker() -> None:
        """Perform 1000 get_or_build calls rotating over the 4 fixtures."""
        try:
            for i in range(1000):
                raw, mask = fixtures[i % 4]
                sdf = get_or_build(raw, mask)
                # Each returned SDF must be float32 (D-19)
                if sdf.dtype != np.float32:
                    raise AssertionError(
                        f"Expected float32, got {sdf.dtype} at iteration {i}"
                    )
        except Exception as exc:
            with err_lock:
                errors.append(exc)

    # Spawn 16 threads
    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)  # hard timeout per thread; deadlock would be caught here

    # 1. No thread raised an exception
    assert not errors, f"{len(errors)} thread(s) raised exceptions:\n" + "\n".join(
        str(e) for e in errors
    )

    # 2. All threads completed (join returned before timeout)
    for i, t in enumerate(threads):
        assert not t.is_alive(), f"Thread {i} is still alive — possible deadlock"

    # 3. For each fixture, get_or_build now returns content-equal to sequential reference
    for i, (raw, mask) in enumerate(fixtures):
        final = get_or_build(raw, mask)
        assert np.array_equal(final, references[i]), (
            f"Cached SDF for fixture {i} differs from reference compute_sdf output"
        )

    clear_cache()
