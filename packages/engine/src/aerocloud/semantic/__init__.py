"""aerocloud.semantic — Phase 8 Semantic Vector Space public package.

Provides BERT embedding inference, cosine similarity matrix computation,
2D projection (UMAP / t-SNE), Sinkhorn-Knopp Optimal Transport,
and semantic-aware word cloud layout.

Phase 8 plans:
- 08-01: BERT embeddings + model singleton warm-up (this package scaffold)
- 08-02: Cosine similarity matrix + UMAP / t-SNE 2D projection
- 08-03: Sinkhorn-Knopp Optimal Transport
- 08-04: Semantic-aware placement integration
- 08-05: Phase exit gate + 3-KI review

Public API:
    SEM-01, SEM-02 — BERT embeddings:
        encode_surfaces(surfaces) -> np.ndarray
        get_model() -> SentenceTransformer
        reset_model() -> None  (testing only)

    SEM-03 — Cosine similarity:
        cosine_similarity_matrix(embeddings) -> np.ndarray

    SEM-04 — 2D projection:
        project_to_2d(embeddings, method, seed) -> np.ndarray

    SEM-07 — pgvector persistence (D-13, D-14, D-15):
        store_embeddings(surfaces, embeddings) -> int
        load_cached_embeddings(surfaces) -> dict[str, np.ndarray]

Error hierarchy:
    SemanticError
    ├── EmbeddingError          (encode failures, DoS guards)
    ├── SinkhornNonConvergenceError (Optimal Transport)
    └── ProjectionError         (UMAP / t-SNE)

References:
    - .planning/phases/08-semantic-vector-space/08-01-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-02-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-05-PLAN.md
    - AeroCloud Blueprint Teil II §2.1 (BERT), §2.2 (Sinkhorn)
"""

from __future__ import annotations

from aerocloud.semantic.cosine import cosine_similarity_matrix
from aerocloud.semantic.embeddings import encode_surfaces, get_model, reset_model
from aerocloud.semantic.transport import compute_transport
from aerocloud.semantic.warm_start import semantic_warm_start
from aerocloud.semantic.errors import (
    EmbeddingError,
    ProjectionError,
    SemanticError,
    SinkhornNonConvergenceError,
)
from aerocloud.semantic.persistence import load_cached_embeddings, store_embeddings
from aerocloud.semantic.projection import project_to_2d

__all__ = [  # noqa: RUF022
    # Core inference (SEM-01, SEM-02)
    "encode_surfaces",
    "get_model",
    "reset_model",
    # Cosine similarity (SEM-03)
    "cosine_similarity_matrix",
    # 2D projection (SEM-04)
    "project_to_2d",
    # Sinkhorn-Knopp Optimal Transport (SEM-05, SEM-06)
    "compute_transport",
    # Semantic warm-start glue function (SEM-08)
    "semantic_warm_start",
    # pgvector persistence cache (SEM-07, D-13, D-14)
    "load_cached_embeddings",
    "store_embeddings",
    # Error hierarchy — alphabetical within group
    "EmbeddingError",
    "ProjectionError",
    "SemanticError",
    "SinkhornNonConvergenceError",
]
