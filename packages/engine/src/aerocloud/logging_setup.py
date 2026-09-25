"""Sprint P26 — stdlib JSON formatter for structured-logging.

Complements :mod:`aerocloud.logging` (structlog-based) with a pure-stdlib
``logging.Formatter`` so modules that emit via ``logging.getLogger(__name__).info(
event, extra={...})`` still produce JSON lines compatible with Loki/ELK.

This is what the mockup-engine uses (see ``mockup/engine.py``) — it cannot
take a hard dependency on structlog because the worker process must still
log usefully if ``configure_logging()`` was never called.

Usage::

    from aerocloud.logging_setup import configure_json_logging
    configure_json_logging()  # idempotent
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_RESERVED_LOGRECORD_KEYS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Format records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 — std signature
        payload: dict[str, Any] = {
            "ts": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
            )
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_KEYS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(level: str | int | None = None) -> None:
    """Install :class:`JSONFormatter` on the root logger. Idempotent."""
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Replace existing handlers' formatters rather than stacking new handlers.
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)
    for handler in root.handlers:
        handler.setFormatter(JSONFormatter())
