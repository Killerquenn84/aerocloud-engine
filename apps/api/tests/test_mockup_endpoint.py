"""Tests for POST /mockup/render (Sprint P23, Phase B, Scenario 11).

BDD Scenario 11:
    Gegeben ein gueltiger Request mit psd_url + design_url
    Wenn POST /mockup/render aufgerufen wird
    Dann wird HTTP 202 zurueckgegeben
    Und task_id ist im Response
    Und Celery-Task "mockup.render" wurde dispatcht
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

VALID_PAYLOAD: dict[str, object] = {
    "psd_url": "https://example.com/template.psd",
    "design_url": "https://example.com/wordcloud.png",
    "layer_name": "WORDCLOUD",
    "output_format": "png",
}


def _make_client() -> TestClient:
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=True)


def test_post_mockup_render_returns_202_with_task_id() -> None:
    """POST /mockup/render with valid body -> 202 + task_id (UUID)."""
    mock_task = MagicMock()
    mock_task.id = str(uuid.uuid4())

    with patch("aerocloud_api.routes.mockup.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        response = client.post("/mockup/render", json=VALID_PAYLOAD)

    assert response.status_code == 202
    body = response.json()
    assert "task_id" in body
    # task_id must be parseable as UUID
    uuid.UUID(body["task_id"])


def test_post_mockup_render_dispatches_celery_task() -> None:
    """POST /mockup/render must dispatch 'mockup.render' on realtime queue."""
    mock_task = MagicMock()
    mock_task.id = "task-abc"

    with patch("aerocloud_api.routes.mockup.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        client.post("/mockup/render", json=VALID_PAYLOAD)

    mock_celery.send_task.assert_called_once()
    call_args = mock_celery.send_task.call_args
    assert call_args[0][0] == "mockup.render"
    kwargs = call_args[1]
    assert kwargs.get("queue") == "realtime"


def test_post_mockup_render_forwards_request_dict() -> None:
    """POST /mockup/render must forward the validated request dict as task args."""
    mock_task = MagicMock()
    mock_task.id = "task-xyz"

    with patch("aerocloud_api.routes.mockup.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        client.post("/mockup/render", json=VALID_PAYLOAD)

    call_args = mock_celery.send_task.call_args
    dispatched = call_args[1]["args"][0]
    assert dispatched["psd_url"] == VALID_PAYLOAD["psd_url"]
    assert dispatched["design_url"] == VALID_PAYLOAD["design_url"]
    assert dispatched["layer_name"] == VALID_PAYLOAD["layer_name"]


def test_post_mockup_render_omits_layer_name_for_auto_detect() -> None:
    """P24: when layer_name is omitted, route passes None so engine auto-detects."""
    mock_task = MagicMock()
    mock_task.id = "task-default"
    payload = {
        "psd_url": "https://example.com/template.psd",
        "design_url": "https://example.com/wordcloud.png",
    }

    with patch("aerocloud_api.routes.mockup.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_task
        client = _make_client()
        response = client.post("/mockup/render", json=payload)

    assert response.status_code == 202
    dispatched = mock_celery.send_task.call_args[1]["args"][0]
    assert dispatched["layer_name"] is None


def test_post_mockup_render_missing_psd_url_returns_422() -> None:
    """POST /mockup/render without psd_url -> 422."""
    payload = dict(VALID_PAYLOAD)
    del payload["psd_url"]

    with patch("aerocloud_api.routes.mockup.celery_app"):
        client = _make_client()
        response = client.post("/mockup/render", json=payload)

    assert response.status_code == 422


def test_post_mockup_render_missing_design_url_returns_422() -> None:
    """POST /mockup/render without design_url -> 422."""
    payload = dict(VALID_PAYLOAD)
    del payload["design_url"]

    with patch("aerocloud_api.routes.mockup.celery_app"):
        client = _make_client()
        response = client.post("/mockup/render", json=payload)

    assert response.status_code == 422


def test_post_mockup_render_invalid_url_scheme_returns_422() -> None:
    """Non-http(s) URLs must be rejected (SSRF guard)."""
    payload = {**VALID_PAYLOAD, "psd_url": "file:///etc/passwd"}

    with patch("aerocloud_api.routes.mockup.celery_app"):
        client = _make_client()
        response = client.post("/mockup/render", json=payload)

    assert response.status_code == 422
