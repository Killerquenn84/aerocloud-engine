"""Reproducibility ID — (input_hash, seed, version) -> output_hash.

References:
    - .planning/phases/02-datenmodell-wiki/02-CONTEXT.md D-05..D-08
"""

from __future__ import annotations

import hashlib

import orjson
from pydantic import Field

from aerocloud import __version__
from aerocloud.models.base import AeroCloudBase


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_input_hash(payload: dict[str, object]) -> str:
    """Return a stable sha256 of a payload, key-sorted, orjson-encoded."""
    serialized = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    return _sha256_hex(serialized)


class ReproducibilityID(AeroCloudBase):
    """Reproducibility identifier for a render run.

    Formed from ``(input_hash, seed, version)`` and resolving to an
    ``output_hash`` that identifies the deterministic result.
    """

    input_hash: str = Field(..., min_length=64, max_length=64)
    seed: int = Field(..., ge=0)
    version: str
    output_hash: str = Field(..., min_length=64, max_length=64)

    @property
    def fingerprint(self) -> str:
        """Stable short identifier combining all fields, for log lines."""
        return f"{self.version}:{self.seed}:{self.input_hash[:12]}->{self.output_hash[:12]}"


def compute_id(
    payload: dict[str, object],
    seed: int,
    output_bytes: bytes | None = None,
    version: str = __version__,
) -> ReproducibilityID:
    """Compute a ReproducibilityID from payload + seed + optional output.

    If ``output_bytes`` is None, the output_hash is derived from (input_hash, seed,
    version) — useful before the actual render runs. Once the real output is
    available, call :func:`compute_id` again with the raw bytes.
    """
    input_hash = canonical_input_hash(payload)
    if output_bytes is None:
        seed_bytes = f"{version}:{seed}:{input_hash}".encode()
        output_hash = _sha256_hex(seed_bytes)
    else:
        output_hash = _sha256_hex(output_bytes)

    return ReproducibilityID(
        input_hash=input_hash,
        seed=seed,
        version=version,
        output_hash=output_hash,
    )
