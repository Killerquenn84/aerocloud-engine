"""Health endpoints: GET /health (public) + GET /health/internal (authenticated).

Design decisions (PROD-17, D-09):
    - GET /health: Public liveness probe. Returns {"status": "ok", "version": __version__}.
      No auth required. Not rate limited. Used by load balancers.
    - GET /health/internal: Authenticated readiness probe. Checks Postgres (SELECT 1),
      Redis (PING), and GPU availability (torch.cuda.is_available()).
      Requires X-Internal-Token header matching settings.internal_health_token.

Security:
    T-12-05-01 (Spoofing): X-Internal-Token header auth on /health/internal.
    T-12-05-03 (Info Disclosure): Returns only status booleans ('ok'/'unavailable'),
        never connection strings, error messages, or credentials.
"""

from __future__ import annotations

import logging

import asyncpg
import redis.asyncio as redis_async
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from aerocloud.config import settings
from aerocloud_api import __version__

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# GET /health — public liveness probe
# ---------------------------------------------------------------------------


@router.get("/health")
async def get_health() -> dict[str, str]:
    """Public liveness probe. Returns status and version (PROD-17).

    Not rate limited — infrastructure probes must always succeed.
    No auth required — safe to expose to load balancers.
    """
    return {"status": "ok", "version": __version__}


# ---------------------------------------------------------------------------
# Sprint P26 — split liveness / readiness
# ---------------------------------------------------------------------------


@router.get("/health/live")
async def get_health_live() -> dict[str, str]:
    """P26 scenario 13: pure liveness probe — always 200 while the process runs.

    Used by Kubernetes ``livenessProbe`` / container orchestrators that should
    only restart the process if Python itself is dead. Does NOT check Redis /
    Postgres — those go through ``/health/ready``.
    """
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def get_health_ready() -> JSONResponse:
    """P26 scenario 13: readiness probe.

    Returns 200 if Redis ping AND Postgres ping succeed, otherwise 503 with a
    per-dependency breakdown. Used by ``readinessProbe`` to gate traffic.
    No auth required: dependency status itself leaks nothing sensitive (only
    'up' / 'down'), unlike ``/health/internal`` which is preserved as the
    detailed-but-authenticated variant.
    """
    redis_state, postgres_state = await _check_redis(), await _check_postgres()
    redis_ok = redis_state == "ok"
    postgres_ok = postgres_state == "ok"
    overall_ok = redis_ok and postgres_ok
    body = {
        "status": "ok" if overall_ok else "unavailable",
        "dependencies": {
            "redis": "up" if redis_ok else "down",
            "postgres": "up" if postgres_ok else "down",
        },
    }
    return JSONResponse(status_code=200 if overall_ok else 503, content=body)


# ---------------------------------------------------------------------------
# GET /health/internal — authenticated readiness probe
# ---------------------------------------------------------------------------


async def _check_postgres() -> str:
    """Check PostgreSQL connectivity via SELECT 1. Returns 'ok' or 'unavailable'."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return "ok"
    except Exception:
        log.warning("health/internal: postgres check failed")
        return "unavailable"


async def _check_redis() -> str:
    """Check Redis connectivity via PING. Returns 'ok' or 'unavailable'."""
    client = redis_async.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    try:
        await client.ping()
        return "ok"
    except Exception:
        log.warning("health/internal: redis check failed")
        return "unavailable"
    finally:
        await client.aclose()


def _check_gpu() -> str:
    """Check GPU availability via torch. Returns 'available' or 'unavailable'.

    torch is imported inline to avoid CUDA context creation before prefork
    (same pattern as render_task — CUDA fork-safety).
    """
    try:
        import torch  # noqa: PLC0415 — intentional inline import for CUDA fork safety

        return "available" if torch.cuda.is_available() else "unavailable"
    except Exception:
        return "unavailable"


@router.get("/health/internal")
async def get_health_internal(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> JSONResponse:
    """Authenticated readiness probe. Checks Postgres, Redis, GPU (PROD-17).

    Auth: X-Internal-Token header must match settings.internal_health_token.
    Returns status strings only — no connection strings or credentials (T-12-05-03).
    """
    # Auth check (T-12-05-01)
    if x_internal_token is None or x_internal_token != settings.internal_health_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Run checks concurrently
    import asyncio  # noqa: PLC0415

    postgres_status, redis_status = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
    )
    gpu_status = _check_gpu()

    overall = "ok" if postgres_status == "ok" and redis_status == "ok" else "degraded"

    return JSONResponse(
        content={
            "status": overall,
            "postgres": postgres_status,
            "redis": redis_status,
            "gpu": gpu_status,
        }
    )
