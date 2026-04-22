"""Rate limiting setup via slowapi (PROD-16, D-10).

Design decisions:
    - Redis-backed token bucket: limiter uses settings.redis_url for distributed
      state across multiple API replicas (not in-memory, which breaks multi-process).
    - 10 requests/minute per IP on POST /render. IP-based (per-shop limiting deferred
      to Shopify session token integration per T-12-05-05 threat acceptance).
    - /health and /metrics are NOT rate limited — infrastructure probes must always succeed.
    - Rate limit exceeded handler returns JSON 429 with error message.

Security:
    T-12-05-02 (DoS): slowapi rate limiter on POST /render at 10/minute per IP.
    T-12-05-05 (Spoofing): IP-based rate limiting accepted; per-shop limiting deferred.
"""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from aerocloud.config import settings

# Module-level limiter singleton — imported by app.py and routes/render.py.
limiter: Limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    # Default limit applied globally; per-route limits override via decorator.
    # /health and /metrics intentionally have no @limiter.limit decorator.
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return a JSON 429 response when the rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": str(exc.detail),
        },
    )
