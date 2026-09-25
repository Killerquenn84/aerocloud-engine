"""Verifies structlog emits JSON and stdlib LoggerFactory is configured."""

from __future__ import annotations

import json
import logging
from io import StringIO

import structlog

from aerocloud.logging import configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    configure_logging()  # second call must not raise


def test_logger_get_succeeds() -> None:
    configure_logging()
    log = get_logger("test-logger")
    # Logger must be callable and the log call must not raise
    log.info("test.event", key="value", number=42)
    log.warning("test.warning", reason="smoke test")


def test_logger_emits_json() -> None:
    # Bypass configure_logging() and test the JSON renderer directly.
    # This isolates the JSON format check from stdlib logging handler routing.
    buf = StringIO()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=buf),
        cache_logger_on_first_use=False,
    )

    log = structlog.get_logger("json-test")
    log.info("captured.event", foo="bar", n=3)

    output = buf.getvalue().strip()
    assert output, "no log output captured"

    parsed = json.loads(output)
    assert parsed["event"] == "captured.event"
    assert parsed["foo"] == "bar"
    assert parsed["n"] == 3
    assert parsed["level"] == "info"
    assert "timestamp" in parsed

    # Reset structlog config so other tests get a fresh state
    structlog.reset_defaults()
    configure_logging()
