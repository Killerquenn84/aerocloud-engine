"""Unit tests for cosine_similarity_matrix (Phase 8, SEM-03, D-04).

BDD Scenario (given/when/then):

  Given a (5, 384) float32 array of random embeddings
  When cosine_similarity_matrix is called
  Then a (5, 5) float32 symmetric matrix with 1.0 diagonal is returned
  And all values are in [-1.0, 1.0]

Edge cases:
  Given a (1, 384) embedding
  When cosine_similarity_matrix is called
  Then a (1, 1) matrix with value 1.0 is returned

  Given a (0, 384) empty array
  When cosine_similarity_matrix is called
  Then SemanticError is raised
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.semantic.cosine import cosine_similarity_matrix
from aerocloud.semantic.errors import SemanticError


class TestCosineShape:
    """Test 1: shape and dtype."""

    def test_returns_n_by_n_float32(self, stub_embeddings_5x384: np.ndarray) -> None:
        result = cosine_similarity_matrix(stub_embeddings_5x384)
        assert result.shape == (5, 5), f"Expected (5, 5), got {result.shape}"
        assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"


class TestCosineProperties:
    """Tests 2-4: mathematical properties."""

    def test_diagonal_is_one(self, stub_embeddings_5x384: np.ndarray) -> None:
        """Test 2: self-similarity is 1.0."""
        result = cosine_similarity_matrix(stub_embeddings_5x384)
        np.testing.assert_allclose(
            np.diag(result),
            np.ones(5, dtype=np.float32),
            atol=1e-6,
            err_msg="Diagonal must be all 1.0 (self-similarity)",
        )

    def test_matrix_is_symmetric(self, stub_embeddings_5x384: np.ndarray) -> None:
        """Test 3: M[i,j] == M[j,i]."""
        result = cosine_similarity_matrix(stub_embeddings_5x384)
        np.testing.assert_allclose(
            result,
            result.T,
            atol=1e-6,
            err_msg="Cosine similarity matrix must be symmetric",
        )

    def test_values_bounded_minus_one_to_one(
        self, stub_embeddings_5x384: np.ndarray
    ) -> None:
        """Test 4: all values in [-1.0, 1.0]."""
        result = cosine_similarity_matrix(stub_embeddings_5x384)
        assert np.all(result >= -1.0 - 1e-6), "All values must be >= -1.0"
        assert np.all(result <= 1.0 + 1e-6), "All values must be <= 1.0"


class TestCosineEdgeCases:
    """Tests 5-6: edge cases."""

    def test_single_word_returns_one_by_one(self) -> None:
        """Test 5: (1, 384) input returns (1, 1) matrix with value 1.0."""
        rng = np.random.default_rng(0)
        single = rng.standard_normal((1, 384)).astype(np.float32)
        result = cosine_similarity_matrix(single)
        assert result.shape == (1, 1), f"Expected (1, 1), got {result.shape}"
        np.testing.assert_allclose(result[0, 0], 1.0, atol=1e-6)

    def test_empty_input_raises_semantic_error(self) -> None:
        """Test 6: (0, 384) empty array raises SemanticError."""
        empty = np.zeros((0, 384), dtype=np.float32)
        with pytest.raises(SemanticError):
            cosine_similarity_matrix(empty)
