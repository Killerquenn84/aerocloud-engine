"""Prometheus FastAPI instrumentation setup (PROD-19, D-20).

Design decisions:
    - prometheus-fastapi-instrumentator auto-instruments all routes and exposes
      /metrics endpoint with default HTTP request duration / count histograms.
    - Called from app.py lifespan on startup after routers are included.
    - The render_duration and render_total Prometheus singletons from
      aerocloud.observability are used directly by the Celery worker; the
      instrumentator here adds HTTP-level metrics on top.

Security:
    /metrics is not protected by auth — Prometheus scrapes from internal network only.
    CORS is disabled globally (D-18), so /metrics is not accessible cross-origin.
"""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app: FastAPI) -> None:
    """Wire Prometheus auto-instrumentation and expose /metrics endpoint (D-20).

    Call this after all routers are included so all routes are instrumented.
    The /metrics endpoint is added by instrumentator.expose(app).
    """
    Instrumentator().instrument(app).expose(app)
