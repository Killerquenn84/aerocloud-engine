"""Typed error hierarchy for the semantic package (Phase 8).

All errors derive from `SemanticError`. Downstream modules pattern-match on
subclasses rather than parsing log messages.

Design decisions:
- D-01: EmbeddingError covers encode failures (empty input, tokeniser overflow)
- D-09: SinkhornNonConvergenceError raised when eps annealing exhausts max_iter
- D-06: ProjectionError covers UMAP / t-SNE projection failures
- T-08-01: EmbeddingError raised for DoS-guard violations (>10_000 surfaces,
  surface > 512 chars)

See .planning/phases/08-semantic-vector-space/08-RESEARCH.md for threat register.
"""

from __future__ import annotations


class SemanticError(Exception):
    """Base class for all aerocloud.semantic exceptions."""


class EmbeddingError(SemanticError):
    """Raised when BERT encoding fails or input violates guards (D-01, T-08-01).

    Examples:
    - Empty surface list passed to encode_surfaces()
    - Surface list length > MAX_SURFACE_COUNT (DoS guard, T-08-01)
    - Individual surface length > MAX_SURFACE_CHARS (DoS guard, T-08-01)
    - sentence-transformers runtime failure
    """


class SinkhornNonConvergenceError(SemanticError):
    """Raised when Sinkhorn-Knopp fails to converge within max_iter (D-09).

    Callers should catch this and fall back to cosine-distance ranking or
    increase sinkhorn_eps_init in config.
    """


class ProjectionError(SemanticError):
    """Raised when 2D projection (UMAP or t-SNE) fails (D-06).

    Typical causes: too few samples for UMAP (< n_neighbors + 1), NaN inputs
    from degenerate embeddings, or sklearn convergence failure for t-SNE.
    """
