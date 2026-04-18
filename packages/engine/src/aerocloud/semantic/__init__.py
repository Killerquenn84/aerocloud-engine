"""aerocloud.semantic — Phase 8 Semantic Vector Space public package.

Provides BERT embedding inference, Sinkhorn-Knopp Optimal Transport,
and 2D projection (UMAP / t-SNE) for semantic-aware word cloud layout.

Phase 8 plans:
- 08-01: BERT embeddings + model singleton warm-up (this package scaffold)
- 08-02: Cosine similarity + distance matrix
- 08-03: UMAP / t-SNE 2D projection for warm-start initialization
- 08-04: Sinkhorn-Knopp Optimal Transport
- 08-05: Semantic-aware placement integration
- 08-06: Phase exit gate + 3-KI review

Public API (SEM-01, SEM-02):
    encode_surfaces(surfaces) -> np.ndarray
    get_model() -> SentenceTransformer
    reset_model() -> None  (testing only)

Error hierarchy:
    SemanticError
    ├── EmbeddingError          (encode failures, DoS guards)
    ├── SinkhornNonConvergenceError (Optimal Transport)
    └── ProjectionError         (UMAP / t-SNE)

References:
    - .planning/phases/08-semantic-vector-space/08-01-PLAN.md
    - AeroCloud Blueprint Teil II §2.1 (BERT), §2.2 (Sinkhorn)
"""

from __future__ import annotations

from aerocloud.semantic.embeddings import encode_surfaces, get_model, reset_model
from aerocloud.semantic.errors import (
    EmbeddingError,
    ProjectionError,
    SemanticError,
    SinkhornNonConvergenceError,
)

__all__ = [  # noqa: RUF022
    # Core inference (SEM-01, SEM-02) — exported first by functional group
    "encode_surfaces",
    "get_model",
    "reset_model",
    # Error hierarchy — alphabetical within group
    "EmbeddingError",
    "ProjectionError",
    "SemanticError",
    "SinkhornNonConvergenceError",
]
