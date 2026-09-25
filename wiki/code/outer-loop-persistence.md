# wiki/code/outer-loop-persistence.md — ArchivePersistence

**Phase:** 09-outer-loop-v1
**Module:** `packages/engine/src/aerocloud/outer_loop/persistence.py`
**Implements:** PostgreSQL archive persistence (flush_batch + load_all) via asyncpg + safetensors (D-10, D-11)

---

## Overview

`ArchivePersistence` provides asynchronous PostgreSQL I/O for the MAP-Elites archive. It implements:
- `flush_batch()`: upsert batch of archive entries with ON CONFLICT fitness guard
- `load_all()`: full archive restore from PostgreSQL at startup (D-11 resume)

Serialization: safetensors for params tensors (NOT pickle — security requirement T-09-06).
Pattern: direct asyncpg connection per call (no pool), matching `semantic/persistence.py`.

---

## Alembic Migration: 0003_archive_v1_outer_loop

Extends `archive_v1` table with 6 new columns:

| Column | Type | Description |
|--------|------|-------------|
| `shape_fidelity` | `REAL` | BD scalar: shape fidelity metric |
| `rotation_ratio` | `REAL` | BD scalar: fraction of rotated words |
| `symmetry` | `REAL` | BD scalar: horizontal symmetry score |
| `semantic_clustering` | `REAL` | BD scalar: spatial/embedding distance consistency |
| `params_blob` | `BYTEA` | safetensors-serialized (N,4) params tensor |
| `quality_metrics` | `JSONB` | QualityMetrics dict for audit trail |

Also adds: `CREATE INDEX CONCURRENTLY IF NOT EXISTS archive_v1_fitness_idx ON archive_v1(fitness DESC)`

Uses `ADD COLUMN IF NOT EXISTS` for idempotency.

---

## Serialization Helpers

### params_to_bytes(params: torch.Tensor) -> bytes

Serialize a params tensor to safetensors bytes for BYTEA storage.

```python
# Internally:
safe_tensor = params.detach().cpu().contiguous()  # Pitfall 6 mitigation
return _st_save({"params": safe_tensor})
```

**Pitfall 6 mitigation:** `.detach().cpu().contiguous()` ensures CPU-resident contiguous memory before safetensors (which requires both).

**Security (T-09-06):** Uses safetensors.torch.save — NOT pickle. safetensors has no arbitrary code execution attack surface.

### bytes_to_params(data: bytes) -> torch.Tensor

Deserialize safetensors bytes back to torch.Tensor.

```python
tensors = _st_load(data)
return tensors["params"]
```

Returns CPU tensor with the original shape.

---

## Class: ArchivePersistence

```python
class ArchivePersistence:
    def __init__(self, dsn: str) -> None
```

| Param | Type | Description |
|-------|------|-------------|
| `dsn` | `str` | asyncpg connection string. T-09-07: never logged. |

---

### flush_batch(entries: list[ArchiveFlushEntry]) -> int

Upsert a batch of archive entries to PostgreSQL.

```python
count = await persistence.flush_batch(entries)
```

**SQL pattern (D-10 — fitness guard):**
```sql
INSERT INTO archive_v1 (bin_id, descriptor, fitness, ..., params_blob, quality_metrics, updated_at)
VALUES ($1, $2::vector, $3, ..., $9, $10::jsonb, NOW())
ON CONFLICT (bin_id) DO UPDATE
    SET ...
    WHERE EXCLUDED.fitness > archive_v1.fitness
```

Key behavior:
- Only replaces existing cell when incoming fitness is strictly higher (D-10)
- All SQL uses `$N` parameterized placeholders — no string interpolation (T-09-05)
- Entire batch runs in a single asyncpg transaction
- Returns `len(entries)` — not affected-row count (asyncpg does not expose that for upserts without RETURNING)
- Empty list is a no-op returning 0

### load_all() -> list[tuple[str, float, np.ndarray, np.ndarray]]

Load all persisted archive entries for startup resume (D-11).

```python
rows = await persistence.load_all()
# Each row: (bin_id, fitness, measures_4d, solution_flat)
```

| Field | Type | Description |
|-------|------|-------------|
| `bin_id` | `str` | Archive cell identifier |
| `fitness` | `float` | Quality score at last flush |
| `measures_4d` | `np.ndarray (4,)` | `[shape_fidelity, rotation_ratio, symmetry, semantic_clustering]` |
| `solution_flat` | `np.ndarray` | Params tensor flattened to 1D via `bytes_to_params().numpy().flatten()` |

Filters: `WHERE params_blob IS NOT NULL` — guards against legacy partial rows.
Order: `ORDER BY fitness DESC` — best elites first.
Returns `[]` when no rows with params_blob exist.

---

## Model: ArchiveFlushEntry

```python
class ArchiveFlushEntry(AeroCloudBase):
    bin_id: str
    descriptor_vec: Any               # np.ndarray (384,) float32 — pgvector embedding
    fitness: float
    metadata: dict[str, Any]
    behavior_descriptor: BehaviorDescriptor  # 4 BD scalars
    params_bytes: bytes               # safetensors bytes (NOT pickle)
    quality_metrics_json: dict[str, Any]

    model_config = ConfigDict(
        frozen=True, strict=False,
        extra="forbid", arbitrary_types_allowed=True
    )
```

Note: `strict=False` override from AeroCloudBase is required to accept numpy arrays for `descriptor_vec`.

---

## Security Profile

| Threat | Mitigation |
|--------|------------|
| T-09-05 (SQL injection) | All SQL uses $N params; no string interpolation of user data |
| T-09-06 (deserialization) | safetensors.torch only; pickle is never imported |
| T-09-07 (DSN in logs) | `_dsn` stored on instance but never referenced in structlog calls |

---

## pgvector Encoding

```python
def _vec_to_pgvector(descriptor: np.ndarray) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in descriptor.tolist()) + "]"
```

Encodes float32 numpy array to pgvector literal `"[v0,v1,...,vN]"` format. Applied to numerical data only — no user-controlled strings. Pattern matches `semantic/persistence.py`.

---

*Module: packages/engine/src/aerocloud/outer_loop/persistence.py*
*Phase: 09-outer-loop-v1*
*Updated: 2026-04-18*
