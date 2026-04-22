"""Render route: POST /render and GET /render/{task_id}/progress (PROD-07, PROD-08).

Design decisions:
    - POST /render: Validates RenderRequest, dispatches Celery task to realtime queue,
      returns 202 with task_id. No synchronous rendering in request handler.
    - GET /render/{task_id}/progress: SSE stream from Redis pub/sub channel
      'render:progress:{task_id}'. Terminates on SUCCESS/FAILURE status event.
      Ping every 15 seconds keeps the connection alive for slow renders.
    - No CORSMiddleware (D-18, CLAUDE.md §12 — server-to-server only).

Security:
    T-12-05-02 (DoS): Rate limited at 10/minute per IP via slowapi (wired in app.py).
    T-12-05-04 (DoS): SSE stream terminates on SUCCESS/FAILURE; ping timeout disconnects
        abandoned streams.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

import redis.asyncio as redis_async
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from aerocloud.config import settings
from aerocloud.models.api import RenderRequest
from aerocloud_worker.celery_app import app as celery_app

log = logging.getLogger(__name__)

router = APIRouter(prefix="/render", tags=["render"])

# Stages that signal end-of-stream
_TERMINAL_STAGES = frozenset({"done", "failed", "success"})


# ---------------------------------------------------------------------------
# POST /render
# ---------------------------------------------------------------------------


@router.post("", status_code=202, response_class=JSONResponse)
async def post_render(body: RenderRequest) -> dict[str, str]:
    """Dispatch a render job to the Celery realtime queue (PROD-07).

    Returns 202 Accepted with the Celery task ID immediately.
    The client polls /render/{task_id}/progress via SSE for updates.
    """
    task = celery_app.send_task(
        "aerocloud_worker.tasks.render.render_task",
        args=[body.model_dump()],
        queue="realtime",
    )
    log.info("render_task dispatched", extra={"task_id": task.id})
    return {"task_id": task.id}


# ---------------------------------------------------------------------------
# GET /render/{task_id}/progress  — SSE stream
# ---------------------------------------------------------------------------


async def _progress_generator(task_id: str) -> AsyncGenerator[dict[str, str], None]:
    """Async generator that yields SSE events from Redis pub/sub (PROD-08).

    Channel: render:progress:{task_id}
    Terminates when stage is 'done', 'failed', or 'success'.
    """
    channel = f"render:progress:{task_id}"
    client = redis_async.from_url(settings.redis_url, decode_responses=False)
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

            stage = payload.get("stage", "")
            if stage in _TERMINAL_STAGES:
                break
    finally:
        await pubsub.unsubscribe(channel)
        await client.aclose()


@router.get("/{task_id}/progress")
async def get_render_progress(task_id: str) -> EventSourceResponse:
    """Stream SSE progress events for a render task (PROD-08).

    Client subscribes once after POST /render returns 202.
    Stream terminates on terminal stage (done/failed/success).
    Ping every 15 seconds prevents proxy timeouts.
    """
    return EventSourceResponse(
        _progress_generator(task_id),
        ping=15,
    )
