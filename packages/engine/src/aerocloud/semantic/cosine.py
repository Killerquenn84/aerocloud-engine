"""Cosine similarity matrix computation for BERT embeddings (Phase 8, SEM-03, D-04).

Public API:
    cosine_similarity_matrix(embeddings) -> np.ndarray

Design decisions:
    D-04: Use sklearn.metrics.pairwise.cosine_similarity for numerically stable
    pairwise cosine computation. Returns (N, N) float32 symmetric matrix.

References:
    - .planning/phases/08-semantic-vector-space/08-02-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-RESEARCH.md §D-04
"""

from __future__ import annotations

import numpy as np
import structlog
from sklearn.metrics.pairwise import cosine_similarity

from aerocloud.semantic.errors import SemanticError

logger = structlog.get_logger(__name__)


def cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity for (N, D) embeddings.

    Args:
        embeddings: (N, D) float32 array where D is embedding dimension.
            Typically N words with D=384 (all-MiniLM-L6-v2 output).

    Returns:
        (N, N) float32 symmetric matrix with 1.0 on diagonal.
        Entry [i, j] is the cosine similarity between embeddings[i] and embeddings[j].

    Raises:
        SemanticError: If embeddings is empty (N=0) or not a 2D array.

    Example:
        >>> rng = np.random.default_rng(42)
        >>> emb = rng.standard_normal((5, 384)).astype(np.float32)
        >>> sim = cosine_similarity_matrix(emb)
        >>> sim.shape
        (5, 5)
        >>> sim.dtype
        dtype('float32')
        >>> np.allclose(np.diag(sim), 1.0, atol=1e-6)
        True
    """
    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        raise SemanticError(
            f"embeddings must be a 2D array with N>0 rows, got shape {embeddings.shape}"
        )

    sim = cosine_similarity(embeddings).astype(np.float32)
    logger.debug(
        "semantic.cosine.computed",
        n=embeddings.shape[0],
        d=embeddings.shape[1],
        output_shape=sim.shape,
    )
    return sim
