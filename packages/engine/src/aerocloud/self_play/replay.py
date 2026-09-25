"""ReplayLogger: asyncpg persistence for self_play_runs and self_play_events.

Design decisions:
    D-17: Direct asyncpg connection per call (no pool) — same pattern as
        ArchivePersistence (outer_loop/persistence.py).
    D-17: UUID generated in Python via uuid.uuid4(), NOT gen_random_uuid() in SQL.
        Research correction: PostgreSQL gen_random_uuid() requires pg_crypto extension;
        Python-side UUID generation is portable and explicit.

Security:
    T-10-01: DSN is stored on instance but NEVER logged. structlog calls use
        structured keys that do not reference the DSN value.
    T-10-02: All SQL uses $N positional parameters; no string interpolation of
        user-derived or run-derived data.
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import numpy as np
import structlog

from aerocloud.self_play.models import SelfPlayEvent

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants (T-10-02: all $N parameterized — no string interpolation)
# ---------------------------------------------------------------------------

_INSERT_RUN_SQL = """
INSERT INTO self_play_runs (run_id, config)
VALUES ($1::uuid, $2::jsonb)
"""

_INSERT_EVENT_SQL = """
INSERT INTO self_play_events (
    run_id, iteration, parent_bin_ids, mutation_type,
    fitness_before, fitness_after, accepted, reject_reason
)
VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
"""

_FINALIZE_RUN_SQL = """
UPDATE self_play_runs
SET ended_at = NOW(),
    n_iterations = $2,
    n_accepted = $3,
    n_rejected = $4,
    kl_divergence = $5
WHERE run_id = $1::uuid
"""

_LOAD_PREV_HISTOGRAM_SQL = """
SELECT config->'descriptor_histogram' AS histogram
FROM self_play_runs
WHERE config ? 'descriptor_histogram'
ORDER BY started_at DESC
LIMIT 1
"""

_STORE_HISTOGRAM_SQL = """
UPDATE self_play_runs
SET config = config || jsonb_build_object('descriptor_histogram', $2::jsonb)
WHERE run_id = $1::uuid
"""


class ReplayLogger:
    """Asyncpg-backed persistence for self-play replay data.

    Provides CRUD operations for self_play_runs and self_play_events tables,
    matching the schema created by Alembic migration 0004.

    Args:
        dsn: asyncpg connection string (postgres://user:pass@host:port/db).
             T-10-01: Never log this value.
    """

    def __init__(self, dsn: str) -> None:
        # T-10-01: Never log DSN value
        self._dsn = dsn

    async def insert_run(self, run_id: uuid.UUID, config: dict[str, object]) -> None:
        """Insert a new run row into self_play_runs.

        Args:
            run_id: Python-generated UUID for this run (NOT SQL DEFAULT).
            config: Arbitrary dict of run metadata (stored as JSONB).

        Security (T-10-02):
            run_id and config are passed as $N parameters; no interpolation.
        """
        config_json = json.dumps(config)
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(_INSERT_RUN_SQL, str(run_id), config_json)
            logger.info(
                "self_play.replay.insert_run.done",
                run_id=str(run_id),
            )
        finally:
            await conn.close()

    async def insert_event(self, run_id: uuid.UUID, event: SelfPlayEvent) -> None:
        """Insert a single self_play_events row.

        Args:
            run_id: Run UUID this event belongs to.
            event: SelfPlayEvent model instance.

        Security (T-10-02):
            All fields passed as $N parameters.
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                _INSERT_EVENT_SQL,
                str(run_id),  # $1 run_id
                event.iteration,  # $2 iteration
                event.parent_bin_ids,  # $3 parent_bin_ids TEXT[]
                event.mutation_type,  # $4 mutation_type
                event.fitness_before,  # $5 fitness_before (nullable)
                event.fitness_after,  # $6 fitness_after
                event.accepted,  # $7 accepted
                event.reject_reason,  # $8 reject_reason
            )
            logger.debug(
                "self_play.replay.insert_event.done",
                run_id=str(run_id),
                iteration=event.iteration,
            )
        finally:
            await conn.close()

    async def finalize_run(
        self,
        run_id: uuid.UUID,
        n_iterations: int,
        n_accepted: int,
        n_rejected: int,
        kl_divergence: float | None,
    ) -> None:
        """Finalize a run: set ended_at and aggregate counters.

        Args:
            run_id: UUID of the run to finalize.
            n_iterations: Total iterations executed.
            n_accepted: Count of accepted mutations.
            n_rejected: Count of rejected mutations.
            kl_divergence: KL-divergence vs previous run; None if no prior run.

        Security (T-10-02):
            All values passed as $N parameters; no interpolation.
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                _FINALIZE_RUN_SQL,
                str(run_id),  # $1
                n_iterations,  # $2
                n_accepted,  # $3
                n_rejected,  # $4
                kl_divergence,  # $5 (nullable)
            )
            logger.info(
                "self_play.replay.finalize_run.done",
                run_id=str(run_id),
                n_iterations=n_iterations,
                n_accepted=n_accepted,
                n_rejected=n_rejected,
            )
        finally:
            await conn.close()

    async def load_previous_descriptor_histogram(
        self,
    ) -> np.ndarray | None:
        """Load the descriptor histogram from the most recent prior run.

        Queries self_play_runs for the latest row that has a
        'descriptor_histogram' key in its config JSONB column.

        Returns:
            np.ndarray of the histogram if found, or None if no prior run
            with a stored histogram exists.

        Security (T-10-02):
            Query has no user-derived parameters; safe as-is.
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(_LOAD_PREV_HISTOGRAM_SQL)
            if row is None or row["histogram"] is None:
                logger.info("self_play.replay.load_histogram.no_prior_run")
                return None
            histogram_data = json.loads(row["histogram"])
            logger.info("self_play.replay.load_histogram.loaded")
            return np.array(histogram_data, dtype=np.float64)
        finally:
            await conn.close()

    async def store_descriptor_histogram(
        self, run_id: uuid.UUID, histogram: list[list[float]]
    ) -> None:
        """Store descriptor histogram in config JSONB for future KL comparison.

        Args:
            run_id: UUID of the current run.
            histogram: 2D list of histogram bin values.

        Security (T-10-02):
            run_id and histogram JSON both passed as $N parameters.
        """
        histogram_json = json.dumps(histogram)
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                _STORE_HISTOGRAM_SQL,
                str(run_id),  # $1
                histogram_json,  # $2 cast ::jsonb
            )
            logger.info(
                "self_play.replay.store_histogram.done",
                run_id=str(run_id),
            )
        finally:
            await conn.close()
