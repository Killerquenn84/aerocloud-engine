"""Thread-based timeout wrapper for synchronous calls (Sprint P26 scenario 6).

We use ``threading`` + ``Event``, not ``signal`` (signals only fire on the
main thread and are unusable inside Celery workers) and not ``subprocess``
(which would mean re-pickling the PSD across the process boundary).

The wrapped call cannot be forcibly killed in Python — there is no public
API for that — but the calling thread does not block past ``timeout_s``,
the daemon worker thread is allowed to die with the interpreter, and
``MockupRenderTimeoutError`` is propagated to the caller so retry / fallback
logic can take over. This is the canonical pattern recommended by the
psd-tools maintainers for parse-timeouts.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, TypeVar

from .exceptions import MockupRenderTimeoutError

T = TypeVar("T")


def with_timeout(
    func: Callable[..., T],
    *args: Any,
    timeout_s: float,
    **kwargs: Any,
) -> T:
    """Run ``func(*args, **kwargs)`` and raise on timeout.

    Returns the function's result on success; re-raises any exception the
    function raised. Raises :class:`MockupRenderTimeoutError` if the call
    does not finish within ``timeout_s`` seconds.
    """
    if timeout_s <= 0:
        raise ValueError(f"timeout_s must be positive, got {timeout_s}")

    result: list[T] = []
    error: list[BaseException] = []
    done = threading.Event()

    def _runner() -> None:
        try:
            result.append(func(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller thread
            error.append(exc)
        finally:
            done.set()

    # daemon=True → thread does not block interpreter shutdown if it leaks.
    thread = threading.Thread(
        target=_runner,
        name=f"with_timeout({getattr(func, '__name__', 'fn')})",
        daemon=True,
    )
    thread.start()

    finished = done.wait(timeout_s)
    if not finished:
        raise MockupRenderTimeoutError(
            f"Call to {getattr(func, '__name__', 'fn')!r} exceeded "
            f"{timeout_s}s timeout"
        )

    if error:
        raise error[0]
    return result[0]
