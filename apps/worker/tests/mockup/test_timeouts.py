"""Sprint P26 — thread-based timeout-wrapper tests (scenario 6)."""
from __future__ import annotations

import threading
import time

import pytest

from aerocloud_worker.mockup.exceptions import MockupRenderTimeoutError
from aerocloud_worker.mockup.timeouts import with_timeout


def _fast_return(value: int) -> int:
    return value * 2


def _slow_sleep(duration: float) -> str:
    time.sleep(duration)
    return "done"


def _explodes() -> None:
    raise ValueError("boom")


def test_scenario_6_returns_value_when_under_timeout() -> None:
    assert with_timeout(_fast_return, 21, timeout_s=2.0) == 42


def test_scenario_6_timeout_raises_typed_error() -> None:
    with pytest.raises(MockupRenderTimeoutError) as excinfo:
        with_timeout(_slow_sleep, 2.0, timeout_s=0.2)
    assert "0.2" in str(excinfo.value)


def test_scenario_6_inner_exception_propagates() -> None:
    with pytest.raises(ValueError, match="boom"):
        with_timeout(_explodes, timeout_s=1.0)


def test_scenario_6_thread_does_not_leak_on_timeout() -> None:
    """After a timeout, the worker thread must be a daemon (no interpreter block)."""
    before = {t.ident for t in threading.enumerate()}
    with pytest.raises(MockupRenderTimeoutError):
        with_timeout(_slow_sleep, 1.0, timeout_s=0.1)
    # Daemon threads die with the interpreter — assert all new threads are daemons.
    after = threading.enumerate()
    new_threads = [t for t in after if t.ident not in before]
    for t in new_threads:
        assert t.daemon, f"with_timeout leaked non-daemon thread {t}"


def test_scenario_6_invalid_timeout_rejected() -> None:
    with pytest.raises(ValueError):
        with_timeout(_fast_return, 1, timeout_s=0)
    with pytest.raises(ValueError):
        with_timeout(_fast_return, 1, timeout_s=-1)
