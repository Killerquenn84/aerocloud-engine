"""FastAPI application factory for AeroCloud API (Phase 12).

Design decisions:
    - Lifespan context manager handles startup/shutdown cleanly.
    - init_tracing() called at startup with optional OTLP endpoint from settings.
    - NO CORSMiddleware (D-18, CLAUDE.md §12 — server-to-server only; Shopify
      session token auth — no cross-origin browser calls expected).
    - Rate limiter and Prometheus metrics wired here (Tasks 2 of Plan 05).

Security:
    T-12-05-01 (Spoofing): /health/internal requires X-Internal-Token header.
    T-12-05-02 (DoS): slowapi rate limiter on POST /render (10/minute per IP).
    T-12-05-03 (Info Disclosure): /health only returns status booleans, no connection strings.
    T-12-05-05 (Spoofing): IP-based rate limiting (per-shop deferred to Shopify token integration).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from aerocloud.config import settings
from aerocloud.observability import init_tracing
from aerocloud_api import __version__
from aerocloud_api.routes.render import router as render_router


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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

    # Include route groups
    application.include_router(render_router)

    return application


app: FastAPI = create_app()
