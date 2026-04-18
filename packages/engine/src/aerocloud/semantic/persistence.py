"""pgvector persistence for BERT embedding cache — Phase 8 SEM-07 (D-13, D-14, D-15).

Public API:
    store_embeddings(surfaces, embeddings) -> int
        Upsert (surface, embedding) pairs into word_embeddings table.
        Returns the number of rows upserted.

    load_cached_embeddings(surfaces) -> dict[str, np.ndarray]
        Load cached embeddings for known surfaces.
        Returns a dict mapping surface → (384,) float32 array.
        Surfaces not found in the cache are omitted (cache miss → empty entry).

Design decisions:
    D-13: Table schema — surface TEXT PRIMARY KEY, embedding vector(384),
          model_version TEXT, created_at TIMESTAMPTZ.
    D-15: This module NEVER touches archive_v1. Strict isolation between the
          embedding cache (word_embeddings) and the MAP-Elites archive (archive_v1).

Security (from threat model):
    T-08-10 (Tampering): All surface values passed as parameterised query
          arguments ($1, $2, …). String interpolation of surface values is
          NEVER used, preventing SQL injection even for adversarial inputs.
    T-08-11 (Info Disclosure): settings.database_url is passed to asyncpg
          connect() but NEVER logged. structlog calls use structured keys
          that do not reference the connection string.

Implementation notes:
    - asyncpg is used for async I/O. Connections are created per-call (no pool)
      to keep the module dependency-free from the Celery worker / FastAPI
      lifecycle. A connection pool can be layered on top in Phase 12.
    - The vector type is serialised as a pgvector-formatted string
      "[v1,v2,...,v384]" and cast with `$2::vector` in SQL. This is the
      standard asyncpg + pgvector approach (no ORM required).
    - asyncpg returns pgvector values as Python lists; we convert to numpy.
"""

from __future__ import annotations

import asyncpg
import numpy as np
import structlog

from aerocloud.config import settings
from aerocloud.semantic.errors import SemanticError

logger = structlog.get_logger(__name__)

#: BERT model name stored alongside each embedding for provenance tracking.
MODEL_VERSION: str = "all-MiniLM-L6-v2"


async def _connect() -> asyncpg.Connection:
    """Open a single asyncpg connection using settings.database_url.

    T-08-11: database_url is never logged here or in callers.
    """
    return await asyncpg.connect(settings.database_url)


async def store_embeddings(
    surfaces: list[str],
    embeddings: np.ndarray,
) -> int:
    """Upsert (surface, embedding) pairs into the word_embeddings cache.

    Uses ``INSERT … ON CONFLICT (surface) DO UPDATE`` for idempotent upserts.
    Calling this function twice with the same surface updates the stored vector
    without raising a duplicate-key error.

    Args:
        surfaces: List of N surface strings (word forms). Each maps 1-to-1 to
            a row in ``embeddings``.
        embeddings: Float32 numpy array of shape (N, 384). Each row is the
            all-MiniLM-L6-v2 embedding for the corresponding surface.

    Returns:
        Number of rows upserted (always ``len(surfaces)`` on success).

    Raises:
        SemanticError: If ``len(surfaces) != embeddings.shape[0]``.
        asyncpg.PostgresError: If the database operation fails (propagated as-is).

    Security (T-08-10):
        Surface values are always passed as parameterised arguments ($1, $2, $3).
        No string formatting or interpolation of user-derived data is performed.

    D-15:
        Only writes to word_embeddings. archive_v1 is never touched.
    """
    if len(surfaces) != embeddings.shape[0]:
        raise SemanticError(
            f"surfaces length ({len(surfaces)}) does not match embeddings rows "
            f"({embeddings.shape[0]})"
        )

    conn = await _connect()
    try:
        count = 0
        for surface, emb_row in zip(surfaces, embeddings, strict=True):
            # Serialise float32 row → "[v0,v1,...,v383]" pgvector literal
            vec_str = "[" + ",".join(f"{float(v):.8f}" for v in emb_row.tolist()) + "]"
            # T-08-10: surface is bound as $1 — never interpolated
            await conn.execute(
                """
                INSERT INTO word_embeddings (surface, embedding, model_version)
                VALUES ($1, $2::vector, $3)
                ON CONFLICT (surface) DO UPDATE
                    SET embedding      = EXCLUDED.embedding,
                        model_version  = EXCLUDED.model_version,
                        created_at     = NOW()
                """,
                surface,
                vec_str,
                MODEL_VERSION,
            )
            count += 1
        logger.info(
            "semantic.persistence.store_embeddings.done",
            count=count,
            model_version=MODEL_VERSION,
        )
        return count
    finally:
        await conn.close()


async def load_cached_embeddings(
    surfaces: list[str],
) -> dict[str, np.ndarray]:
    """Load cached embeddings for known surfaces from word_embeddings.

    Surfaces that do not exist in the cache are silently omitted from the result
    (cache miss). The caller should fall back to BERT inference for missing keys.

    Args:
        surfaces: List of surface strings to look up. May be empty.

    Returns:
        Dict mapping surface → (384,) float32 numpy array. Contains only the
        surfaces that were found in the cache. Empty dict if no surfaces are
        cached or if ``surfaces`` is empty.

    Raises:
        asyncpg.PostgresError: If the database operation fails (propagated as-is).

    Security (T-08-10):
        Surface strings are passed via ``ANY($1::text[])`` — fully parameterised,
        no string formatting of user input.

    D-15:
        Only reads from word_embeddings. archive_v1 is never touched.
    """
    if not surfaces:
        return {}

    conn = await _connect()
    try:
        # T-08-10: surface list bound as $1 parameter — no interpolation
        rows = await conn.fetch(
            "SELECT surface, embedding FROM word_embeddings WHERE surface = ANY($1::text[])",
            surfaces,
        )
        result: dict[str, np.ndarray] = {}
        for row in rows:
            # asyncpg returns pgvector as a Python list[float]; convert to float32
            vec = np.array(row["embedding"], dtype=np.float32)
            result[row["surface"]] = vec
        logger.debug(
            "semantic.persistence.load_cached_embeddings.done",
            requested=len(surfaces),
            found=len(result),
        )
        return result
    finally:
        await conn.close()
