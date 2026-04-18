# semantic/persistence.py — Module Documentation

**Phase:** 08-semantic-vector-space
**Package:** `aerocloud.semantic`
**Module:** `packages/engine/src/aerocloud/semantic/persistence.py`
**Requirements:** SEM-07
**Status:** Implemented + tested (Phase 8 complete)

---

## Overview

pgvector persistence for BERT embedding cache. Provides async upsert and lookup functions
for the `word_embeddings` table, enabling embeddings to be reused across rendering runs
without re-running BERT inference.

**Core design (D-13 to D-15):** New Alembic migration `0002_word_embeddings` creates the
table with `surface TEXT PRIMARY KEY`, `embedding vector(384)`, HNSW cosine index, and
full `archive_v1` isolation (D-15: this module NEVER touches `archive_v1`).

---

## Public API

### `async store_embeddings(surfaces, embeddings) -> int`

Upsert `(surface, embedding)` pairs into the `word_embeddings` cache.

**Args:**
- `surfaces`: List of N surface strings (word forms)
- `embeddings`: `(N, 384)` float32 numpy array

**Returns:** Number of rows upserted (always `len(surfaces)` on success)

**Raises:**
- `SemanticError`: If `len(surfaces) != embeddings.shape[0]`
- `asyncpg.PostgresError`: If the database operation fails (propagated as-is)

**SQL Pattern (T-08-10 — fully parameterised):**
```sql
INSERT INTO word_embeddings (surface, embedding, model_version)
VALUES ($1, $2::vector, $3)
ON CONFLICT (surface) DO UPDATE
    SET embedding     = EXCLUDED.embedding,
        model_version = EXCLUDED.model_version,
        created_at    = NOW()
```

### `async load_cached_embeddings(surfaces) -> dict[str, np.ndarray]`

Load cached embeddings for known surfaces. Surfaces not in cache are silently omitted.

**Args:**
- `surfaces`: List of surface strings to look up. May be empty.

**Returns:** `dict[str, ndarray(384,)]` — only surfaces found in cache. Empty dict if
none cached or `surfaces` is empty.

**SQL Pattern (T-08-10):**
```sql
SELECT surface, embedding
FROM word_embeddings
WHERE surface = ANY($1::text[])
```

---

## Database Schema (D-13)

Alembic migration `0002_word_embeddings`:

```sql
CREATE TABLE word_embeddings (
    surface       TEXT PRIMARY KEY,
    embedding     vector(384) NOT NULL,
    model_version TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### HNSW Index (D-14)

```sql
CREATE INDEX word_embeddings_embedding_hnsw_idx
    ON word_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

- `vector_cosine_ops`: Matches the `all-MiniLM-L6-v2` cosine similarity metric
- `m=16`: Fanout per layer (balanced speed/memory for ~10k word vocabulary)
- `ef_construction=64`: Build-time quality (higher = better recall, slower build)
- **Phase 9 use:** MAP-Elites ANN similarity search will query this index

---

## Implementation Details

### Connection Pattern

```python
async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(settings.database_url)
```

Per-call connection (no pool) to keep the module dependency-free from the Celery worker
/ FastAPI lifecycle. A connection pool will be layered on top in Phase 12 production
hardening. Database URL is never logged (T-08-11).

### Vector Serialization

pgvector values are serialized as `"[v0,v1,...,v383]"` string and cast with `$2::vector`
in SQL. asyncpg returns pgvector values as Python `list[float]`; we convert to `float32`
numpy on read.

```python
vec_str = "[" + ",".join(f"{float(v):.8f}" for v in emb_row.tolist()) + "]"
```

### Model Version Tracking

`MODEL_VERSION = "all-MiniLM-L6-v2"` is stored alongside each embedding for provenance
tracking. If the model changes, the stored version enables cache invalidation.

---

## Security

| Threat | ID | Mitigation |
|--------|----|------------|
| SQL injection | T-08-10 | All surface values passed as parameterised `$N` args; no string interpolation |
| Info disclosure (connection string) | T-08-11 | `settings.database_url` never logged; structlog calls use structured keys only |

---

## D-15: archive_v1 Isolation

This module contains **zero** references to `archive_v1` in executable SQL. The
`word_embeddings` table is strictly separate from the MAP-Elites archive. The
`archive_v1.descriptor vector(384)` column is reserved for Phase 9 aggregate layout
embeddings — Phase 8 does not write or read from it.

Verified by static check in SUMMARY self-check: `grep "archive_v1" persistence.py`
returns comments only.

---

## References

- `packages/engine/src/aerocloud/semantic/persistence.py`
- `infra/alembic/versions/0002_word_embeddings.py`
- `packages/engine/tests/semantic/integration/test_pgvector.py`
- `.planning/phases/08-semantic-vector-space/08-05-PLAN.md`
- `.planning/phases/08-semantic-vector-space/08-CONTEXT.md` §D-13 to D-15
- `infra/alembic/versions/0001_baseline.py` — existing `archive_v1` + pgvector extension
