"""Shared pytest fixtures for aerocloud.semantic tests (Phase 8).

Provides stub embeddings and sample word surfaces for unit tests that need
to avoid loading the real BERT model (slow, requires network on first run).

Usage:
    Tests that need real model output should use the encode_surfaces function
    directly with ``reset_model()`` teardown (or the monkeypatched model).
    Tests that only need shaped numpy arrays should use stub_embeddings_5x384.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

# Override model cache dir for tests — /var/cache/aerocloud may not be
# writable in CI; /tmp/aerocloud-models is always available.
os.environ.setdefault("MODEL_CACHE_DIR", "/tmp/aerocloud-models")


@pytest.fixture
def stub_embeddings_5x384() -> np.ndarray:
    """Return a (5, 384) float32 array with deterministic random values (seed=42).

    Uses numpy default_rng for reproducibility. NOT from the BERT model —
    use this fixture for shape/validation tests, not semantic tests.
    """
    rng = np.random.default_rng(42)
    return rng.standard_normal((5, 384)).astype(np.float32)


@pytest.fixture
def stub_embeddings_10x384() -> np.ndarray:
    """Return a (10, 384) float32 array with deterministic random values (seed=7).

    Uses numpy default_rng for reproducibility. 10 rows are needed for UMAP
    tests because default n_neighbors=15 requires at least n_neighbors+1 samples;
    the projection.py implementation auto-clamps n_neighbors to min(15, n-1).
    """
    rng = np.random.default_rng(7)
    return rng.standard_normal((10, 384)).astype(np.float32)


@pytest.fixture
def stub_embeddings_3x384() -> np.ndarray:
    """Return a (3, 384) float32 array for small-N edge-case tests (seed=99).

    Used to verify that UMAP does not crash when N < default n_neighbors (15).
    """
    rng = np.random.default_rng(99)
    return rng.standard_normal((3, 384)).astype(np.float32)


@pytest.fixture
def sample_surfaces() -> list[str]:
    """Five diverse English weather words for semantic test fixtures."""
    return ["cloud", "rain", "sun", "wind", "storm"]
