"""Tests for the mockup.render Celery task (Sprint P23, Phase B).

Covers BDD Scenarios 10, 11 (worker side):
    - Cache HIT: identical inputs return cached output_url without invoking MockupEngine
    - Cache MISS: MockupEngine.render is called, result written to Redis cache
    - Progress events published to mockup:progress:{task_id}
    - SUCCESS event includes output_url
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_VALID_REQUEST: dict[str, Any] = {
    "psd_url": "https://example.com/template.psd",
    "design_url": "https://example.com/wordcloud.png",
    "layer_name": "WORDCLOUD",
    "output_format": "png",
}


def _import_task() -> Any:
    import importlib  # noqa: PLC0415

    return importlib.import_module("aerocloud_worker.tasks.mockup")


def _make_mock_redis(cache_value: bytes | None = None) -> MagicMock:
    mock = MagicMock()
    mock.publish = MagicMock(return_value=0)
    mock.get = MagicMock(return_value=cache_value)
    mock.set = MagicMock(return_value=True)
    return mock


def _fake_psd_bytes() -> bytes:
    return b"\x89PSDFAKE" + b"\x00" * 64


def _fake_design_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _patch_httpx_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make httpx.Client().get(url).content return deterministic bytes."""

    def fake_get(self: Any, url: str, *_a: Any, **_kw: Any) -> Any:  # noqa: ARG001
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith(".psd"):
            resp.content = _fake_psd_bytes()
        else:
            resp.content = _fake_design_bytes()
        return resp

    import httpx  # noqa: PLC0415

    monkeypatch.setattr(httpx.Client, "get", fake_get)


def test_mockup_task_registered_with_correct_name() -> None:
    mod = _import_task()
    assert hasattr(mod, "mockup_render_task")
    assert mod.mockup_render_task.name == "mockup.render"


def test_mockup_task_cache_hit_skips_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 10: cached URL returned, MockupEngine.render NOT invoked."""
    mod = _import_task()
    task = mod.mockup_render_task

    cached_url = "https://example.com/mockups/cached.png"
    mock_redis = _make_mock_redis(cache_value=cached_url.encode("utf-8"))

    _patch_httpx_download(monkeypatch)

    fake_engine = MagicMock()
    fake_engine.render = MagicMock()

    with (
        patch("aerocloud_worker.tasks.mockup.redis_lib") as mock_redis_lib,
        patch("aerocloud_worker.tasks.mockup.MockupEngine", return_value=fake_engine),
    ):
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        result = task.apply(args=[_VALID_REQUEST], task_id="cache-hit-1").get()

    assert result["output_url"] == cached_url
    fake_engine.render.assert_not_called()


def test_mockup_task_cache_miss_invokes_renderer_and_caches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Scenario 10 inverse: cache MISS -> MockupEngine.render runs + cache write."""
    mod = _import_task()
    task = mod.mockup_render_task

    mock_redis = _make_mock_redis(cache_value=None)
    _patch_httpx_download(monkeypatch)

    fake_image = MagicMock()
    fake_image.save = MagicMock()
    fake_engine = MagicMock()
    fake_engine.render = MagicMock(return_value=fake_image)

    output_dir = tmp_path / "mockups"
    monkeypatch.setenv("MOCKUP_OUTPUT_DIR", str(output_dir))

    with (
        patch("aerocloud_worker.tasks.mockup.redis_lib") as mock_redis_lib,
        patch("aerocloud_worker.tasks.mockup.MockupEngine", return_value=fake_engine),
    ):
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        result = task.apply(args=[_VALID_REQUEST], task_id="cache-miss-1").get()

    fake_engine.render.assert_called_once()
    fake_image.save.assert_called_once()
    # Cache write happened with TTL
    assert mock_redis.set.called
    set_kwargs = mock_redis.set.call_args.kwargs
    set_args = mock_redis.set.call_args.args
    # Either kwargs={'ex': ...} or positional — accept both, but ex must be in there
    ex_value = set_kwargs.get("ex")
    if ex_value is None and len(set_args) >= 3:
        ex_value = set_args[2]
    assert ex_value is not None and ex_value > 0
    assert "output_url" in result


def test_mockup_task_publishes_progress_to_redis_channel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Progress events published to mockup:progress:{task_id}."""
    mod = _import_task()
    task = mod.mockup_render_task

    mock_redis = _make_mock_redis(cache_value=None)
    _patch_httpx_download(monkeypatch)

    fake_image = MagicMock()
    fake_image.save = MagicMock()
    fake_engine = MagicMock(); fake_engine.render = MagicMock(return_value=fake_image)
    monkeypatch.setenv("MOCKUP_OUTPUT_DIR", str(tmp_path / "mockups"))

    task_id = "progress-task-id"
    with (
        patch("aerocloud_worker.tasks.mockup.redis_lib") as mock_redis_lib,
        patch("aerocloud_worker.tasks.mockup.MockupEngine", return_value=fake_engine),
    ):
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task.apply(args=[_VALID_REQUEST], task_id=task_id).get()

    expected_channel = f"mockup:progress:{task_id}"
    publish_calls = mock_redis.publish.call_args_list
    channels = [c[0][0] for c in publish_calls]
    assert expected_channel in channels

    statuses = [json.loads(c[0][1]).get("status") for c in publish_calls]
    assert "started" in statuses
    assert "success" in statuses


def test_mockup_task_success_event_carries_output_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Final success event contains an output_url field."""
    mod = _import_task()
    task = mod.mockup_render_task

    mock_redis = _make_mock_redis(cache_value=None)
    _patch_httpx_download(monkeypatch)

    fake_image = MagicMock(); fake_image.save = MagicMock()
    fake_engine = MagicMock(); fake_engine.render = MagicMock(return_value=fake_image)
    monkeypatch.setenv("MOCKUP_OUTPUT_DIR", str(tmp_path / "mockups"))

    with (
        patch("aerocloud_worker.tasks.mockup.redis_lib") as mock_redis_lib,
        patch("aerocloud_worker.tasks.mockup.MockupEngine", return_value=fake_engine),
    ):
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task.apply(args=[_VALID_REQUEST], task_id="success-payload").get()

    payloads = [json.loads(c[0][1]) for c in mock_redis.publish.call_args_list]
    success_events = [p for p in payloads if p.get("status") == "success"]
    assert success_events, "Expected at least one success event"
    assert "output_url" in success_events[-1]
