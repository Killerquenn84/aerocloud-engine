"""Add Phase 9 outer-loop columns to archive_v1.

Revision ID: 0003_archive_v1_outer_loop
Revises: 0002_word_embeddings
Create Date: 2026-04-18

References:
    - .planning/phases/09-outer-loop-v1/09-03-PLAN.md (Task 1)
    - D-08: Add scalar BD columns + params_blob BYTEA + quality_metrics JSONB
    - D-09: Behavioral descriptor scalars in dedicated columns for indexing
    - D-10: ON CONFLICT fitness guard requires fitness column to be indexed
    - T-09-05: All queries use parameterized placeholders; no string interpolation

Design:
    Extends the existing archive_v1 table (from 0001_baseline) with six new
    columns required by the MAP-Elites outer loop (Phase 9):

    Behavioral descriptor scalars (D-08):
        shape_fidelity       REAL  — stored separately for B-tree indexing
        rotation_ratio       REAL  — fraction of words with |theta| > pi/4
        symmetry             REAL  — horizontal reflection score
        semantic_clustering  REAL  — inverted spatial/embedding distortion

    Params blob (D-08):
        params_blob  BYTEA  — safetensors-serialized (N, 4) params tensor.
                              NOT pickle (security constraint from CLAUDE.md).

    Quality metrics (D-08):
        quality_metrics  JSONB  — serialized QualityMetrics dict for auditability.

    Additional index (D-10, D-14):
        archive_v1_fitness_idx  ON archive_v1 (fitness DESC)
        Supports top-N queries for periodic re-evaluation (D-14) and the
        fitness guard in the ON CONFLICT upsert (D-10).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_archive_v1_outer_loop"
down_revision: str | None = "0002_word_embeddings"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add Phase 9 BD scalar columns, params_blob, quality_metrics, and fitness index."""
    # D-08: Add the six new columns using ADD COLUMN IF NOT EXISTS (idempotent).
    # Single ALTER TABLE with multiple ADD COLUMN clauses for atomicity.
    op.execute(
        """
        ALTER TABLE archive_v1
            ADD COLUMN IF NOT EXISTS shape_fidelity       REAL,
            ADD COLUMN IF NOT EXISTS rotation_ratio        REAL,
            ADD COLUMN IF NOT EXISTS symmetry              REAL,
            ADD COLUMN IF NOT EXISTS semantic_clustering   REAL,
            ADD COLUMN IF NOT EXISTS params_blob           BYTEA,
            ADD COLUMN IF NOT EXISTS quality_metrics       JSONB
        """
    )

    # B-tree index on fitness DESC for re-evaluation top-N queries (D-14)
    # and to support the ON CONFLICT fitness guard (D-10).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS archive_v1_fitness_idx
            ON archive_v1 (fitness DESC)
        """
    )


def downgrade() -> None:
    """Remove the fitness index and the six Phase 9 columns."""
    op.execute("DROP INDEX IF EXISTS archive_v1_fitness_idx")
    op.execute(
        """
        ALTER TABLE archive_v1
            DROP COLUMN IF EXISTS shape_fidelity,
            DROP COLUMN IF EXISTS rotation_ratio,
            DROP COLUMN IF EXISTS symmetry,
            DROP COLUMN IF EXISTS semantic_clustering,
            DROP COLUMN IF EXISTS params_blob,
            DROP COLUMN IF EXISTS quality_metrics
        """
    )
