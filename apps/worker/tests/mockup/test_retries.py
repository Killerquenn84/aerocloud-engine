"""Sprint P26 — retry-decorator tests (scenarios 5 + 7)."""
from __future__ import annotations

import pytest

from aerocloud_worker.mockup.exceptions import (
    RateLimitError,
    S3DownloadError,
)
from aerocloud_worker.mockup.retries import retry


# ---------------------------------------------------------------------------
# Scenario 5 — S3 download timeout → exponential backoff → S3DownloadError
# ---------------------------------------------------------------------------


def test_scenario_5_first_call_succeeds_no_retry() -> None:
    calls = {"n": 0}

    @retry(max_attempts=3, exceptions=(IOError,))
    def fetch() -> str:
        calls["n"] += 1
        return "ok"

    assert fetch() == "ok"
    assert calls["n"] == 1


def test_scenario_5_transient_io_error_recovers() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry(
        max_attempts=3,
        base_delay=1.0,
        exceptions=(TimeoutError,),
        sleep=sleeps.append,
        jitter=lambda d: d,  # deterministic for the assertion
    )
    def fetch() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("S3 slow")
        return "ok"

    assert fetch() == "ok"
    assert calls["n"] == 3
    # 1s for attempt 1 → 2s for attempt 2 (exponential).
    assert sleeps == [1.0, 2.0]


def test_scenario_5_all_attempts_fail_raises_last_exception() -> None:
    calls = {"n": 0}

    @retry(
        max_attempts=3,
        exceptions=(S3DownloadError,),
        sleep=lambda _: None,
    )
    def fetch() -> str:
        calls["n"] += 1
        raise S3DownloadError(f"attempt {calls['n']}")

    with pytest.raises(S3DownloadError, match="attempt 3"):
        fetch()
    assert calls["n"] == 3


def test_scenario_5_unrelated_exceptions_propagate_immediately() -> None:
    calls = {"n": 0}

    @retry(max_attempts=3, exceptions=(IOError,), sleep=lambda _: None)
    def fetch() -> str:
        calls["n"] += 1
        raise ValueError("not retried")

    with pytest.raises(ValueError):
        fetch()
    assert calls["n"] == 1


def test_scenario_5_backoff_is_capped_by_max_delay() -> None:
    sleeps: list[float] = []

    @retry(
        max_attempts=5,
        base_delay=10.0,
        max_delay=15.0,
        exceptions=(IOError,),
        sleep=sleeps.append,
        jitter=lambda d: d,
    )
    def fetch() -> str:
        raise IOError("nope")

    with pytest.raises(IOError):
        fetch()
    # 10 → capped at 15 → 15 → 15. Four sleeps (one after each of 4 fails).
    assert sleeps == [10.0, 15.0, 15.0, 15.0]


# ---------------------------------------------------------------------------
# Scenario 7 — 429 response is respected
# ---------------------------------------------------------------------------


def test_scenario_7_rate_limit_honours_retry_after() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry(
        max_attempts=5,
        base_delay=1.0,
        exceptions=(IOError,),
        sleep=sleeps.append,
        jitter=lambda d: d,
    )
    def upload() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError(retry_after_s=10)
        return "ok"

    assert upload() == "ok"
    # The first sleep must be exactly Retry-After (10s), NOT the 1s backoff.
    assert sleeps == [10.0]
    assert calls["n"] == 2


def test_scenario_7_rate_limit_persists_until_max_attempts() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry(
        max_attempts=5,
        exceptions=(IOError,),
        sleep=sleeps.append,
        jitter=lambda d: d,
    )
    def upload() -> str:
        calls["n"] += 1
        raise RateLimitError(retry_after_s=3)

    with pytest.raises(RateLimitError):
        upload()
    assert calls["n"] == 5
    assert sleeps == [3.0, 3.0, 3.0, 3.0]  # 4 sleeps between 5 attempts


def test_scenario_7_rate_limit_retried_even_when_not_in_exceptions() -> None:
    """RateLimitError must be retried regardless of the `exceptions` whitelist."""
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry(
        max_attempts=3,
        exceptions=(KeyError,),  # deliberately wrong type
        sleep=sleeps.append,
        jitter=lambda d: d,
    )
    def upload() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError(retry_after_s=2)
        return "ok"

    assert upload() == "ok"
    assert sleeps == [2.0]
