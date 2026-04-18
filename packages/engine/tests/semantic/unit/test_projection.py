"""Unit tests for project_to_2d (Phase 8, SEM-04, D-05, D-06).

BDD Scenario (given/when/then):

  Given a (10, 384) float32 array of random embeddings
  When project_to_2d is called with method="umap"
  Then a (10, 2) float32 array is returned

  Given a (10, 384) float32 array of random embeddings
  When project_to_2d is called with method="tsne"
  Then a (10, 2) float32 array is returned

  Given the same (10, 384) embeddings and seed=42
  When project_to_2d is called twice
  Then the two outputs are identical (determinism)

  Given an unknown method string
  When project_to_2d is called
  Then ProjectionError is raised

  Given only 3 embeddings (fewer than default UMAP n_neighbors)
  When project_to_2d is called with method="umap"
  Then no crash occurs and (3, 2) is returned
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.semantic.errors import ProjectionError
from aerocloud.semantic.projection import project_to_2d


class TestProjectionShape:
    """Tests 1-2: output shape and dtype."""

    def test_umap_returns_n_by_2_float32(
        self, stub_embeddings_10x384: np.ndarray
    ) -> None:
        """Test 1: UMAP projection returns (10, 2) float32."""
        result = project_to_2d(stub_embeddings_10x384, method="umap", seed=42)
        assert result.shape == (10, 2), f"Expected (10, 2), got {result.shape}"
        assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"

    def test_tsne_returns_n_by_2_float32(
        self, stub_embeddings_10x384: np.ndarray
    ) -> None:
        """Test 2: t-SNE projection returns (10, 2) float32."""
        result = project_to_2d(stub_embeddings_10x384, method="tsne", seed=42)
        assert result.shape == (10, 2), f"Expected (10, 2), got {result.shape}"
        assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"


class TestProjectionErrors:
    """Test 3: invalid method raises ProjectionError."""

    def test_invalid_method_raises_projection_error(
        self, stub_embeddings_10x384: np.ndarray
    ) -> None:
        """Test 3: Unknown method raises ProjectionError."""
        with pytest.raises(ProjectionError, match="Unknown projection method"):
            project_to_2d(stub_embeddings_10x384, method="pca")  # type: ignore[arg-type]


class TestProjectionDeterminism:
    """Tests 4-5: same seed produces identical output."""

    def test_umap_same_seed_identical_output(
        self, stub_embeddings_10x384: np.ndarray
    ) -> None:
        """Test 4: UMAP with seed=42 is deterministic across two calls."""
        result1 = project_to_2d(stub_embeddings_10x384, method="umap", seed=42)
        result2 = project_to_2d(stub_embeddings_10x384, method="umap", seed=42)
        assert np.array_equal(result1, result2), (
            "UMAP with same seed must produce identical output on repeated calls"
        )

    def test_tsne_same_seed_identical_output(
        self, stub_embeddings_10x384: np.ndarray
    ) -> None:
        """Test 5: t-SNE with seed=42 is deterministic across two calls."""
        result1 = project_to_2d(stub_embeddings_10x384, method="tsne", seed=42)
        result2 = project_to_2d(stub_embeddings_10x384, method="tsne", seed=42)
        assert np.array_equal(result1, result2), (
            "t-SNE with same seed must produce identical output on repeated calls"
        )


class TestProjectionSmallInput:
    """Test 6: UMAP handles fewer samples than default n_neighbors."""

    def test_umap_small_n_does_not_crash(
        self, stub_embeddings_3x384: np.ndarray
    ) -> None:
        """Test 6: UMAP with N=3 (< default n_neighbors=15) returns (3, 2)."""
        result = project_to_2d(stub_embeddings_3x384, method="umap", seed=42)
        assert result.shape == (3, 2), f"Expected (3, 2) for N=3 input, got {result.shape}"
        assert result.dtype == np.float32
