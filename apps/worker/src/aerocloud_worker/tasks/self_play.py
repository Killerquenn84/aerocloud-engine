"""Celery task: self_play_nightly (Phase 10, D-02, D-03, Plan 03).

Full SelfPlayLoop wiring implemented in Plan 03.

Design decisions:
    D-02: Task bound (bind=True) to allow retry/self-reference.
    D-02: queue=background — long-running nightly job; isolated from HTTP queue.
    D-02: soft_time_limit=28800 (8 hours); time_limit=28900 (8h + 100s grace).
    D-02: max_retries=0 — self-play is a best-effort nightly job; no retry spam.
    D-03: SoftTimeLimitExceeded -> flush_and_finalize for graceful partial result.

Security:
    T-10-04: REDIS_URL from environment; task does not access DSN directly.
    T-10-07 (DoS): soft_time_limit=28800 limits maximum run duration to 8 hours.
        time_limit=28900 is the hard kill safety net (D-03).
    T-10-08 (Tampering): SelfPlayLoop enforces STRICT > dominance (D-08).
    T-10-09 (Repudiation): All iterations logged to self_play_events (D-17).

Note on typing:
    Celery does not ship complete mypy stubs; the @app.task decorator is untyped.
    We use `# type: ignore[misc]` on the decorator and type the function body
    conservatively. self is typed as Any (Celery Task instance) to allow
    self.request access.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.loop import SelfPlayLoop
from aerocloud_worker.celery_app import app

logger = structlog.get_logger(__name__)


@app.task(
    bind=True,
    name="aerocloud_worker.tasks.self_play.self_play_nightly",
    queue="background",
    soft_time_limit=28800,
    time_limit=28900,
    max_retries=0,
)
def self_play_nightly(self: Any, config_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Nightly self-play training loop.

    Builds a SelfPlayLoop from environment variables and runs it for the
    configured number of iterations. Handles SoftTimeLimitExceeded gracefully
    by calling flush_and_finalize() to preserve partial results.

    Args:
        config_override: Optional dict of SelfPlayConfig field overrides.
            If None, defaults from SelfPlayConfig() are used.

    Returns:
        dict with run result fields (run_id, n_iterations, n_accepted, n_rejected,
        kl_divergence, exit_reason) for Celery result backend.
    """
    cfg_kwargs: dict[str, Any] = config_override or {}
    cfg = SelfPlayConfig(**cfg_kwargs)  # validates overrides at task start

    logger.info(
        "self_play.task.self_play_nightly.started",
        n_iterations=cfg.n_iterations,
        task_id=self.request.id,
    )

    loop = SelfPlayLoop.build_from_env()
    result = None

    try:
        result = loop.run(cfg.n_iterations)

        logger.info(
            "self_play.task.self_play_nightly.completed",
            run_id=result.run_id,
            n_iterations=result.n_iterations,
            n_accepted=result.n_accepted,
            n_rejected=result.n_rejected,
            kl_divergence=result.kl_divergence,
            task_id=self.request.id,
        )

    except SoftTimeLimitExceeded:
        # Graceful shutdown: preserve partial results (D-03, T-10-07)
        n_done = loop._n_accepted + loop._n_rejected
        result = loop.flush_and_finalize(n_done=n_done, exit_reason="soft_timeout")

        logger.warning(
            "self_play.task.self_play_nightly.soft_timeout",
            run_id=result.run_id,
            n_done=n_done,
            n_accepted=result.n_accepted,
            n_rejected=result.n_rejected,
            task_id=self.request.id,
        )

    return result.model_dump()
