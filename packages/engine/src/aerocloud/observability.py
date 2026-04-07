"""OpenTelemetry SDK initialization.

Phase 1: SDK is initialized with a NoOp exporter. The real OTLP exporter is
wired up in Phase 12 when a collector is deployed alongside the engine.

Usage:
    >>> from aerocloud.observability import init_tracing
    >>> init_tracing(service_name="aerocloud-engine")
    >>> tracer = init_tracing.get_tracer(__name__)
    >>> with tracer.start_as_current_span("my-span"):
    ...     pass

References:
    - .planning/research/ARCHITECTURE.md §8 (observability)
    - .planning/phases/01-foundation/01-CONTEXT.md D-28
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_INITIALIZED: bool = False


def init_tracing(service_name: str = "aerocloud-engine") -> None:
    """Initialize the global OpenTelemetry TracerProvider.

    Idempotent: subsequent calls are no-ops. In Phase 1 this uses a NoOp
    exporter; Phase 12 will attach an OTLP exporter pointing at the cluster
    collector.
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
    trace.set_tracer_provider(provider)

    _INITIALIZED = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given instrumentation name."""
    if not _INITIALIZED:
        init_tracing()
    return trace.get_tracer(name)
