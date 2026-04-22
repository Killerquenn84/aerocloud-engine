"""Graceful shutdown signal handler for AeroCloud Celery worker.

Design decisions (Phase 12, D-22):
    - Connects to worker_shutting_down Celery signal at app load time.
    - Logs shutdown event via structlog for observability.
    - Future: flush in-flight archive writes before exit.

Security:
    T-12-03-01: Graceful drain ensures in-flight render tasks complete or timeout
        cleanly rather than being killed mid-GPU-kernel.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery.signals import worker_shutting_down

log = structlog.get_logger(__name__)


@worker_shutting_down.connect
def on_worker_shutting_down(
    sig: str,
    how: str,
    exitcode: int,
    **kwargs: Any,
) -> None:
    """Handle worker shutdown signal — log and prepare for clean exit.

    Args:
        sig: Signal name that triggered shutdown (e.g., 'SIGTERM').
        how: Shutdown method (e.g., 'cold', 'warm').
        exitcode: Exit code the worker will use.
        **kwargs: Additional Celery signal kwargs (ignored).
    """
    log.info(
        "worker.shutting_down",
        signal=sig,
        how=how,
        exitcode=exitcode,
    )
    # Future: flush in-flight archive writes here (Phase 12 PROD-20)
