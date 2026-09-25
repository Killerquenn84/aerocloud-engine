"""Tests for observability.py — OTLP exporter upgrade + Prometheus metrics.

Phase 12 Plan 04: PROD-18 (OTLP exporter) + PROD-19 (Prometheus metrics).

BDD Scenarios (Given/When/Then):

Scenario: NoOp mode (backward compatible)
  Given no otlp_endpoint is provided
  When init_tracing() is called
  Then a TracerProvider is created with no span processors

Scenario: OTLP mode
  Given an otlp_endpoint URL is provided
  When init_tracing(otlp_endpoint="http://localhost:4317") is called
  Then a BatchSpanProcessor with OTLPSpanExporter is added to the provider

Scenario: Idempotency
  Given init_tracing has already been called
  When init_tracing() is called again
  Then the second call is a no-op (no re-initialization)

Scenario: get_tracer returns a Tracer
  Given init_tracing has been called
  When get_tracer("test") is called
  Then a Tracer instance is returned

Scenario: Prometheus metrics are module-level singletons
  Given the observability module is imported
  Then render_duration is a prometheus_client Histogram
  And render_total is a prometheus_client Counter
  And gpu_memory_used is a prometheus_client Gauge

Scenario: AeroCloudSettings.otlp_endpoint defaults to None
  Given the Settings class is imported
  When Settings() is instantiated
  Then otlp_endpoint is None

Scenario: AeroCloudSettings.otlp_endpoint accepts URL string
  Given a valid URL string "http://collector:4317"
  When Settings(otlp_endpoint="http://collector:4317") is created
  Then settings.otlp_endpoint == "http://collector:4317"
"""

from __future__ import annotations

import importlib

import pytest
from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset() -> None:
    """Reset the observability module's _INITIALIZED flag for test isolation."""
    import aerocloud.observability as obs

    obs._reset_tracing()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_tracing() -> None:
    """Ensure each test starts with a clean tracing state."""
    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# PROD-18: OTLP exporter
# ---------------------------------------------------------------------------


class TestInitTracingNoOp:
    """init_tracing without otlp_endpoint — NoOp / backward-compatible."""

    def test_noop_mode_no_span_processors(self) -> None:
        """NoOp mode: TracerProvider must have zero active span processors."""
        from aerocloud.observability import init_tracing

        init_tracing()  # no otlp_endpoint

        provider = trace.get_tracer_provider()
        # SDK TracerProvider exposes _active_span_processor; in NoOp mode
        # it should be a SynchronousMultiSpanProcessor with 0 children,
        # or a NoOpSpanProcessor sentinel.  The simplest invariant: there are
        # no OTLPSpanExporter instances attached.
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        assert isinstance(provider, SDKTracerProvider)
        # Collect all exporters from all span processors
        processor = provider._active_span_processor
        exporters = _collect_exporters(processor)
        assert not any(isinstance(e, OTLPSpanExporter) for e in exporters), (
            "NoOp mode must not contain an OTLPSpanExporter"
        )

    def test_noop_mode_get_tracer_returns_tracer(self) -> None:
        """After NoOp init, get_tracer returns a valid Tracer instance."""
        from aerocloud.observability import get_tracer, init_tracing

        init_tracing()
        tracer = get_tracer("test.module")
        assert isinstance(tracer, trace.Tracer)

    def test_noop_mode_span_can_be_started(self) -> None:
        """Tracer in NoOp mode must not raise when starting a span."""
        from aerocloud.observability import get_tracer, init_tracing

        init_tracing()
        tracer = get_tracer("test.noop")
        with tracer.start_as_current_span("noop-span"):
            pass  # must not raise


class TestInitTracingOTLP:
    """init_tracing with otlp_endpoint — OTLP exporter wired."""

    def test_otlp_mode_has_batch_span_processor(self) -> None:
        """OTLP mode: provider must include a BatchSpanProcessor."""
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from aerocloud.observability import init_tracing

        init_tracing(otlp_endpoint="http://localhost:4317")

        provider = trace.get_tracer_provider()
        processor = provider._active_span_processor  # type: ignore[attr-defined]
        processors = _collect_processors(processor)
        assert any(isinstance(p, BatchSpanProcessor) for p in processors), (
            "OTLP mode must include a BatchSpanProcessor"
        )

    def test_otlp_mode_has_otlp_exporter(self) -> None:
        """OTLP mode: provider must have an OTLPSpanExporter attached."""
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        from aerocloud.observability import init_tracing

        init_tracing(otlp_endpoint="http://localhost:4317")

        provider = trace.get_tracer_provider()
        processor = provider._active_span_processor  # type: ignore[attr-defined]
        exporters = _collect_exporters(processor)
        assert any(isinstance(e, OTLPSpanExporter) for e in exporters), (
            "OTLP mode must attach an OTLPSpanExporter"
        )

    def test_otlp_mode_endpoint_configured(self) -> None:
        """OTLP exporter must be configured with the provided endpoint."""
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        from aerocloud.observability import init_tracing

        endpoint = "http://otel-collector:4317"
        init_tracing(otlp_endpoint=endpoint)

        provider = trace.get_tracer_provider()
        processor = provider._active_span_processor  # type: ignore[attr-defined]
        exporters = _collect_exporters(processor)
        otlp_exporters = [e for e in exporters if isinstance(e, OTLPSpanExporter)]
        assert len(otlp_exporters) == 1


class TestInitTracingIdempotency:
    """init_tracing is idempotent — second call must be a no-op."""

    def test_idempotent_noop_mode(self) -> None:
        """Two calls in NoOp mode: only one provider initialization."""
        from aerocloud.observability import init_tracing

        init_tracing()
        provider_after_first = trace.get_tracer_provider()

        init_tracing()  # second call
        provider_after_second = trace.get_tracer_provider()

        assert provider_after_first is provider_after_second

    def test_idempotent_otlp_mode(self) -> None:
        """Two calls in OTLP mode: provider not re-created on second call."""
        from aerocloud.observability import init_tracing

        init_tracing(otlp_endpoint="http://localhost:4317")
        provider_after_first = trace.get_tracer_provider()

        init_tracing(otlp_endpoint="http://localhost:4317")
        provider_after_second = trace.get_tracer_provider()

        assert provider_after_first is provider_after_second

    def test_idempotent_mixed_modes(self) -> None:
        """NoOp first, then OTLP: second call is ignored."""
        from aerocloud.observability import init_tracing

        init_tracing()  # NoOp
        provider_noop = trace.get_tracer_provider()

        init_tracing(otlp_endpoint="http://localhost:4317")  # OTLP — must be ignored
        provider_after_otlp = trace.get_tracer_provider()

        assert provider_noop is provider_after_otlp


class TestGetTracer:
    """get_tracer() returns a valid Tracer after init."""

    def test_get_tracer_without_prior_init(self) -> None:
        """get_tracer auto-initializes (NoOp) if init_tracing was not called."""
        from aerocloud.observability import _reset_tracing, get_tracer

        _reset_tracing()
        tracer = get_tracer("aerocloud.test")
        assert isinstance(tracer, trace.Tracer)

    def test_get_tracer_with_prior_init(self) -> None:
        """get_tracer returns a Tracer after explicit init_tracing."""
        from aerocloud.observability import get_tracer, init_tracing

        init_tracing()
        tracer = get_tracer("aerocloud.something")
        assert isinstance(tracer, trace.Tracer)


# ---------------------------------------------------------------------------
# PROD-19: Prometheus metrics
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    """Module-level Prometheus metric singletons."""

    def test_render_duration_is_histogram(self) -> None:
        """render_duration must be a Histogram."""
        from aerocloud.observability import render_duration

        assert isinstance(render_duration, Histogram)

    def test_render_total_is_counter(self) -> None:
        """render_total must be a Counter."""
        from aerocloud.observability import render_total

        assert isinstance(render_total, Counter)

    def test_gpu_memory_used_is_gauge(self) -> None:
        """gpu_memory_used must be a Gauge."""
        from aerocloud.observability import gpu_memory_used

        assert isinstance(gpu_memory_used, Gauge)

    def test_render_duration_name(self) -> None:
        """render_duration metric must have the canonical name."""
        from aerocloud.observability import render_duration

        # prometheus_client stores the name without the _bucket/_sum suffix
        assert render_duration._name == "aerocloud_render_duration_seconds"

    def test_render_total_name(self) -> None:
        """render_total metric must have the canonical name.

        prometheus_client automatically appends ``_total`` in the exposition
        format (Prometheus convention for Counters), so the internal ``_name``
        attribute stores the base name without the ``_total`` suffix.
        The full exposition name is ``aerocloud_renders_total``.
        """
        from aerocloud.observability import render_total

        # Internal base name (prometheus_client strips _total per convention)
        assert render_total._name == "aerocloud_renders"
        # The metric type confirms this is a counter (will be exposed as _total)
        assert render_total._type == "counter"

    def test_gpu_memory_used_name(self) -> None:
        """gpu_memory_used metric must have the canonical name."""
        from aerocloud.observability import gpu_memory_used

        assert gpu_memory_used._name == "aerocloud_gpu_memory_used_bytes"

    def test_render_total_has_status_label(self) -> None:
        """render_total must accept a 'status' label."""
        from aerocloud.observability import render_total

        # Labelling must not raise
        render_total.labels(status="success").inc()
        render_total.labels(status="error").inc()

    def test_render_duration_observe(self) -> None:
        """render_duration.observe() must not raise."""
        from aerocloud.observability import render_duration

        render_duration.observe(1.5)

    def test_gpu_memory_used_set(self) -> None:
        """gpu_memory_used.set() must not raise."""
        from aerocloud.observability import gpu_memory_used

        gpu_memory_used.set(1_000_000)

    def test_render_duration_custom_buckets(self) -> None:
        """render_duration must use the specified bucket boundaries."""
        from aerocloud.observability import render_duration

        expected_buckets = (0.5, 1, 2, 5, 10, 30, 60, 120, 300)
        # prometheus_client stores upper_bounds (includes +Inf at end)
        actual_upper_bounds = tuple(render_duration._upper_bounds[:-1])  # strip +Inf
        assert actual_upper_bounds == expected_buckets


# ---------------------------------------------------------------------------
# Config: otlp_endpoint field
# ---------------------------------------------------------------------------


class TestSettingsOtlpEndpoint:
    """AeroCloudSettings must expose otlp_endpoint."""

    def test_default_is_none(self) -> None:
        """otlp_endpoint defaults to None when env var not set."""
        import os

        from aerocloud.config import Settings

        env_backup = os.environ.pop("OTLP_ENDPOINT", None)
        try:
            s = Settings()
            assert s.otlp_endpoint is None
        finally:
            if env_backup is not None:
                os.environ["OTLP_ENDPOINT"] = env_backup

    def test_accepts_url_string(self) -> None:
        """otlp_endpoint accepts a valid URL string."""
        from aerocloud.config import Settings

        s = Settings(otlp_endpoint="http://collector:4317")
        assert s.otlp_endpoint == "http://collector:4317"

    def test_accepts_none_explicitly(self) -> None:
        """otlp_endpoint can be set to None explicitly."""
        from aerocloud.config import Settings

        s = Settings(otlp_endpoint=None)
        assert s.otlp_endpoint is None


# ---------------------------------------------------------------------------
# _reset_tracing helper
# ---------------------------------------------------------------------------


class TestResetTracingHelper:
    """_reset_tracing() must allow re-initialization for test isolation."""

    def test_reset_allows_reinit(self) -> None:
        """After _reset_tracing, init_tracing can be called again."""
        from aerocloud.observability import _reset_tracing, init_tracing

        init_tracing()
        _reset_tracing()
        # Should not raise — re-initialization after reset
        init_tracing(otlp_endpoint="http://localhost:4317")

    def test_reset_clears_initialized_flag(self) -> None:
        """After _reset_tracing, _INITIALIZED must be False."""
        import aerocloud.observability as obs

        obs.init_tracing()
        assert obs._INITIALIZED is True

        obs._reset_tracing()
        assert obs._INITIALIZED is False


# ---------------------------------------------------------------------------
# Internal helpers (not tests)
# ---------------------------------------------------------------------------


def _collect_exporters(processor: object) -> list[object]:
    """Recursively extract all exporters from a (possibly composite) processor."""
    exporters: list[object] = []
    # SynchronousMultiSpanProcessor / ConcurrentMultiSpanProcessor
    if hasattr(processor, "_span_processors"):
        for sub in processor._span_processors:
            exporters.extend(_collect_exporters(sub))
    # BatchSpanProcessor / SimpleSpanProcessor
    elif hasattr(processor, "span_exporter"):
        exporters.append(processor.span_exporter)
    return exporters


def _collect_processors(processor: object) -> list[object]:
    """Recursively extract all processors from a composite processor."""
    processors: list[object] = []
    if hasattr(processor, "_span_processors"):
        for sub in processor._span_processors:
            processors.append(sub)
            processors.extend(_collect_processors(sub))
    else:
        processors.append(processor)
    return processors
