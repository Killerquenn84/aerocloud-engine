"""Add word_embeddings table for BERT embedding cache (Phase 8, SEM-07).

Revision ID: 0002_word_embeddings
Revises: 0001_baseline
Create Date: 2026-04-16

References:
    - .planning/phases/08-semantic-vector-space/08-05-PLAN.md (SEM-07)
    - .planning/phases/08-semantic-vector-space/08-RESEARCH.md D-13, D-14
    - Decision D-13: table schema (surface PK, embedding vector(384), model_version, created_at)
    - Decision D-14: HNSW index on embedding column with vector_cosine_ops
    - Decision D-15: Phase 8 does NOT write to archive_v1
    - T-08-10: All surface values inserted via parameterised queries (no interpolation)
    - T-08-11: database_url sourced from env var only; never appears in migration SQL

Design:
    - `surface` is the primary key (text). Each unique word surface has at most
      one cached embedding. Upsert pattern (INSERT ... ON CONFLICT DO UPDATE)
      keeps the cache fresh without duplicates.
    - `embedding` uses raw SQL vector(384) type (same pattern as 0001_baseline
      for archive_v1.descriptor). pgvector extension created idempotently.
    - HNSW index parameters: m=16, ef_construction=64 (pgvector defaults).
      Fine-tuning deferred to Phase 9 alongside archive_v1 HNSW tuning.
    - `model_version` records which BERT model produced the vector; defaults to
      all-MiniLM-L6-v2 to match Phase 8 implementation.
    - `created_at` is a timezone-aware server timestamp (DEFAULT NOW()).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_word_embeddings"
down_revision: str | None = "0001_baseline"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create word_embeddings table with pgvector HNSW index (D-13, D-14)."""
    # pgvector extension is created idempotently — may already exist from 0001
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE word_embeddings (
            surface        TEXT                     PRIMARY KEY,
            embedding      vector(384)              NOT NULL,
            model_version  TEXT                     NOT NULL DEFAULT 'all-MiniLM-L6-v2',
            created_at     TIMESTAMPTZ              NOT NULL DEFAULT NOW()
        )
        """
    )

    # HNSW index for cosine similarity (D-14): enables fast ANN search in Phase 9
    # m=16, ef_construction=64 are pgvector defaults — tune in Phase 9
    op.execute(
        """
        CREATE INDEX ix_word_embeddings_embedding_hnsw
            ON word_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Drop HNSW index and word_embeddings table (extension is left in place)."""
    op.execute("DROP INDEX IF EXISTS ix_word_embeddings_embedding_hnsw")
    op.execute("DROP TABLE IF EXISTS word_embeddings")
    # Note: pgvector extension intentionally NOT dropped — archive_v1 may use it
