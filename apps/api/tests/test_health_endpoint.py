"""Tests for GET /health and GET /health/internal (PROD-17).

TDD RED → GREEN cycle per CLAUDE.md section 8.

Scenarios:
    Given a running API
    When GET /health is called
    Then 200 is returned with {"status": "ok", "version": "0.1.0"}

    Given a running API with a valid X-Internal-Token header
    When GET /health/internal is called
    Then 200 is returned with postgres, redis, gpu status fields

    Given a running API without auth header
    When GET /health/internal is called
    Then 401 is returned

    Given a running API with wrong token
    When GET /health/internal is called
    Then 401 is returned

    Given a running API
    When GET /health is called
    Then it is NOT rate limited (no 429 on repeated calls)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    from aerocloud_api.app import app  # noqa: PLC0415

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GET /health — public liveness probe
# ---------------------------------------------------------------------------


def test_health_returns_200() -> None:
    """GET /health → 200 OK."""
    client = _make_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok() -> None:
    """GET /health body contains {"status": "ok"}."""
    client = _make_client()
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"


def test_health_returns_version() -> None:
    """GET /health body contains version string."""
    from aerocloud_api import __version__  # noqa: PLC0415

    client = _make_client()
    response = client.get("/health")
    body = response.json()
    assert body["version"] == __version__


# ---------------------------------------------------------------------------
# GET /health/internal — authenticated detailed probe
# ---------------------------------------------------------------------------


def test_health_internal_requires_auth_header() -> None:
    """GET /health/internal without X-Internal-Token → 401."""
    client = _make_client()
    response = client.get("/health/internal")
    assert response.status_code == 401


def test_health_internal_wrong_token_returns_401() -> None:
    """GET /health/internal with wrong token → 401."""
    client = _make_client()
    response = client.get("/health/internal", headers={"X-Internal-Token": "wrong-token"})
    assert response.status_code == 401


def test_health_internal_valid_token_returns_200() -> None:
    """GET /health/internal with valid token → 200 with health fields."""
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        # Mock Postgres connection: connect returns context manager with fetchval
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        # Mock Redis: ping returns True
        mock_redis_conn = AsyncMock()
        mock_redis_conn.ping = AsyncMock(return_value=True)
        mock_redis_conn.aclose = AsyncMock()
        mock_redis.from_url = MagicMock(return_value=mock_redis_conn)

        from aerocloud.config import settings  # noqa: PLC0415

        client = _make_client()
        response = client.get(
            "/health/internal",
            headers={"X-Internal-Token": settings.internal_health_token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "postgres" in body
    assert "redis" in body
    assert "gpu" in body


def test_health_internal_returns_status_strings() -> None:
    """GET /health/internal returns 'ok'/'unavailable' string values, not raw booleans."""
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        mock_redis_conn = AsyncMock()
        mock_redis_conn.ping = AsyncMock(return_value=True)
        mock_redis_conn.aclose = AsyncMock()
        mock_redis.from_url = MagicMock(return_value=mock_redis_conn)

        from aerocloud.config import settings  # noqa: PLC0415

        client = _make_client()
        response = client.get(
            "/health/internal",
            headers={"X-Internal-Token": settings.internal_health_token},
        )

    body = response.json()
    # Values must be strings, not True/False booleans (info disclosure prevention T-12-05-03)
    assert body["postgres"] in ("ok", "unavailable")
    assert body["redis"] in ("ok", "unavailable")
    assert body["gpu"] in ("available", "unavailable")


def test_health_internal_postgres_failure_returns_unavailable() -> None:
    """GET /health/internal with Postgres down → postgres: 'unavailable' but still 200."""
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("connection refused"))

        mock_redis_conn = AsyncMock()
        mock_redis_conn.ping = AsyncMock(return_value=True)
        mock_redis_conn.aclose = AsyncMock()
        mock_redis.from_url = MagicMock(return_value=mock_redis_conn)

        from aerocloud.config import settings  # noqa: PLC0415

        client = _make_client()
        response = client.get(
            "/health/internal",
            headers={"X-Internal-Token": settings.internal_health_token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "unavailable"
    assert body["redis"] == "ok"


def test_health_internal_redis_failure_returns_unavailable() -> None:
    """GET /health/internal with Redis down → redis: 'unavailable' but still 200."""
    with (
        patch("aerocloud_api.routes.health.asyncpg") as mock_asyncpg,
        patch("aerocloud_api.routes.health.redis_async") as mock_redis,
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        mock_redis_conn = AsyncMock()
        mock_redis_conn.ping = AsyncMock(side_effect=Exception("connection refused"))
        mock_redis_conn.aclose = AsyncMock()
        mock_redis.from_url = MagicMock(return_value=mock_redis_conn)

        from aerocloud.config import settings  # noqa: PLC0415

        client = _make_client()
        response = client.get(
            "/health/internal",
            headers={"X-Internal-Token": settings.internal_health_token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "ok"
    assert body["redis"] == "unavailable"
