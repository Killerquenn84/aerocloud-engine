"""Tests for POST /render and GET /render/{task_id}/progress (PROD-07, PROD-08).

TDD RED → GREEN cycle per CLAUDE.md section 8.

Scenarios:
    Given a valid RenderRequest body
    When POST /render is called
    Then 202 is returned with a task_id UUID

    Given an invalid RenderRequest (missing text)
    When POST /render is called
    Then 422 Unprocessable Entity is returned

    Given Celery is available
    When POST /render is called with a valid body
    Then render_task is dispatched with request dict

    Given a task_id
    When GET /render/{task_id}/progress is called
    Then response content-type is text/event-stream

    Given the app
    When inspecting installed middleware
    Then no CORSMiddleware is present
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYLOAD: dict[str, object] = {
    "text": "hello world",
    "shape_b64": "aGVsbG8=",  # minimal base64 (no path traversal)
    "width": 512,
    "height": 512,
    "seed": 42,
    "max_words": 50,
    "font_family": "Inter",
}


def _make_client() -> TestClient:
    """Return TestClient bound to the FastAPI app."""
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test: POST /render happy path
# ---------------------------------------------------------------------------


def test_post_render_returns_202_with_task_id() -> None:
    """POST /render with valid body → 202 + task_id."""
    mock_task = MagicMock()
    mock_task.id = "mock-task-uuid-1234"

    with patch("aerocloud_api.routes.render.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        response = client.post("/render", json=VALID_PAYLOAD)

    assert response.status_code == 202
    body = response.json()
    assert "task_id" in body
    assert body["task_id"] == "mock-task-uuid-1234"


def test_post_render_dispatches_celery_task() -> None:
    """POST /render must call celery_app.send_task with the correct task name."""
    mock_task = MagicMock()
    mock_task.id = "task-abc"

    with patch("aerocloud_api.routes.render.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        client.post("/render", json=VALID_PAYLOAD)

    mock_celery.send_task.assert_called_once()
    call_args = mock_celery.send_task.call_args
    assert call_args[0][0] == "aerocloud_worker.tasks.render.render_task"
    # Queue must be realtime
    kwargs = call_args[1]
    assert kwargs.get("queue") == "realtime"


def test_post_render_passes_request_dict_to_celery() -> None:
    """POST /render must forward the validated request dict as task args."""
    mock_task = MagicMock()
    mock_task.id = "task-xyz"

    with patch("aerocloud_api.routes.render.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        client.post("/render", json=VALID_PAYLOAD)

    call_args = mock_celery.send_task.call_args
    dispatched_dict = call_args[1]["args"][0]
    assert dispatched_dict["text"] == VALID_PAYLOAD["text"]
    assert dispatched_dict["seed"] == VALID_PAYLOAD["seed"]


# ---------------------------------------------------------------------------
# Test: POST /render validation (422)
# ---------------------------------------------------------------------------


def test_post_render_missing_text_returns_422() -> None:
    """POST /render without 'text' field → 422 Unprocessable Entity."""
    payload = dict(VALID_PAYLOAD)
    del payload["text"]

    with patch("aerocloud_api.routes.render.celery_app"):
        client = _make_client()
        response = client.post("/render", json=payload)

    assert response.status_code == 422


def test_post_render_missing_shape_b64_returns_422() -> None:
    """POST /render without 'shape_b64' field → 422 Unprocessable Entity."""
    payload = dict(VALID_PAYLOAD)
    del payload["shape_b64"]

    with patch("aerocloud_api.routes.render.celery_app"):
        client = _make_client()
        response = client.post("/render", json=payload)

    assert response.status_code == 422


def test_post_render_empty_text_returns_422() -> None:
    """POST /render with empty text → 422 (min_length=1 constraint)."""
    payload = {**VALID_PAYLOAD, "text": ""}

    with patch("aerocloud_api.routes.render.celery_app"):
        client = _make_client()
        response = client.post("/render", json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test: GET /render/{task_id}/progress SSE
# ---------------------------------------------------------------------------


def test_get_render_progress_returns_event_stream_content_type() -> None:
    """GET /render/{task_id}/progress → Content-Type: text/event-stream."""
    with patch("aerocloud_api.routes.render.redis_async") as mock_redis_module:
        mock_pubsub = MagicMock()
        # subscribe returns immediately
        mock_pubsub.subscribe = AsyncMock()
        # listen yields one progress message then stops
        async def _listen() -> object:  # type: ignore[return]
            msg: dict[str, object] = {
                "type": "message",
                "data": json.dumps({"stage": "done", "progress": 100, "task_id": "t1"}).encode(),
            }
            yield msg

        mock_pubsub.listen = _listen
        mock_conn = MagicMock()
        mock_conn.pubsub.return_value = mock_pubsub
        mock_redis_module.from_url.return_value = mock_conn

        client = _make_client()
        with client.stream("GET", "/render/some-task-id/progress") as resp:
            assert "text/event-stream" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Test: No CORS middleware (D-18)
# ---------------------------------------------------------------------------


def test_no_cors_middleware_on_app() -> None:
    """The FastAPI app must NOT include CORSMiddleware (D-18, server-to-server only)."""
    from starlette.middleware.cors import CORSMiddleware  # noqa: PLC0415

    from aerocloud_api.app import app  # noqa: PLC0415

    middleware_classes = [
        m.cls for m in app.user_middleware  # type: ignore[attr-defined]
        if hasattr(m, "cls")
    ]
    assert CORSMiddleware not in middleware_classes
