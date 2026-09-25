"""Tests for GET /mockup/render/{task_id}/progress SSE-Stream (Scenario 12).

BDD Scenario 12:
    Gegeben ein laufender mockup.render Task
    Wenn GET /mockup/render/{task_id}/progress aufgerufen wird
    Dann wird SSE-Stream mit Events {status, progress%, output_url} gestreamt
    Und endet mit SUCCESS-Event inkl. output_url
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=True)


def test_get_mockup_progress_returns_event_stream_content_type() -> None:
    """SSE stream returns text/event-stream Content-Type."""
    with patch("aerocloud_api.routes.mockup.redis_async") as mock_redis_module:
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()

        async def _listen() -> object:  # type: ignore[return]
            yield {
                "type": "message",
                "data": json.dumps(
                    {
                        "status": "success",
                        "progress": 100,
                        "output_url": "https://example.com/mockups/abc.png",
                    }
                ).encode(),
            }

        mock_pubsub.listen = _listen
        mock_conn = MagicMock()
        mock_conn.pubsub.return_value = mock_pubsub
        mock_conn.aclose = AsyncMock()
        mock_redis_module.from_url.return_value = mock_conn

        client = _make_client()
        with client.stream("GET", "/mockup/render/some-task-id/progress") as resp:
            assert "text/event-stream" in resp.headers["content-type"]


def test_get_mockup_progress_streams_progress_and_complete_events() -> None:
    """SSE stream emits multiple progress events and terminates on success."""
    progress_events = [
        {"status": "started", "progress": 0},
        {"status": "downloading", "progress": 10},
        {"status": "rendering", "progress": 70},
        {
            "status": "success",
            "progress": 100,
            "output_url": "https://example.com/mockups/abc.png",
        },
    ]

    with patch("aerocloud_api.routes.mockup.redis_async") as mock_redis_module:
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()

        async def _listen() -> object:  # type: ignore[return]
            for ev in progress_events:
                yield {"type": "message", "data": json.dumps(ev).encode()}

        mock_pubsub.listen = _listen
        mock_conn = MagicMock()
        mock_conn.pubsub.return_value = mock_pubsub
        mock_conn.aclose = AsyncMock()
        mock_redis_module.from_url.return_value = mock_conn

        client = _make_client()
        with client.stream("GET", "/mockup/render/task-1/progress") as resp:
            body = b"".join(resp.iter_bytes())

    text = body.decode("utf-8")
    # All four payloads should appear in the SSE body
    assert "started" in text
    assert "rendering" in text
    assert "success" in text
    assert "output_url" in text


def test_get_mockup_progress_terminates_on_failure() -> None:
    """SSE stream terminates when status == 'failure'."""
    with patch("aerocloud_api.routes.mockup.redis_async") as mock_redis_module:
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()

        emitted: list[dict[str, object]] = []

        async def _listen() -> object:  # type: ignore[return]
            ev = {"status": "failure", "progress": 0, "error": "boom"}
            emitted.append(ev)
            yield {"type": "message", "data": json.dumps(ev).encode()}
            # Following event must never be reached because stream terminates
            ev2 = {"status": "ghost", "progress": 0}
            emitted.append(ev2)
            yield {"type": "message", "data": json.dumps(ev2).encode()}

        mock_pubsub.listen = _listen
        mock_conn = MagicMock()
        mock_conn.pubsub.return_value = mock_pubsub
        mock_conn.aclose = AsyncMock()
        mock_redis_module.from_url.return_value = mock_conn

        client = _make_client()
        with client.stream("GET", "/mockup/render/task-x/progress") as resp:
            body = b"".join(resp.iter_bytes())

    text = body.decode("utf-8")
    assert "failure" in text
    assert "ghost" not in text
