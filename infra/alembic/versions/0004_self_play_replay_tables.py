"""Add Phase 10 self-play replay tables.

Revision ID: 0004_self_play_replay_tables
Revises: 0003_archive_v1_outer_loop
Create Date: 2026-04-16

References:
    - .planning/phases/10-self-play/10-01-PLAN.md (Task 2)
    - D-15: self_play_runs table schema
    - D-16: self_play_events table schema + FK to self_play_runs
    - T-10-02: UUID generated in Python via uuid.uuid4() (not SQL DEFAULT)

Design:
    Creates two new tables for self-play training replay persistence:

    self_play_runs (D-15):
        run_id UUID PRIMARY KEY
            Primary key; NO DEFAULT — generated in Python via uuid.uuid4().
            Python-side UUID generation is portable and explicit;
            avoids dependency on pg_crypto extension.
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        ended_at TIMESTAMPTZ (nullable — set by finalize_run)
        n_iterations INT NOT NULL DEFAULT 0
        n_accepted INT NOT NULL DEFAULT 0
        n_rejected INT NOT NULL DEFAULT 0
        kl_divergence REAL (nullable — None when no prior run exists)
        config JSONB NOT NULL DEFAULT '{}'::jsonb
            Stores arbitrary metadata including descriptor_histogram for KL.

    self_play_events (D-16):
        event_id BIGSERIAL PRIMARY KEY (auto-increment, no Python UUID needed)
        run_id UUID NOT NULL REFERENCES self_play_runs ON DELETE CASCADE
        iteration INT NOT NULL
        parent_bin_ids TEXT[] NOT NULL DEFAULT '{}'
        mutation_type TEXT NOT NULL
        fitness_before REAL (nullable — None when bin was empty)
        fitness_after REAL NOT NULL
        accepted BOOL NOT NULL
        reject_reason TEXT (nullable, empty string for accepted events)

    Index (D-16):
        self_play_events_run_id_iteration_idx ON self_play_events (run_id, iteration)
        Supports efficient per-run event queries during replay.

Security:
    T-10-02: No user-derived data in migration SQL; UUID from Python, not SQL DEFAULT.
    T-10-03: Retention policy deferred to Phase 12; table grows linearly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_self_play_replay_tables"
down_revision: str | None = "0003_archive_v1_outer_loop"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create self_play_runs, self_play_events tables and supporting index."""
    # D-15: self_play_runs table
    # run_id has NO DEFAULT — UUID generated in Python via uuid.uuid4()
    op.execute(
        """
        CREATE TABLE self_play_runs (
            run_id          UUID        PRIMARY KEY,
            started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at        TIMESTAMPTZ,
            n_iterations    INT         NOT NULL DEFAULT 0,
            n_accepted      INT         NOT NULL DEFAULT 0,
            n_rejected      INT         NOT NULL DEFAULT 0,
            kl_divergence   REAL,
            config          JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )

    # D-16: self_play_events table with FK to self_play_runs
    op.execute(
        """
        CREATE TABLE self_play_events (
            event_id        BIGSERIAL   PRIMARY KEY,
            run_id          UUID        NOT NULL
                                REFERENCES self_play_runs (run_id)
                                ON DELETE CASCADE,
            iteration       INT         NOT NULL,
            parent_bin_ids  TEXT[]      NOT NULL DEFAULT '{}',
            mutation_type   TEXT        NOT NULL,
            fitness_before  REAL,
            fitness_after   REAL        NOT NULL,
            accepted        BOOL        NOT NULL,
            reject_reason   TEXT
        )
        """
    )

    # D-16: Index supporting per-run event queries (run_id, iteration)
    op.execute(
        """
        CREATE INDEX self_play_events_run_id_iteration_idx
            ON self_play_events (run_id, iteration)
        """
    )


def downgrade() -> None:
    """Remove self_play_events and self_play_runs tables (events first for FK)."""
    op.execute("DROP TABLE IF EXISTS self_play_events")
    op.execute("DROP TABLE IF EXISTS self_play_runs")
