"""Tests for Celery worker configuration — Phase 12-03 (PROD-09, PROD-10, PROD-11, PROD-12).

Validates queue routing, timeout settings, prefetch multiplier, and graceful
shutdown signal handler registration.
"""

from __future__ import annotations

import importlib
import types


def test_task_routes_realtime_queue_for_render() -> None:
    """Render tasks must be routed to the 'realtime' queue (PROD-09)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    routes = app.conf.task_routes
    assert isinstance(routes, dict), "task_routes must be a dict"
    assert "aerocloud_worker.tasks.render.*" in routes, (
        "render.* route missing — must be mapped to realtime queue"
    )
    assert routes["aerocloud_worker.tasks.render.*"] == {"queue": "realtime"}, (
        "render.* must route to 'realtime' queue"
    )


def test_task_routes_background_queue_for_self_play() -> None:
    """Self-play tasks must remain routed to the 'background' queue (PROD-09)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    routes = app.conf.task_routes
    assert "aerocloud_worker.tasks.self_play.*" in routes, (
        "self_play.* route missing — must be mapped to background queue"
    )
    assert routes["aerocloud_worker.tasks.self_play.*"] == {"queue": "background"}, (
        "self_play.* must route to 'background' queue"
    )


def test_worker_prefetch_multiplier_is_one() -> None:
    """Prefetch multiplier must be 1 to prevent GPU OOM from task pile-up (PROD-10, T-12-03-04)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    assert app.conf.worker_prefetch_multiplier == 1, (
        "worker_prefetch_multiplier must be 1 for GPU workloads"
    )


def test_render_task_time_limit_300s() -> None:
    """Render task hard timeout must be 300 seconds (PROD-11, T-12-03-01)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    annotations = app.conf.task_annotations
    assert isinstance(annotations, dict), "task_annotations must be a dict"
    render_ann = annotations.get("aerocloud_worker.tasks.render.*", {})
    assert render_ann.get("time_limit") == 300, (
        "render task must have time_limit=300 (5-min hard kill)"
    )


def test_render_task_soft_time_limit_270s() -> None:
    """Render task soft timeout must be 270 seconds (allows cleanup before hard kill)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    annotations = app.conf.task_annotations
    render_ann = annotations.get("aerocloud_worker.tasks.render.*", {})
    assert render_ann.get("soft_time_limit") == 270, (
        "render task must have soft_time_limit=270 (30s cleanup window)"
    )


def test_self_play_soft_time_limit_28800s() -> None:
    """Self-play task soft timeout must be 28800 seconds (8 hours, PROD-12)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    annotations = app.conf.task_annotations
    self_play_ann = annotations.get("aerocloud_worker.tasks.self_play.*", {})
    assert self_play_ann.get("soft_time_limit") == 28800, (
        "self_play task must retain soft_time_limit=28800 (8 hours)"
    )


def test_no_global_task_time_limit() -> None:
    """No global task_time_limit must be set — different limits per queue (D-11)."""
    from aerocloud_worker.celery_app import app  # noqa: PLC0415

    # Celery default is None for task_time_limit (no global hard kill)
    assert app.conf.task_time_limit is None, (
        "global task_time_limit must not be set — use task_annotations per task"
    )


def test_shutdown_module_imports_cleanly() -> None:
    """shutdown.py must import without errors and register the signal handler."""
    mod = importlib.import_module("aerocloud_worker.shutdown")
    assert isinstance(mod, types.ModuleType), "shutdown module must be importable"
    assert hasattr(mod, "on_worker_shutting_down"), (
        "shutdown module must export on_worker_shutting_down"
    )


def test_shutdown_signal_is_connected() -> None:
    """on_worker_shutting_down must be registered on the worker_shutting_down signal."""
    from celery.signals import worker_shutting_down  # noqa: PLC0415

    # Celery Signal stores receivers; verify our handler is registered
    import aerocloud_worker.shutdown  # noqa: F401, PLC0415

    receivers = worker_shutting_down.receivers
    assert len(receivers) > 0, (
        "worker_shutting_down signal must have at least one receiver (on_worker_shutting_down)"
    )
    # Verify the registered receiver is our function
    receiver_names = [
        getattr(recv[1](), "__name__", "") if recv[1]() is not None else ""
        for recv in receivers
    ]
    assert "on_worker_shutting_down" in receiver_names, (
        "on_worker_shutting_down must be connected to worker_shutting_down signal"
    )
