# wiki/code/self-play-replay.md — ReplayLogger

**Phase:** 10-self-play
**Module:** `packages/engine/src/aerocloud/self_play/replay.py`
**Implements:** ReplayLogger — asyncpg persistence for `self_play_runs` and `self_play_events` tables (D-15, D-16, D-17).

---

## Overview

`ReplayLogger` provides async CRUD operations for the two replay tables created by Alembic migration `0004_self_play_replay_tables.py`. Every nightly Self-Play run is recorded atomically. Both accepted and rejected events are logged (T-10-09 repudiation mitigation).

**Pattern:** Direct asyncpg connection per call (no pool), following `ArchivePersistence` pattern. Nightly job runs once; connection pool overhead is unnecessary.

---

## SQL Constants

All SQL uses `$N` positional parameters — no string interpolation of any user-derived or run-derived data (T-10-02):

| Constant | Purpose |
|----------|---------|
| `_INSERT_RUN_SQL` | Insert new run row |
| `_INSERT_EVENT_SQL` | Insert per-iteration event row |
| `_FINALIZE_RUN_SQL` | Update run with end_at + aggregate counters |
| `_LOAD_PREV_HISTOGRAM_SQL` | Fetch descriptor_histogram from most recent prior run |
| `_STORE_HISTOGRAM_SQL` | JSONB merge: append descriptor_histogram to run config |

### Histogram Storage Design

The descriptor histogram is stored as a JSONB field embedded in the `config` column of `self_play_runs`. This avoids a new table for a single array:

```sql
-- Store:
UPDATE self_play_runs
SET config = config || jsonb_build_object('descriptor_histogram', $2::jsonb)
WHERE run_id = $1::uuid

-- Load (most recent prior run with histogram):
SELECT config->'descriptor_histogram' AS histogram
FROM self_play_runs
WHERE config ? 'descriptor_histogram'
ORDER BY started_at DESC LIMIT 1
```

---

## Class: ReplayLogger

```python
class ReplayLogger:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn  # T-10-01: never logged
```

**T-10-01:** DSN stored on instance but NEVER appears in any structlog call. All log keys use `run_id` (UUID string) and numeric counters only.

---

## Methods

### insert_run(run_id: uuid.UUID, config: dict[str, object]) -> None

Inserts a new row into `self_play_runs` with:
- `run_id`: Python-generated UUID (NOT SQL `DEFAULT`)
- `config`: JSONB dict of SelfPlayConfig fields

`config` serialized via `json.dumps(config)` then passed as `$2::jsonb`. `run_id` cast via `$1::uuid`.

### insert_event(run_id: uuid.UUID, event: SelfPlayEvent) -> None

Inserts one row into `self_play_events` mapping all `SelfPlayEvent` fields to `$N` params. `parent_bin_ids` is passed as a Python `list[str]` → asyncpg serializes to PostgreSQL `TEXT[]`.

### finalize_run(run_id, n_iterations, n_accepted, n_rejected, kl_divergence) -> None

`UPDATE self_play_runs SET ended_at=NOW(), n_iterations=$2, ...`. `kl_divergence` is `float | None` (nullable `REAL` column).

### load_previous_descriptor_histogram() -> np.ndarray | None

Queries most recent run with `descriptor_histogram` in `config` JSONB. Returns `np.array(data, dtype=float64)` if found, else `None` (first night with no prior run).

`json.loads(row["histogram"])` deserializes JSONB → Python list → numpy array.

### store_descriptor_histogram(run_id: uuid.UUID, histogram: list[list[float]]) -> None

Stores `current_measures.tolist()` as JSONB in the current run's `config` field for next night's KL comparison. Uses JSONB merge (`config || jsonb_build_object(...)`) to avoid overwriting existing config keys.

---

## Resource Management

Every method follows the pattern:
```python
conn = await asyncpg.connect(self._dsn)
try:
    await conn.execute(SQL, *params)
finally:
    await conn.close()
```

No connection pool. No context manager (`async with`) — explicit `try/finally` matches `ArchivePersistence` idiom.

---

## DB Schema (Alembic 0004)

```sql
CREATE TABLE self_play_runs (
    run_id      UUID PRIMARY KEY,  -- Python uuid.uuid4(), NO DEFAULT
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    n_iterations INT,
    n_accepted  INT,
    n_rejected  INT,
    kl_divergence REAL,
    config      JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE self_play_events (
    event_id       BIGSERIAL PRIMARY KEY,
    run_id         UUID NOT NULL REFERENCES self_play_runs(run_id) ON DELETE CASCADE,
    iteration      INT NOT NULL,
    parent_bin_ids TEXT[] NOT NULL,
    mutation_type  TEXT NOT NULL,
    fitness_before REAL,      -- NULL if bin was empty
    fitness_after  REAL NOT NULL,
    accepted       BOOLEAN NOT NULL,
    reject_reason  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_self_play_events_run_id ON self_play_events(run_id);
```

---

## Design Decisions

| Decision | Detail |
|----------|--------|
| D-15 | `self_play_runs` table: UUID PK, started_at, ended_at, aggregates, config JSONB |
| D-16 | `self_play_events` table: BIGSERIAL PK, FK to runs, per-iteration mutation details |
| D-17 | Full replay reconstruction per success criterion 4; UUID in Python not SQL |

---

## Security

| Threat | Status |
|--------|--------|
| T-10-01 | DSN stored but never logged — all structlog keys exclude DSN |
| T-10-02 | All SQL uses `$N` positional parameters — no string interpolation anywhere |

---

## Tests

`test_replay.py`: 20 unit tests covering:
- SQL injection resistance (regex check for `$N` params, no string interpolation)
- `insert_run` / `insert_event` / `finalize_run` asyncpg call sequences
- `load_previous_descriptor_histogram` with/without prior data
- `store_descriptor_histogram` JSONB merge pattern
- DSN not in any structlog call (T-10-01)

---

*Module: packages/engine/src/aerocloud/self_play/replay.py*
*Phase: 10-self-play*
*Updated: 2026-04-21*
