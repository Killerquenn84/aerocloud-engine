"""Tests for the render_task Celery task — Phase 12-03 (PROD-09, PROD-10, PROD-11).

Tests validate:
- Task registration and naming
- Task accepts RenderRequest-shaped dict and returns RenderResult-shaped dict
- torch imported inside task body only (not at module level)
- Progress published to Redis channel render:progress:{task_id}
- SoftTimeLimitExceeded handled — failure progress published, then re-raised
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RENDER_TASK_PATH = Path(__file__).parent.parent / "src" / "aerocloud_worker" / "tasks" / "render.py"

_VALID_REQUEST: dict[str, Any] = {
    "text": "hello world",
    "shape_b64": "aGVsbG8=",  # base64 "hello" — passes path traversal validator
    "width": 128,
    "height": 128,
    "seed": 42,
    "max_words": 10,
    "font_family": "Inter",
}


def _render_task_source() -> str:
    return RENDER_TASK_PATH.read_text()


def _render_task_module() -> Any:
    """Dynamically import render task module."""
    import importlib  # noqa: PLC0415

    return importlib.import_module("aerocloud_worker.tasks.render")


def _make_mock_redis() -> MagicMock:
    """Return a MagicMock that behaves like redis.Redis."""
    mock = MagicMock()
    mock.publish = MagicMock(return_value=0)
    return mock


# ---------------------------------------------------------------------------
# Task structure tests
# ---------------------------------------------------------------------------


def test_render_task_module_exists() -> None:
    """tasks/render.py must exist on disk."""
    assert RENDER_TASK_PATH.exists(), f"Missing: {RENDER_TASK_PATH}"


def test_torch_not_imported_at_module_level() -> None:
    """torch must NOT be imported at module top-level — only inside task body (CUDA fork safety)."""
    source = _render_task_source()
    tree = ast.parse(source)

    for node in ast.iter_child_nodes(tree):
        # Top-level import statements only
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                assert "torch" not in names, (
                    "torch must not be imported at module top-level (CUDA fork safety)"
                )
            elif isinstance(node, ast.ImportFrom) and node.module == "torch":
                raise AssertionError(
                    "torch must not be imported at module top-level (CUDA fork safety)"
                )


def test_render_task_registered_with_correct_name() -> None:
    """render_task must be registered as 'aerocloud_worker.tasks.render.render_task'."""
    mod = _render_task_module()
    assert hasattr(mod, "render_task"), "render_task not found in tasks/render.py"
    task = mod.render_task
    assert task.name == "aerocloud_worker.tasks.render.render_task", (
        f"Task name mismatch: {task.name}"
    )


def test_render_task_accepts_request_dict_returns_dict() -> None:
    """render_task must accept a dict and return a dict (RenderRequest/RenderResult shapes)."""
    mod = _render_task_module()
    task = mod.render_task

    mock_redis = _make_mock_redis()

    with patch("aerocloud_worker.tasks.render.redis_lib") as mock_redis_lib:
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        # task.apply() runs the task synchronously in Celery's EAGER mode
        task_result = task.apply(args=[_VALID_REQUEST])

    result = task_result.get()
    assert isinstance(result, dict), f"render_task must return a dict, got: {type(result)}"


def test_render_task_publishes_progress_to_redis_channel() -> None:
    """render_task must publish progress to render:progress:{task_id} channel."""
    mod = _render_task_module()
    task = mod.render_task

    mock_redis = _make_mock_redis()
    task_id = "test-progress-task-id"

    with patch("aerocloud_worker.tasks.render.redis_lib") as mock_redis_lib:
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task.apply(args=[_VALID_REQUEST], task_id=task_id)

    expected_channel = f"render:progress:{task_id}"
    publish_calls = mock_redis.publish.call_args_list
    assert len(publish_calls) > 0, "No redis.publish calls — progress not published"
    channels_used = [c[0][0] for c in publish_calls]
    assert expected_channel in channels_used, (
        f"Expected progress channel '{expected_channel}', got: {channels_used}"
    )


def test_render_task_publishes_started_and_done_progress() -> None:
    """render_task must publish 'started' and 'done' progress stages."""
    mod = _render_task_module()
    task = mod.render_task

    mock_redis = _make_mock_redis()
    task_id = "test-stages-task-id"

    with patch("aerocloud_worker.tasks.render.redis_lib") as mock_redis_lib:
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task.apply(args=[_VALID_REQUEST], task_id=task_id)

    publish_calls = mock_redis.publish.call_args_list
    messages = [json.loads(c[0][1]) for c in publish_calls]
    stages = [m.get("stage") for m in messages]

    assert "started" in stages, f"'started' stage not published. Stages: {stages}"
    assert "done" in stages, f"'done' stage not published. Stages: {stages}"


def test_render_task_publishes_failure_on_soft_time_limit() -> None:
    """On SoftTimeLimitExceeded, task must publish failure progress then re-raise."""
    from celery.exceptions import SoftTimeLimitExceeded  # noqa: PLC0415

    mod = _render_task_module()
    task = mod.render_task

    mock_redis = _make_mock_redis()
    task_id = "test-timeout-task-id"

    # Raise SoftTimeLimitExceeded on the 'nlp' publish call
    def publish_side_effect(channel: str, message: str) -> int:
        msg = json.loads(message)
        if msg.get("stage") == "nlp":
            raise SoftTimeLimitExceeded()
        return 0

    mock_redis.publish.side_effect = publish_side_effect

    with patch("aerocloud_worker.tasks.render.redis_lib") as mock_redis_lib:
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task_result = task.apply(args=[_VALID_REQUEST], task_id=task_id)

    # Task should have failed
    assert task_result.failed(), "Task should be in FAILED state after SoftTimeLimitExceeded"

    # Check that 'failed' stage was published
    all_messages = [json.loads(c[0][1]) for c in mock_redis.publish.call_args_list]
    stages = [m.get("stage") for m in all_messages]
    assert "failed" in stages, (
        f"'failed' stage must be published on SoftTimeLimitExceeded. Got: {stages}"
    )


def test_render_result_has_required_fields() -> None:
    """render_task return dict must contain reproducibility_id, placed_words, score, png_b64, elapsed_ms."""
    mod = _render_task_module()
    task = mod.render_task

    mock_redis = _make_mock_redis()

    with patch("aerocloud_worker.tasks.render.redis_lib") as mock_redis_lib:
        mock_redis_lib.Redis.from_url.return_value = mock_redis
        task_result = task.apply(args=[_VALID_REQUEST])

    result = task_result.get()
    required_fields = {"reproducibility_id", "placed_words", "score", "png_b64", "elapsed_ms"}
    missing = required_fields - set(result.keys())
    assert not missing, f"render_task result missing fields: {missing}"
