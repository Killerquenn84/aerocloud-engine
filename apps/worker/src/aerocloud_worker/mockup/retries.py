"""Exponential-backoff retry decorator (Sprint P26 scenarios 5 + 7).

Provides a single decorator :func:`retry` with the following semantics:

* up to ``max_attempts`` total tries (so ``max_attempts=3`` means 1 try + 2 retries)
* exponential backoff: ``base_delay * 2**(attempt-1)``, capped at ``max_delay``
* full jitter (delay in ``[0, computed_delay]``) to spread thundering herds
* exceptions outside ``exceptions`` propagate immediately (no retry)
* :class:`~aerocloud_worker.mockup.exceptions.RateLimitError` is ALWAYS
  retried (regardless of ``exceptions``) and honours its ``retry_after_s``
  attribute instead of the computed backoff

The sleep call is parameterised so tests can mock it cleanly.
"""
from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable, Type, TypeVar

from .exceptions import RateLimitError

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_EXCEPTIONS: tuple[Type[BaseException], ...] = (IOError,)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[Type[BaseException], ...] = _DEFAULT_EXCEPTIONS,
    *,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] = lambda d: random.uniform(0.0, d),
) -> Callable[[F], F]:
    """Decorator factory — see module docstring."""
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >=1, got {max_attempts}")

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            last_exc: BaseException | None = None
            while attempt < max_attempts:
                attempt += 1
                try:
                    return fn(*args, **kwargs)
                except RateLimitError as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        break
                    wait = float(exc.retry_after_s)
                    log.warning(
                        "retry.rate_limited",
                        extra={
                            "event": "retry.rate_limited",
                            "fn": fn.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "wait_s": wait,
                        },
                    )
                    sleep(wait)
                except exceptions as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        break
                    computed = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    wait = jitter(computed)
                    log.warning(
                        "retry.backoff",
                        extra={
                            "event": "retry.backoff",
                            "fn": fn.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "wait_s": wait,
                            "error_type": type(exc).__name__,
                        },
                    )
                    sleep(wait)
            # All attempts exhausted: re-raise the last exception so callers
            # get the typed error (not a wrapper).
            assert last_exc is not None  # noqa: S101 — invariant
            raise last_exc

        return wrapped  # type: ignore[return-value]

    return decorator
