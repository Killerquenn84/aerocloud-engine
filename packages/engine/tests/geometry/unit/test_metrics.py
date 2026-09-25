"""Unit tests for geometry/metrics.py (D-48, D-49).

Verifies that all 5 metric instruments and the structlog logger exist and are
accessible. The OTel NoOp backend means instrument calls are silent no-ops in
tests — we only verify the objects exist and are the correct type.
"""

from __future__ import annotations

from opentelemetry.metrics import Counter, Histogram

from aerocloud.geometry.metrics import (
    DROPPED_WORDS,
    PLACEMENT_SECONDS,
    SDF_BUILD_SECONDS,
    SDF_CACHE_HITS,
    SDF_CACHE_MISSES,
    logger,
)


def test_logger_is_structlog_bound_logger() -> None:
    """metrics.logger must be a structlog BoundLogger (D-48)."""
    # structlog wraps the logger in a proxy; both BoundLogger and BoundLoggerLazyProxy
    # satisfy the structlog interface. We verify it is callable and structlog-originated.
    assert logger is not None
    # structlog loggers support bind() — verifies it is not a stdlib logger
    bound = logger.bind(test="value")
    assert bound is not None


def test_sdf_cache_hits_is_counter() -> None:
    """SDF_CACHE_HITS must be an OTel Counter (D-49)."""
    assert isinstance(SDF_CACHE_HITS, Counter)


def test_sdf_cache_misses_is_counter() -> None:
    """SDF_CACHE_MISSES must be an OTel Counter (D-49)."""
    assert isinstance(SDF_CACHE_MISSES, Counter)


def test_dropped_words_is_counter() -> None:
    """DROPPED_WORDS must be an OTel Counter (D-49)."""
    assert isinstance(DROPPED_WORDS, Counter)


def test_sdf_build_seconds_is_histogram() -> None:
    """SDF_BUILD_SECONDS must be an OTel Histogram (D-49)."""
    assert isinstance(SDF_BUILD_SECONDS, Histogram)


def test_placement_seconds_is_histogram() -> None:
    """PLACEMENT_SECONDS must be an OTel Histogram (D-49)."""
    assert isinstance(PLACEMENT_SECONDS, Histogram)


def test_counter_add_does_not_raise() -> None:
    """Counter.add() must not raise on a NoOp provider."""
    SDF_CACHE_HITS.add(1)
    SDF_CACHE_MISSES.add(1)
    DROPPED_WORDS.add(1, {"reason": "no_feasible_anchor"})


def test_histogram_record_does_not_raise() -> None:
    """Histogram.record() must not raise on a NoOp provider."""
    SDF_BUILD_SECONDS.record(0.123)
    PLACEMENT_SECONDS.record(0.456)
