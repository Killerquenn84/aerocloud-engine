"""Phase 2 baseline: archive_v1 table with pgvector HNSW index.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-07

References:
    - .planning/phases/02-datenmodell-wiki/02-CONTEXT.md D-10
    - wiki/knowledge/stack-versions.md (pgvector 0.4.2, HNSW for BERT 384-dim)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create pgvector extension + archive_v1 table + HNSW index."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE archive_v1 (
            id BIGSERIAL PRIMARY KEY,
            bin_id TEXT UNIQUE NOT NULL,
            descriptor vector(384) NOT NULL,
            fitness DOUBLE PRECISION NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # HNSW index for cosine similarity on 384-dim BERT embeddings
    # m=16, ef_construction=64 are pgvector defaults — tune in Phase 9
    op.execute(
        """
        CREATE INDEX archive_v1_descriptor_idx
            ON archive_v1
            USING hnsw (descriptor vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Drop the HNSW index and archive_v1 table (extension is left in place)."""
    op.execute("DROP INDEX IF EXISTS archive_v1_descriptor_idx")
    op.execute("DROP TABLE IF EXISTS archive_v1")
    # Note: we do NOT drop the vector extension — other tables may use it
