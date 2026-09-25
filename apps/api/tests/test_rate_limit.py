"""Tests for rate limiting on POST /render (PROD-16).

TDD RED → GREEN cycle per CLAUDE.md section 8.

Scenarios:
    Given a client sending 11 requests to POST /render within a minute
    When the 11th request is sent
    Then 429 Too Many Requests is returned

    Given a client calling GET /health repeatedly
    When many requests are sent
    Then no 429 is returned (health endpoint is NOT rate limited)

    Given a rate limit exceeded response
    When the response is inspected
    Then it contains an appropriate error message
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

VALID_PAYLOAD: dict[str, object] = {
    "text": "hello world",
    "shape_b64": "aGVsbG8=",
    "width": 512,
    "height": 512,
    "seed": 42,
    "max_words": 50,
    "font_family": "Inter",
}


def _make_client() -> TestClient:
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Rate limit: POST /render
# ---------------------------------------------------------------------------


def test_render_rate_limit_returns_429_after_limit() -> None:
    """POST /render returns 429 after exceeding 10/minute per IP."""
    mock_task = MagicMock()
    mock_task.id = "task-rate-test"

    with patch("aerocloud_api.routes.render.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()

        responses = [client.post("/render", json=VALID_PAYLOAD) for _ in range(15)]

    status_codes = [r.status_code for r in responses]
    # At least one response must be 429
    assert 429 in status_codes, f"Expected 429 in: {status_codes}"
    # First 10 should all be 202
    for i, code in enumerate(status_codes[:10]):
        assert code == 202, f"Request {i + 1} should be 202, got {code}"


def test_render_rate_limit_response_has_error_message() -> None:
    """429 response from rate limiter includes an error detail."""
    mock_task = MagicMock()
    mock_task.id = "task-rate-err"

    with patch("aerocloud_api.routes.render.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()

        responses = [client.post("/render", json=VALID_PAYLOAD) for _ in range(15)]

    rate_limited = [r for r in responses if r.status_code == 429]
    assert rate_limited, "No 429 response found"
    # Response must have a body (not empty)
    body = rate_limited[0].text
    assert len(body) > 0


# ---------------------------------------------------------------------------
# Health endpoint must NOT be rate limited
# ---------------------------------------------------------------------------


def test_health_not_rate_limited() -> None:
    """GET /health must not trigger rate limiting even on many calls."""
    client = _make_client()

    responses = [client.get("/health") for _ in range(20)]
    status_codes = [r.status_code for r in responses]

    assert 429 not in status_codes, f"Health endpoint unexpectedly rate limited: {status_codes}"
    assert all(code == 200 for code in status_codes)
