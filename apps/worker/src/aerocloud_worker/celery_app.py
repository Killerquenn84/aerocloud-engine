"""Celery application instance with Beat schedule for AeroCloud Worker.

Design decisions (Phase 10, D-01, D-02; Phase 12, D-11, D-12, D-13, D-14):
    - Beat schedule triggers self_play_nightly at 02:00 Europe/Berlin nightly.
    - Broker URL from REDIS_URL env var (default: redis://localhost:6379/0).
    - UTC enabled; timezone set to Europe/Berlin for Beat crontab expressions.
    - Two queues: realtime (render tasks) and background (self-play tasks).
    - worker_prefetch_multiplier=1: one task at a time prevents GPU OOM (D-12).
    - Per-task time limits via task_annotations (D-13):
        render.*: time_limit=300 (5-min hard kill), soft_time_limit=270 (30s cleanup).
        self_play.*: soft_time_limit=28800 (8 hours nightly budget).
    - D-14 GPU isolation: each worker instance sets CUDA_VISIBLE_DEVICES=N in
        its environment (configured in docker-compose or PM2, not in code).

Security:
    T-10-04: REDIS_URL from environment; never hardcoded. Worker runs on
        trusted VPS — env var injection requires root access.
    T-12-03-01 (DoS): time_limit=300 hard kill prevents cost runaway on render tasks.
    T-12-03-02 (DoS): max-tasks-per-child=50 (set in entrypoint) prevents GPU memory leak.
    T-12-03-04 (DoS): worker_prefetch_multiplier=1 prevents GPU OOM from queued task pile-up.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

app = Celery("aerocloud_worker")

# ---------------------------------------------------------------------------
# Broker / backend configuration
# ---------------------------------------------------------------------------

app.conf.broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
app.conf.result_backend = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Time zone (D-01: crontab expressed in Europe/Berlin local time)
# ---------------------------------------------------------------------------

app.conf.timezone = "Europe/Berlin"
app.conf.enable_utc = True

# ---------------------------------------------------------------------------
# GPU concurrency (D-12): one task at a time — GPU tasks must not be prefetched
# ---------------------------------------------------------------------------

app.conf.worker_prefetch_multiplier = 1

# ---------------------------------------------------------------------------
# Beat schedule (D-01, D-02)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    "self-play-nightly": {
        "task": "aerocloud_worker.tasks.self_play.self_play_nightly",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "background"},
    },
}

# ---------------------------------------------------------------------------
# Task routes (D-11: realtime for render, background for self-play)
# ---------------------------------------------------------------------------

app.conf.task_routes = {
    "aerocloud_worker.tasks.render.*": {"queue": "realtime"},
    "mockup.*": {"queue": "realtime"},
    "aerocloud_worker.tasks.self_play.*": {"queue": "background"},
}

# ---------------------------------------------------------------------------
# Per-task time limits (D-13)
# Do NOT set global task_time_limit — different limits per queue.
# ---------------------------------------------------------------------------

app.conf.task_annotations = {
    "aerocloud_worker.tasks.render.*": {
        "time_limit": 300,  # 5-min hard kill (T-12-03-01)
        "soft_time_limit": 270,  # 30s cleanup window before hard kill
    },
    "mockup.*": {
        "time_limit": 300,  # 5-min hard kill (Sprint P23, Phase B)
        "soft_time_limit": 270,
    },
    "aerocloud_worker.tasks.self_play.*": {
        "soft_time_limit": 28800,  # 8-hour nightly budget
    },
}

# ---------------------------------------------------------------------------
# Task autodiscovery
# ---------------------------------------------------------------------------

app.autodiscover_tasks(["aerocloud_worker.tasks"])

# ---------------------------------------------------------------------------
# Graceful shutdown signal handler (D-22)
# Import here to ensure the signal is registered at app load time.
# ---------------------------------------------------------------------------

import aerocloud_worker.shutdown  # noqa: E402, F401
