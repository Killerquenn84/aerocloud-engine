"""Mockup route: POST /mockup/render + GET /mockup/render/{task_id}/progress.

Sprint P23, Phase B — open-source Mockup-Engine (psd-tools + Pillow).

Design decisions:
    - POST /mockup/render: Validates MockupRenderRequest, dispatches Celery task
      'mockup.render' to the realtime queue, returns 202 with task_id.
    - GET /mockup/render/{task_id}/progress: SSE stream from Redis pub/sub channel
      'mockup:progress:{task_id}'. Terminates on status='success' or 'failure'.
      Ping every 15 seconds keeps long-polling proxies happy.
    - Follows the exact pattern from routes/render.py for consistency.

Security:
    T-P23-01 (DoS): Rate limited at 10/minute per IP via slowapi (analog /render).
    T-P23-02 (SSRF): MockupRenderRequest pydantic validator rejects file:// URLs.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis_async
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from aerocloud.config import settings
from aerocloud.models.api import MockupRenderRequest
from aerocloud_api.middleware.rate_limit import limiter
from aerocloud_worker.celery_app import app as celery_app

log = logging.getLogger(__name__)

router = APIRouter(prefix="/mockup", tags=["mockup"])

# Terminal statuses that end the SSE stream
_TERMINAL_STATUSES = frozenset({"success", "failure"})


# ---------------------------------------------------------------------------
# POST /mockup/render
# ---------------------------------------------------------------------------


@router.post("/render", status_code=202, response_class=JSONResponse)
@limiter.limit("10/minute")
async def post_mockup_render(  # noqa: ARG001
    request: Request, body: MockupRenderRequest
) -> dict[str, str]:
    """Dispatch a mockup render job to the Celery realtime queue (Scenario 11).

    Returns 202 Accepted with the Celery task ID immediately. The client polls
    /mockup/render/{task_id}/progress via SSE for updates.
    """
    task = celery_app.send_task(
        "mockup.render",
        args=[body.model_dump()],
        queue="realtime",
    )
    log.info("mockup_render dispatched", extra={"task_id": task.id})
    return {"task_id": task.id}


# ---------------------------------------------------------------------------
# GET /mockup/render/{task_id}/progress — SSE stream
# ---------------------------------------------------------------------------


async def _progress_generator(task_id: str) -> AsyncGenerator[dict[str, str], None]:
    """Yield SSE events from Redis pub/sub channel mockup:progress:{task_id}.

    Terminates when payload status is in _TERMINAL_STATUSES ('success' or 'failure').
    """
    channel = f"mockup:progress:{task_id}"
    client = redis_async.from_url(settings.redis_url, decode_responses=False)  # type: ignore[no-untyped-call]
    pubsub = client.pubsub()

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                log.warning("SSE: invalid JSON from Redis channel %s", channel)
                continue

            yield {"data": json.dumps(payload)}

            status = payload.get("status", "")
            if status in _TERMINAL_STATUSES:
                break
    finally:
        await pubsub.unsubscribe(channel)
        await client.aclose()


@router.get("/render/{task_id}/progress")
async def get_mockup_progress(task_id: str) -> EventSourceResponse:
    """Stream SSE progress events for a mockup render task (Scenario 12).

    Client subscribes once after POST /mockup/render returns 202.
    Stream terminates on terminal status (success/failure). Ping every 15s.
    """
    return EventSourceResponse(
        _progress_generator(task_id),
        ping=15,
    )
