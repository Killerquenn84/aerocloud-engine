"""Celery application instance with Beat schedule for AeroCloud Worker.

Design decisions (Phase 10, D-01, D-02):
    - Beat schedule triggers self_play_nightly at 02:00 Europe/Berlin nightly.
    - Broker URL from REDIS_URL env var (default: redis://localhost:6379/0).
    - UTC enabled; timezone set to Europe/Berlin for Beat crontab expressions.
    - Task routes direct self-play tasks to the 'background' queue.

Security:
    T-10-04: REDIS_URL from environment; never hardcoded. Worker runs on
        trusted VPS — env var injection requires root access.
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
# Task routes (D-02: background queue for self-play tasks)
# ---------------------------------------------------------------------------

app.conf.task_routes = {
    "aerocloud_worker.tasks.self_play.*": {"queue": "background"},
}

# ---------------------------------------------------------------------------
# Task autodiscovery
# ---------------------------------------------------------------------------

app.autodiscover_tasks(["aerocloud_worker.tasks"])
