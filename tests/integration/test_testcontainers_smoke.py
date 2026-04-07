"""Integration smoke test — spins up Postgres + Redis via testcontainers.

This test is opt-in via ``-m integration``. Requires Docker daemon running
on the host.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_postgres_reachable() -> None:
    """Starts a postgres container and verifies it's reachable."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        assert "postgresql" in url or "postgres" in url


def test_redis_reachable() -> None:
    """Starts a redis container and verifies it's reachable."""
    try:
        from testcontainers.redis import RedisContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with RedisContainer("redis:7-alpine") as rc:
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(6379)
        assert host
        assert int(port) > 0
