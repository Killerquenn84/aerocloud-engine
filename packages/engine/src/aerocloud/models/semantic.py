"""Pydantic domain models for the semantic vector space (Phase 8).

Models:
- EmbeddingResult: validated (N, 384) float32 BERT embedding matrix + surfaces
- TransportPlan: validated (N, N) doubly-stochastic Sinkhorn-Knopp output

Design decisions:
- strict=False + arbitrary_types_allowed=True: numpy arrays cannot pass strict
  type coercion; we convert to float32 in model_post_init instead (D-03).
- frozen=True: models are immutable after construction (AeroCloudBase pattern).
- Shape validation in model_post_init: Pydantic field validators run before
  __init__ returns; post-init is the correct hook for numpy shape checks.

References:
- .planning/phases/08-semantic-vector-space/08-01-PLAN.md Step 3
- AeroCloud Blueprint Teil II §2.1 (BERT embeddings)
"""

from __future__ import annotations

import numpy as np
from pydantic import ConfigDict

from aerocloud.models.base import AeroCloudBase


class EmbeddingResult(AeroCloudBase):
    """Validated BERT embedding result for a list of word surfaces.

    Attributes:
        surfaces: Tuple of word surfaces in the same order as embeddings rows.
        embeddings: Float32 numpy array of shape (N, 384), where N == len(surfaces).

    Raises:
        ValueError: If embeddings.ndim != 2, embeddings.shape[1] != 384, or
            row count does not match len(surfaces).

    Example:
        >>> import numpy as np
        >>> result = EmbeddingResult(
        ...     surfaces=("hello", "world"),
        ...     embeddings=np.zeros((2, 384), dtype=np.float32),
        ... )
        >>> result.embeddings.shape
        (2, 384)
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,  # allow numpy array coercion in model_post_init
        arbitrary_types_allowed=True,
    )

    surfaces: tuple[str, ...]
    embeddings: np.ndarray  # (N, 384) float32

    def model_post_init(self, __context: object) -> None:
        """Coerce embeddings to float32 and validate shape invariants."""
        arr = np.asarray(self.embeddings, dtype=np.float32)
        object.__setattr__(self, "embeddings", arr)
        if arr.ndim != 2 or arr.shape[1] != 384:
            raise ValueError(f"embeddings must be shape (N, 384), got {arr.shape}")
        if arr.shape[0] != len(self.surfaces):
            raise ValueError(
                f"embeddings rows ({arr.shape[0]}) != surfaces count ({len(self.surfaces)})"
            )


class TransportPlan(AeroCloudBase):
    """Validated Sinkhorn-Knopp optimal transport plan (Phase 8 D-09).

    Attributes:
        transport_matrix: Float64 numpy array of shape (N, N), doubly stochastic
            (rows and columns sum to 1/N after normalization).
        eps_used: The final epsilon value at convergence.
        iterations: Number of Sinkhorn iterations performed.

    Raises:
        ValueError: If transport_matrix is not 2-D or not square.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=False,  # allow numpy array coercion
        arbitrary_types_allowed=True,
    )

    transport_matrix: np.ndarray  # (N, N) float64, doubly stochastic
    eps_used: float
    iterations: int

    def model_post_init(self, __context: object) -> None:
        """Coerce transport_matrix to float64 and validate shape invariants."""
        arr = np.asarray(self.transport_matrix, dtype=np.float64)
        object.__setattr__(self, "transport_matrix", arr)
        if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
            raise ValueError(f"transport_matrix must be square (N, N), got {arr.shape}")
