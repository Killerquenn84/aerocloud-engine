"""Pytest configuration and fixtures for aerocloud-api tests.

The SlowAPI rate limiter uses a Redis-backed storage in production.
For unit tests we swap the storage backend of the EXISTING limiter singleton
to MemoryStorage so tests never hit a real Redis instance.

Key insight: @limiter.limit("10/minute") captures the *limiter instance* in a
closure at decoration time (via async_wrapper). Replacing app.state.limiter
with a new Limiter object does NOT affect the decorator's closure. The only
reliable fix is to swap the storage on both the limiter AND its inner strategy
object (limiter.limiter.storage), which is where __evaluate_limits actually
calls .hit().

Each test gets a fresh MemoryStorage so rate-limit counters do not bleed
between tests (e.g. rate_limit tests exhausting the counter that later render
endpoint tests hit).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from limits.storage import MemoryStorage


@pytest.fixture(autouse=True)
def _use_memory_rate_limiter() -> Generator[None, None, None]:
    """Swap RedisStorage → MemoryStorage on the production limiter per test.

    autouse=True applies this to every test in this package automatically.
    A fresh MemoryStorage is installed per test so rate-limit counters reset.
    Both limiter._storage and limiter.limiter.storage (the strategy's reference)
    are replaced — the strategy reads .storage directly when calling .hit().
    The original storage is restored in the yield-teardown after each test.
    """
    from aerocloud_api.middleware.rate_limit import limiter  # noqa: PLC0415

    # Save originals
    original_limiter_storage = limiter._storage
    original_strategy_storage = limiter.limiter.storage  # FixedWindowRateLimiter.storage

    # Install fresh in-memory storage for this test
    mem_storage = MemoryStorage()
    limiter._storage = mem_storage
    limiter.limiter.storage = mem_storage  # update the strategy's reference too

    yield

    # Restore originals so production config is valid after the test session
    limiter._storage = original_limiter_storage
    limiter.limiter.storage = original_strategy_storage
