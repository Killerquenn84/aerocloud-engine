"""Structured JSON logging via structlog.

Usage:
    >>> from aerocloud.logging import configure_logging, get_logger
    >>> configure_logging()
    >>> log = get_logger(__name__)
    >>> log.info("event.name", key="value")

All logs are JSON-formatted to stdout for machine ingestion (OpenTelemetry
exporters, container log collectors, Grafana Loki).

References:
    - .planning/research/ARCHITECTURE.md §8 (observability)
    - .planning/phases/01-foundation/01-CONTEXT.md D-27
"""

from __future__ import annotations

import logging
import os
import sys

import structlog
from structlog.types import Processor

_LOG_LEVEL_ENV = "LOG_LEVEL"
_DEFAULT_LEVEL = "INFO"


def _resolve_level() -> int:
    raw = os.environ.get(_LOG_LEVEL_ENV, _DEFAULT_LEVEL).upper()
    return getattr(logging, raw, logging.INFO)


def configure_logging() -> None:
    """Configure structlog to emit JSON logs on stdout.

    Idempotent: safe to call multiple times. The second call is a no-op because
    structlog caches its configuration internally.
    """
    level = _resolve_level()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        # stdlib LoggerFactory because we use structlog.stdlib.add_logger_name
        # which reads logger.name (PrintLogger has no .name attribute).
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger. Call :func:`configure_logging` first."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
