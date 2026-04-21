"""Celery task: self_play_nightly (Phase 10, D-02, D-03).

This task is a stub for Phase 10 Plan 01. Full SelfPlayLoop wiring is
implemented in Plan 03.

Design decisions:
    D-02: Task bound (bind=True) to allow retry/self-reference.
    D-02: queue=background — long-running nightly job; isolated from HTTP queue.
    D-02: soft_time_limit=28800 (8 hours); time_limit=28900 (8h + 100s grace).
    D-02: max_retries=0 — self-play is a best-effort nightly job; no retry spam.
    D-03: Task body is a stub returning {"status": "not_implemented"} until
        Plan 03 wires the full SelfPlayLoop.

Security:
    T-10-04: REDIS_URL from environment; task does not access DSN directly.

Note on typing:
    Celery does not ship complete mypy stubs; the @app.task decorator is untyped.
    We use `# type: ignore[misc]` on the decorator and type the function body
    conservatively. self is typed as Any (Celery Task instance) to allow
    self.request access.
"""

from __future__ import annotations

from typing import Any

import structlog

from aerocloud.self_play.config import SelfPlayConfig
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
    """Nightly self-play training loop (stub — full logic wired in Plan 03).

    Args:
        config_override: Optional dict of SelfPlayConfig field overrides.
            If None, defaults from SelfPlayConfig() are used.

    Returns:
        dict with "status" key. Stub returns {"status": "not_implemented"}.

    Note:
        Full SelfPlayLoop is wired in Plan 03. This stub allows the Beat
        schedule and task registration to be verified independently.
    """
    cfg_kwargs: dict[str, Any] = config_override or {}
    cfg = SelfPlayConfig(**cfg_kwargs)  # validates overrides at task start

    logger.info(
        "self_play.task.self_play_nightly.started",
        n_iterations=cfg.n_iterations,
        task_id=self.request.id,
    )

    # TODO(Plan 03): Replace stub with full SelfPlayLoop invocation
    return {"status": "not_implemented"}
