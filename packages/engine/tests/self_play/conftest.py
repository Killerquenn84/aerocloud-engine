"""Shared fixtures for self_play tests."""

from __future__ import annotations

import pytest


@pytest.fixture()
def default_config_kwargs() -> dict:
    """Return a minimal valid SelfPlayConfig kwargs dict."""
    return {}  # all fields have defaults
