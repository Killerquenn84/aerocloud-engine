"""FastAPI application factory for AeroCloud API (Phase 12).

Design decisions:
    - Lifespan context manager handles startup/shutdown cleanly.
    - init_tracing() called at startup with optional OTLP endpoint from settings.
    - NO CORSMiddleware (D-18, CLAUDE.md §12 — server-to-server only; Shopify
      session token auth — no cross-origin browser calls expected).
    - Rate limiter wired to app.state and exception handler (Task 2 of Plan 05).
    - Prometheus auto-instrumentation called after all routers are included (D-20).

Security:
    T-12-05-01 (Spoofing): /health/internal requires X-Internal-Token header.
    T-12-05-02 (DoS): slowapi rate limiter on POST /render (10/minute per IP).
    T-12-05-03 (Info Disclosure): /health only returns status booleans, no connection strings.
    T-12-05-05 (Spoofing): IP-based rate limiting (per-shop deferred to Shopify token integration).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from aerocloud.config import settings
from aerocloud.observability import init_tracing
from aerocloud_api import __version__
from aerocloud_api.metrics import setup_metrics
from aerocloud_api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from aerocloud_api.routes.health import router as health_router
from aerocloud_api.routes.mockup import router as mockup_router
from aerocloud_api.routes.render import router as render_router

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Startup and shutdown lifecycle handler."""
    # Startup: initialise distributed tracing (NoOp if no endpoint configured)
    init_tracing(otlp_endpoint=settings.otlp_endpoint)

    yield

    # Shutdown: nothing to clean up at this layer (Redis connections are per-request)


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="AeroCloud Engine API",
        version=__version__,
        description="HTTP surface for the AeroCloud word cloud rendering engine.",
        lifespan=lifespan,
    )

    # Wire rate limiter (T-12-05-02)
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    application.add_middleware(SlowAPIMiddleware)

    # Include route groups
    application.include_router(render_router)
    application.include_router(mockup_router)
    application.include_router(health_router)

    # Wire Prometheus auto-instrumentation (D-20) — after routers so all routes instrumented
    setup_metrics(application)

    return application


app: FastAPI = create_app()
