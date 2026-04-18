"""UMAP / t-SNE 2D projection for semantic warm-start initialization (Phase 8, SEM-04).

Public API:
    project_to_2d(embeddings, method, seed) -> np.ndarray

Design decisions:
    D-05: UMAP is the primary method — faster convergence, better topology
    preservation at large N compared to t-SNE.
    D-06: t-SNE is the fallback — slower but well-understood; caller selects
    via settings.projection_method or explicit method argument.

    Small-N guard: UMAP n_neighbors is auto-clamped to min(15, max(2, N-1))
    to avoid "n_neighbors must be smaller than n_samples" errors when the word
    cloud has fewer words than the UMAP neighbourhood size.

    Perplexity guard: t-SNE perplexity is auto-clamped to min(30, max(1, N-1))
    to avoid "perplexity must be less than n_samples" errors.

References:
    - .planning/phases/08-semantic-vector-space/08-02-PLAN.md
    - .planning/phases/08-semantic-vector-space/08-RESEARCH.md §D-05, §D-06
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import structlog

from aerocloud.config import settings
from aerocloud.semantic.errors import ProjectionError

logger = structlog.get_logger(__name__)


def project_to_2d(
    embeddings: np.ndarray,
    method: Literal["umap", "tsne"] | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """Project (N, D) embeddings to (N, 2) using UMAP or t-SNE.

    Args:
        embeddings: (N, D) float32 array. Typically (N, 384) from all-MiniLM-L6-v2.
        method: Projection method — "umap" or "tsne". Defaults to
            settings.projection_method (environment-configurable, default "umap").
        seed: Random seed for reproducibility. Defaults to settings.seed (42).
            Two calls with the same (embeddings, method, seed) produce bit-equal output.

    Returns:
        (N, 2) float32 array of 2D canvas positions for warm-start initialization.

    Raises:
        ProjectionError: If method is not "umap" or "tsne", or if the underlying
            library raises an unrecoverable error.

    Example:
        >>> rng = np.random.default_rng(42)
        >>> emb = rng.standard_normal((10, 384)).astype(np.float32)
        >>> coords = project_to_2d(emb, method="umap", seed=42)
        >>> coords.shape
        (10, 2)
        >>> coords.dtype
        dtype('float32')
    """
    effective_method = method if method is not None else settings.projection_method
    effective_seed = seed if seed is not None else settings.seed
    n = embeddings.shape[0]

    logger.debug(
        "semantic.projection.start",
        method=effective_method,
        n=n,
        seed=effective_seed,
    )

    if effective_method == "umap":
        coords = _umap_project(embeddings, n=n, seed=effective_seed)
    elif effective_method == "tsne":
        coords = _tsne_project(embeddings, n=n, seed=effective_seed)
    else:
        raise ProjectionError(
            f"Unknown projection method: {effective_method!r}. Use 'umap' or 'tsne'."
        )

    result = np.asarray(coords, dtype=np.float32)
    logger.debug(
        "semantic.projection.complete",
        method=effective_method,
        n=n,
        output_shape=result.shape,
    )
    return result


def _umap_project(embeddings: np.ndarray, *, n: int, seed: int) -> np.ndarray:
    """Internal UMAP projection helper (D-05).

    Clamps n_neighbors to [2, N-1] to handle small-N inputs gracefully.

    For very small N (< 4), UMAP's spectral layout (eigsh) fails with sparse
    matrices when k >= N. We fall back to PCA-based init in that case to avoid
    the scipy ARPACK error while still returning the correct (N, 2) shape.
    """
    import umap  # noqa: PLC0415 — lazy import to keep module cheap for CPU-only envs

    n_neighbors = min(15, max(2, n - 1))
    # UMAP spectral layout requires k < N in eigsh; for N < 4 this cannot be
    # satisfied with the default spectral init. Use "random" init as fallback.
    init: str = "spectral" if n >= 4 else "random"
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        min_dist=0.1,
        metric="cosine",
        random_state=seed,
        init=init,
    )
    return reducer.fit_transform(embeddings.astype(np.float32))  # type: ignore[no-any-return]


def _tsne_project(embeddings: np.ndarray, *, n: int, seed: int) -> np.ndarray:
    """Internal t-SNE projection helper (D-06).

    Clamps perplexity to [1, N-1] to handle small-N inputs gracefully.
    Uses PCA init for deterministic initialisation independent of random_state.
    """
    from sklearn.manifold import TSNE  # noqa: PLC0415

    perplexity = min(30.0, max(1.0, float(n - 1)))
    reducer = TSNE(
        n_components=2,
        perplexity=perplexity,
        random_state=seed,
        init="pca",
    )
    return reducer.fit_transform(embeddings.astype(np.float32))  # type: ignore[no-any-return]
