"""Archive persistence: flush_batch + load_all via asyncpg (Plan 09-03, D-10, D-11).

Public API:
    params_to_bytes(params: torch.Tensor) -> bytes
        Serialize (N, 4) params tensor to safetensors bytes for BYTEA column.
        Calls .detach().cpu().contiguous() internally (Pitfall 6).
        NOT pickle — pickle is security-forbidden per CLAUDE.md.

    bytes_to_params(data: bytes) -> torch.Tensor
        Deserialize safetensors bytes back to a torch.Tensor.

    class ArchivePersistence:
        flush_batch(entries) -> int
            Upsert a list of ArchiveFlushEntry into archive_v1 via ON CONFLICT.
            Only updates the row when EXCLUDED.fitness > archive_v1.fitness (D-10).
            Returns the number of entries submitted (not rows actually changed —
            asyncpg execute() does not expose affected-row count for upserts
            without a RETURNING clause; count is len(entries)).

        load_all() -> list[tuple[str, float, np.ndarray, np.ndarray]]
            Load all rows from archive_v1.
            Returns (bin_id, fitness, measures_4d, solution_flat) per row.
            measures_4d = [shape_fidelity, rotation_ratio, symmetry, semantic_clustering].
            solution_flat = bytes_to_params(params_blob).numpy().flatten().

Design decisions (from 09-03-PLAN.md):
    D-10: ON CONFLICT (bin_id) DO UPDATE WHERE EXCLUDED.fitness > archive_v1.fitness
    D-11: Batch flush every 100 evals + final flush; load at startup to resume.
    D-11: Direct asyncpg connection per call (no pool) — same as semantic/persistence.py.

Security:
    T-09-05 (Tampering — SQL injection): All SQL uses $N parameterized placeholders.
        No string formatting or interpolation of user data. bin_id, fitness, BD
        scalars, params_blob and quality_metrics are always bound as query arguments.
    T-09-06 (Tampering — deserialization): safetensors only; pickle is NEVER used.
        safetensors has no arbitrary code execution attack surface.
    T-09-07 (Info Disclosure — DSN in logs): DSN is stored on the class but never
        logged. structlog calls use structured keys that do not reference the DSN.
"""

from __future__ import annotations

import json

import asyncpg
import numpy as np
import structlog
import torch
from safetensors.torch import load as _st_load
from safetensors.torch import save as _st_save

from aerocloud.outer_loop.models import ArchiveFlushEntry

logger = structlog.get_logger(__name__)

# Re-export ArchiveFlushEntry so callers can import from this module
__all__ = [
    "ArchiveFlushEntry",
    "ArchivePersistence",
    "bytes_to_params",
    "params_to_bytes",
]

# ---------------------------------------------------------------------------
# Serialization helpers (T-09-06: safetensors — no pickle)
# ---------------------------------------------------------------------------

_PARAMS_KEY = "params"


def params_to_bytes(params: torch.Tensor) -> bytes:
    """Serialize a params tensor to safetensors bytes for BYTEA storage.

    Args:
        params: Params tensor of any shape (typically (N, 4)).
            May be on any device and may be non-contiguous.

    Returns:
        Raw safetensors bytes suitable for direct insertion into a BYTEA column.

    Security (T-09-06):
        Uses safetensors.torch.save — NOT pickle. safetensors does not execute
        arbitrary code during deserialization.

    Pitfall 6 mitigation:
        .detach().cpu().contiguous() ensures the tensor is CPU-resident and
        memory-contiguous before passing to safetensors (which requires both).
    """
    safe_tensor = params.detach().cpu().contiguous()
    return _st_save({_PARAMS_KEY: safe_tensor})


def bytes_to_params(data: bytes) -> torch.Tensor:
    """Deserialize safetensors bytes to a torch.Tensor.

    Args:
        data: Raw bytes produced by params_to_bytes().

    Returns:
        Torch tensor on CPU; shape matches the original tensor.

    Security (T-09-06):
        Uses safetensors.torch.load — NOT pickle.
    """
    tensors = _st_load(data)
    return tensors[_PARAMS_KEY]


# ---------------------------------------------------------------------------
# ArchivePersistence
# ---------------------------------------------------------------------------

_UPSERT_SQL = """
INSERT INTO archive_v1 (
    bin_id, descriptor, fitness, metadata,
    shape_fidelity, rotation_ratio, symmetry, semantic_clustering,
    params_blob, quality_metrics, updated_at
)
VALUES ($1, $2::vector, $3, $4::jsonb, $5, $6, $7, $8, $9, $10::jsonb, NOW())
ON CONFLICT (bin_id) DO UPDATE
    SET fitness              = EXCLUDED.fitness,
        descriptor           = EXCLUDED.descriptor,
        metadata             = EXCLUDED.metadata,
        shape_fidelity       = EXCLUDED.shape_fidelity,
        rotation_ratio       = EXCLUDED.rotation_ratio,
        symmetry             = EXCLUDED.symmetry,
        semantic_clustering  = EXCLUDED.semantic_clustering,
        params_blob          = EXCLUDED.params_blob,
        quality_metrics      = EXCLUDED.quality_metrics,
        updated_at           = NOW()
    WHERE EXCLUDED.fitness > archive_v1.fitness
"""

_LOAD_SQL = """
SELECT
    bin_id,
    fitness,
    shape_fidelity,
    rotation_ratio,
    symmetry,
    semantic_clustering,
    params_blob
FROM archive_v1
WHERE params_blob IS NOT NULL
ORDER BY fitness DESC
"""


def _vec_to_pgvector(descriptor: np.ndarray) -> str:
    """Convert a float32 ndarray to a pgvector literal string.

    Format: "[v0,v1,...,vN]" — same pattern as semantic/persistence.py.

    T-09-05: This is applied to numerical data only; no user-controlled strings
    are interpolated into SQL.
    """
    return "[" + ",".join(f"{float(v):.8f}" for v in descriptor.tolist()) + "]"


class ArchivePersistence:
    """PostgreSQL persistence for the MAP-Elites archive (D-10, D-11).

    Uses asyncpg for async I/O with a direct connection per call (no pool),
    following the pattern established in aerocloud.semantic.persistence.

    Args:
        dsn: asyncpg connection string (postgres://user:pass@host:port/db).
             T-09-07: Never log this value.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    # ------------------------------------------------------------------
    # flush_batch
    # ------------------------------------------------------------------

    async def flush_batch(self, entries: list[ArchiveFlushEntry]) -> int:
        """Upsert a batch of archive entries to PostgreSQL.

        Uses ON CONFLICT (bin_id) DO UPDATE ... WHERE EXCLUDED.fitness >
        archive_v1.fitness to implement the fitness guard (D-10): only update
        an existing cell when the incoming elite has strictly higher fitness.

        Args:
            entries: List of ArchiveFlushEntry objects to persist.
                     Empty list is a no-op returning 0.

        Returns:
            Number of entries processed (len(entries)). Note: asyncpg's
            execute() does not return a per-upsert affected-row count without
            RETURNING; we return the number of entries submitted, not the number
            of cells that actually changed.

        Security (T-09-05):
            All SQL parameters are passed as positional $N arguments.
            bin_id, fitness, BD scalars, descriptor, metadata, params_blob, and
            quality_metrics are NEVER string-interpolated into the query.

        T-09-07: DSN is not logged.
        """
        if not entries:
            return 0

        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                for entry in entries:
                    bd = entry.behavior_descriptor
                    vec_str = _vec_to_pgvector(entry.descriptor_vec)
                    metadata_json = json.dumps(entry.metadata)
                    quality_json = json.dumps(entry.quality_metrics_json)

                    # T-09-05: all values bound as $N — no interpolation
                    await conn.execute(
                        _UPSERT_SQL,
                        entry.bin_id,  # $1 bin_id
                        vec_str,  # $2 descriptor (cast ::vector)
                        entry.fitness,  # $3 fitness
                        metadata_json,  # $4 metadata (cast ::jsonb)
                        bd.shape_fidelity,  # $5 shape_fidelity
                        bd.rotation_ratio,  # $6 rotation_ratio
                        bd.symmetry,  # $7 symmetry
                        bd.semantic_clustering,  # $8 semantic_clustering
                        entry.params_bytes,  # $9 params_blob (BYTEA)
                        quality_json,  # $10 quality_metrics (cast ::jsonb)
                    )

            logger.info(
                "outer_loop.persistence.flush_batch.done",
                n_entries=len(entries),
            )
            return len(entries)
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # load_all
    # ------------------------------------------------------------------

    async def load_all(
        self,
    ) -> list[tuple[str, float, np.ndarray, np.ndarray]]:
        """Load all archive entries from PostgreSQL (D-11: startup resume).

        Fetches all rows that have a non-NULL params_blob (fully persisted
        entries). Ordered by fitness DESC so callers see best elites first.

        Returns:
            List of (bin_id, fitness, measures_4d, solution_flat) tuples where:
                - bin_id: str — archive cell identifier
                - fitness: float — quality score at time of last flush
                - measures_4d: np.ndarray shape (4,) — [shape_fidelity,
                  rotation_ratio, symmetry, semantic_clustering]
                - solution_flat: np.ndarray — params tensor flattened to 1D
                  (restored via bytes_to_params(params_blob).numpy().flatten())

        Returns [] when the table has no rows or no rows with params_blob.

        T-09-07: DSN is not logged.
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(_LOAD_SQL)
            result: list[tuple[str, float, np.ndarray, np.ndarray]] = []
            for row in rows:
                bin_id: str = row["bin_id"]
                fitness: float = float(row["fitness"])

                # measures_4d: BD scalars in canonical order (D-01)
                measures_4d = np.array(
                    [
                        float(row["shape_fidelity"]),
                        float(row["rotation_ratio"]),
                        float(row["symmetry"]),
                        float(row["semantic_clustering"]),
                    ],
                    dtype=np.float32,
                )

                # solution_flat: restore params from BYTEA
                params_tensor = bytes_to_params(bytes(row["params_blob"]))
                solution_flat = params_tensor.numpy().flatten()

                result.append((bin_id, fitness, measures_4d, solution_flat))

            logger.info(
                "outer_loop.persistence.load_all.done",
                n_rows=len(result),
            )
            return result
        finally:
            await conn.close()
