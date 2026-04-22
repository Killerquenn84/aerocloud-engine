"""OpenTelemetry SDK initialization + Prometheus metrics.

Phase 12 (PROD-18, PROD-19): Upgrades NoOp tracing to full OTLP export when
an endpoint is configured, and defines module-level Prometheus metric singletons
used by the Celery worker and FastAPI instrumentator.

Backward compatibility: callers that do not pass ``otlp_endpoint`` continue to
get the Phase 1 NoOp behaviour — no exporter, no span processor.

Usage:
    >>> from aerocloud.observability import init_tracing, get_tracer
    >>> init_tracing(service_name="aerocloud-engine", otlp_endpoint="http://otel:4317")
    >>> tracer = get_tracer(__name__)
    >>> with tracer.start_as_current_span("my-span"):
    ...     pass

Prometheus metrics (module-level singletons):
    >>> from aerocloud.observability import render_duration, render_total, gpu_memory_used
    >>> render_duration.observe(2.3)
    >>> render_total.labels(status="success").inc()
    >>> gpu_memory_used.set(512_000_000)

References:
    - .planning/phases/12-production-v1/12-04-PLAN.md (PROD-18, PROD-19)
    - .planning/phases/01-foundation/01-CONTEXT.md D-28
    - T-12-04-01: span attributes must not contain PII or secrets
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import Counter, Gauge, Histogram

_INITIALIZED: bool = False

# ---------------------------------------------------------------------------
# Prometheus metric singletons (PROD-19)
# These are created once at module import time — prometheus_client pattern.
# ---------------------------------------------------------------------------

render_duration: Histogram = Histogram(
    "aerocloud_render_duration_seconds",
    "End-to-end render latency",
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
)

render_total: Counter = Counter(
    "aerocloud_renders_total",
    "Total renders by status",
    labelnames=["status"],
)

gpu_memory_used: Gauge = Gauge(
    "aerocloud_gpu_memory_used_bytes",
    "Current GPU memory usage in bytes",
)


# ---------------------------------------------------------------------------
# OpenTelemetry initializer (PROD-18)
# ---------------------------------------------------------------------------


def init_tracing(
    service_name: str = "aerocloud-engine",
    otlp_endpoint: str | None = None,
) -> None:
    """Initialize the global OpenTelemetry TracerProvider.

    Idempotent: subsequent calls are no-ops (the first call wins).

    Args:
        service_name: OTel ``service.name`` resource attribute.
        otlp_endpoint: gRPC endpoint for the OTLP collector, e.g.
            ``"http://otel-collector:4317"``.  When ``None`` (default) no
            span processor is attached — equivalent to the Phase 1 NoOp mode.

    Security note (T-12-04-01):
        Span attributes added by callers must contain only operational data
        (latency, status, task_id).  PII and API keys must never appear in
        spans.
    """
    global _INITIALIZED  # noqa: PLW0603
    if _INITIALIZED:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)

    if otlp_endpoint is not None:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _INITIALIZED = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given instrumentation name.

    Auto-initializes in NoOp mode if :func:`init_tracing` was not called yet.
    """
    if not _INITIALIZED:
        init_tracing()
    return trace.get_tracer(name)


def _reset_tracing() -> None:
    """Reset the module-level initialization flag and OTel global state.

    **Test-only helper.**  Allows tests to call :func:`init_tracing` multiple
    times within the same process without state leaking between test cases.
    Do not call this in production code.

    Internals: opentelemetry-api (≥ 1.20) protects the global TracerProvider
    slot with a ``Once`` sentinel (``_TRACER_PROVIDER_SET_ONCE``).  We reset
    both the provider reference and that sentinel's ``_done`` flag so the next
    :func:`init_tracing` call can install a fresh provider.
    """
    global _INITIALIZED  # noqa: PLW0603
    _INITIALIZED = False

    import opentelemetry.trace as _tm  # local alias to avoid shadowing module-level `trace`

    # Reset the provider reference.  These attributes are private internals of
    # the opentelemetry-api package; we use setattr/getattr to avoid mypy
    # attr-defined errors while remaining explicit about intent.
    if hasattr(_tm, "_TRACER_PROVIDER"):
        setattr(_tm, "_TRACER_PROVIDER", None)

    # Reset the Once sentinel so set_tracer_provider() is allowed again.
    if hasattr(_tm, "_TRACER_PROVIDER_SET_ONCE"):
        once = getattr(_tm, "_TRACER_PROVIDER_SET_ONCE")
        if hasattr(once, "_done"):
            once._done = False  # noqa: SLF001  # private attr of Once — intentional test reset
