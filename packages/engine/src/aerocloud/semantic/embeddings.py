"""BERT embedding encode + lazy singleton model (Phase 8, SEM-01, SEM-02).

Public API:
- get_model() -> SentenceTransformer: Returns the cached singleton, loading
  and warming it up on first call.
- reset_model() -> None: Clears the singleton (for testing only).
- encode_surfaces(surfaces) -> np.ndarray: Encodes a list of word surfaces
  into an (N, 384) float32 numpy array.

Design decisions (from .planning/phases/08-semantic-vector-space/08-RESEARCH.md):
- D-01: Model: sentence-transformers/all-MiniLM-L6-v2 (22M params, 384-dim).
- D-02: Singleton with warm-up: lazy init on first encode_surfaces() call;
  warm-up runs a single ["warm"] encode to JIT-compile the tokenizer graph.
- D-03: Batch encoding via sentence-transformers with embedding_batch_size from
  settings; convert_to_numpy=True returns np.ndarray directly.
- T-08-01: DoS guards: list > MAX_SURFACE_COUNT or surface > MAX_SURFACE_CHARS
  raise EmbeddingError before any model inference.

Determinism:
- all-MiniLM-L6-v2 is a deterministic feedforward model on CPU (no dropout
  at inference time by default). Two calls with identical input produce
  bit-exact identical output.
"""

from __future__ import annotations

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from aerocloud.config import settings
from aerocloud.semantic.errors import EmbeddingError

logger = structlog.get_logger(__name__)

# DoS guards (T-08-01: STRIDE Threat Register)
MAX_SURFACE_COUNT: int = 10_000
MAX_SURFACE_CHARS: int = 512

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Return the cached SentenceTransformer singleton, loading on first call.

    On first call:
    1. Loads all-MiniLM-L6-v2 from model_cache_dir (downloads on cache miss).
    2. Runs a warm-up encode(["warm"]) to trigger JIT compilation of the
       tokenizer graph (SEM-02).
    3. Caches the model instance in module-level _model.

    Subsequent calls return the cached instance immediately (same id()).

    Returns:
        The cached SentenceTransformer instance.
    """
    global _model  # noqa: PLW0603
    if _model is None:
        logger.info(
            "semantic.embeddings.loading_model",
            model="all-MiniLM-L6-v2",
            cache_dir=settings.model_cache_dir,
        )
        _model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            cache_folder=settings.model_cache_dir,
        )
        # SEM-02: warm-up to JIT the tokenizer graph
        _model.encode(
            ["warm"],
            batch_size=1,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        logger.info("semantic.embeddings.model_ready")
    return _model


def reset_model() -> None:
    """Clear the singleton (for testing only — do NOT call in production code).

    Allows test fixtures to isolate singleton state between test cases.
    After reset, the next call to get_model() or encode_surfaces() will
    re-load and re-warm the model.
    """
    global _model  # noqa: PLW0603
    _model = None


def encode_surfaces(surfaces: list[str]) -> np.ndarray:
    """Encode a list of word surfaces into (N, 384) float32 BERT embeddings.

    Args:
        surfaces: Non-empty list of word surface strings to encode.
            Must not exceed MAX_SURFACE_COUNT (10_000) items.
            Each string must not exceed MAX_SURFACE_CHARS (512) characters.

    Returns:
        Float32 numpy array of shape (N, 384) where N == len(surfaces).

    Raises:
        EmbeddingError: If surfaces is empty, exceeds MAX_SURFACE_COUNT,
            or any individual surface exceeds MAX_SURFACE_CHARS.

    Example:
        >>> embeddings = encode_surfaces(["hello", "world"])
        >>> embeddings.shape
        (2, 384)
        >>> embeddings.dtype
        dtype('float32')
    """
    # T-08-01: DoS guard — empty list
    if not surfaces:
        raise EmbeddingError("Cannot encode empty surface list")

    # T-08-01: DoS guard — too many surfaces
    if len(surfaces) > MAX_SURFACE_COUNT:
        raise EmbeddingError(f"Surface list too long: {len(surfaces)} > limit {MAX_SURFACE_COUNT}")

    # T-08-01: DoS guard — surface exceeds BERT max token length
    for surface in surfaces:
        if len(surface) > MAX_SURFACE_CHARS:
            raise EmbeddingError(
                f"Surface too long: {len(surface)} chars > max {MAX_SURFACE_CHARS}"
            )

    model = get_model()
    result = model.encode(
        surfaces,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    return np.asarray(result, dtype=np.float32)
