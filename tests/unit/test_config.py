"""Verifies pydantic-settings loads config from environment variables."""

from __future__ import annotations

import pytest

from aerocloud.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert "postgresql://" in s.database_url
    assert "redis://" in s.redis_url
    assert s.seed == 42
    assert s.log_level == "INFO"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("SEED", "999")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    s = Settings()
    assert s.database_url == "postgresql://test:test@localhost:5432/test"
    assert s.seed == 999
    assert s.log_level == "DEBUG"


def test_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("database_url", "postgresql://lowercase@localhost/db")
    s = Settings()
    assert "lowercase" in s.database_url
