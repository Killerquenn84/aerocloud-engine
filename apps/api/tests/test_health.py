"""Sprint P26 — /health/live + /health/ready (scenario 13)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /health/live — always 200
# ---------------------------------------------------------------------------


def test_health_live_returns_200_no_auth() -> None:
    response = _client().get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /health/ready — 200 if all deps up, 503 otherwise
# ---------------------------------------------------------------------------


def _mock_postgres_ok():
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    return AsyncMock(return_value=mock_conn)


def _mock_redis_ok():
    mock_redis_conn = AsyncMock()
    mock_redis_conn.ping = AsyncMock(return_value=True)
    mock_redis_conn.aclose = AsyncMock()
    return MagicMock(return_value=mock_redis_conn)


def test_health_ready_returns_200_when_all_up() -> None:
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_asyncpg.connect = _mock_postgres_ok()
        mock_redis.from_url = _mock_redis_ok()
        response = _client().get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {"redis": "up", "postgres": "up"}


def test_health_ready_returns_503_when_redis_down() -> None:
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_asyncpg.connect = _mock_postgres_ok()

        mock_redis_conn = AsyncMock()
        mock_redis_conn.ping = AsyncMock(side_effect=Exception("connection refused"))
        mock_redis_conn.aclose = AsyncMock()
        mock_redis.from_url = MagicMock(return_value=mock_redis_conn)

        response = _client().get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["dependencies"]["redis"] == "down"
    assert body["dependencies"]["postgres"] == "up"


def test_health_ready_returns_503_when_postgres_down() -> None:
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("pg down"))
        mock_redis.from_url = _mock_redis_ok()
        response = _client().get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["dependencies"]["postgres"] == "down"
    assert body["dependencies"]["redis"] == "up"


# ---------------------------------------------------------------------------
# Legacy /health remains an unauthenticated 200 (alias for /health/live).
# ---------------------------------------------------------------------------


def test_legacy_health_still_returns_200() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
