"""Unit tests for aerocloud.semantic.embeddings (Phase 8 Plan 01).

TDD Red-Green workflow:
- RED: Tests written against the interface spec BEFORE implementation
- GREEN: Implementation written to pass these tests

Test coverage per plan spec:
- Test 1: encode_surfaces(["hello", "world"]) returns ndarray shape (2, 384) float32
- Test 2: encode_surfaces(["single"]) returns ndarray shape (1, 384) float32
- Test 3: encode_surfaces([]) raises EmbeddingError (empty input guard)
- Test 4: get_model() returns same object on second call (singleton identity)
- Test 5: EmbeddingResult validates (2, 384) array; wrong shape raises ValidationError
- Test 6: Determinism — encode_surfaces(["test"]) identical across two calls

Threat model coverage:
- T-08-01: DoS guard — list > MAX_SURFACE_COUNT raises EmbeddingError
- T-08-01: DoS guard — surface > MAX_SURFACE_CHARS raises EmbeddingError

Design notes:
- Real BERT model is used in all encode tests (all-MiniLM-L6-v2, 22MB download).
  Tests are marked `@pytest.mark.slow` but NOT skipped in CI — they are the
  acceptance gate for SEM-01 (BERT inference) and SEM-02 (model warm-up).
- reset_model() is called in a fixture to ensure singleton isolation between tests.
- The model singleton test (Test 4) checks identity with id() — not equality.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from aerocloud.models.semantic import EmbeddingResult
from aerocloud.semantic.errors import EmbeddingError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Ensure the model singleton is reset before each test for isolation."""
    from aerocloud import semantic  # noqa: PLC0415

    semantic.reset_model()
    yield
    semantic.reset_model()


# ---------------------------------------------------------------------------
# Test 1: Multi-surface encode shape + dtype
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_encode_surfaces_two_words_returns_2x384_float32() -> None:
    """encode_surfaces(['hello', 'world']) returns ndarray shape (2, 384) float32."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    result = encode_surfaces(["hello", "world"])

    assert isinstance(result, np.ndarray), "Result must be numpy ndarray"
    assert result.shape == (2, 384), f"Expected (2, 384), got {result.shape}"
    assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"


# ---------------------------------------------------------------------------
# Test 2: Single surface encode
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_encode_surfaces_single_word_returns_1x384_float32() -> None:
    """encode_surfaces(['single']) returns ndarray shape (1, 384) float32."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    result = encode_surfaces(["single"])

    assert isinstance(result, np.ndarray), "Result must be numpy ndarray"
    assert result.shape == (1, 384), f"Expected (1, 384), got {result.shape}"
    assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"


# ---------------------------------------------------------------------------
# Test 3: Empty input guard
# ---------------------------------------------------------------------------


def test_encode_surfaces_empty_list_raises_embedding_error() -> None:
    """encode_surfaces([]) raises EmbeddingError (not any other exception)."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    with pytest.raises(EmbeddingError, match="[Ee]mpty"):
        encode_surfaces([])


# ---------------------------------------------------------------------------
# Test 4: Singleton identity
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_get_model_returns_cached_singleton() -> None:
    """get_model() returns the same object on second call (id equality)."""
    from aerocloud.semantic import get_model  # noqa: PLC0415

    model_a = get_model()
    model_b = get_model()

    assert id(model_a) == id(model_b), (
        f"Singleton broken: id(a)={id(model_a)} != id(b)={id(model_b)}"
    )


# ---------------------------------------------------------------------------
# Test 5: EmbeddingResult Pydantic validation
# ---------------------------------------------------------------------------


def test_embedding_result_validates_correct_shape() -> None:
    """EmbeddingResult validates a (2, 384) float32 array."""
    arr = np.zeros((2, 384), dtype=np.float32)
    result = EmbeddingResult(surfaces=("a", "b"), embeddings=arr)

    assert result.embeddings.shape == (2, 384)
    assert result.embeddings.dtype == np.float32


def test_embedding_result_rejects_wrong_dim() -> None:
    """EmbeddingResult raises ValidationError for wrong embedding dimension."""
    arr = np.zeros((2, 512), dtype=np.float32)  # wrong dim: 512 instead of 384

    with pytest.raises((ValidationError, ValueError)):
        EmbeddingResult(surfaces=("a", "b"), embeddings=arr)


def test_embedding_result_rejects_row_count_mismatch() -> None:
    """EmbeddingResult raises ValueError when rows != len(surfaces)."""
    arr = np.zeros((3, 384), dtype=np.float32)  # 3 rows but only 2 surfaces

    with pytest.raises((ValidationError, ValueError)):
        EmbeddingResult(surfaces=("a", "b"), embeddings=arr)


def test_embedding_result_rejects_1d_array() -> None:
    """EmbeddingResult raises ValueError for 1D array (wrong ndim)."""
    arr = np.zeros(384, dtype=np.float32)  # 1D, not 2D

    with pytest.raises((ValidationError, ValueError)):
        EmbeddingResult(surfaces=("a",), embeddings=arr)


# ---------------------------------------------------------------------------
# Test 6: Determinism
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_encode_surfaces_deterministic_across_calls() -> None:
    """encode_surfaces(['test']) produces bit-exact identical output on two calls."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    result_a = encode_surfaces(["test"])
    result_b = encode_surfaces(["test"])

    assert np.array_equal(result_a, result_b), (
        "encode_surfaces is not deterministic: two calls produced different results"
    )


# ---------------------------------------------------------------------------
# Threat model: T-08-01 DoS guards
# ---------------------------------------------------------------------------


def test_encode_surfaces_rejects_oversized_list() -> None:
    """T-08-01: List > MAX_SURFACE_COUNT (10_000) raises EmbeddingError."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    oversized = ["word"] * 10_001

    with pytest.raises(EmbeddingError, match="[Ll]imit|[Tt]oo many|[Mm]ax"):
        encode_surfaces(oversized)


def test_encode_surfaces_rejects_too_long_surface() -> None:
    """T-08-01: Surface > MAX_SURFACE_CHARS (512) raises EmbeddingError."""
    from aerocloud.semantic import encode_surfaces  # noqa: PLC0415

    too_long = ["x" * 513]

    with pytest.raises(EmbeddingError, match="[Ll]ong|[Cc]har|[Mm]ax"):
        encode_surfaces(too_long)
