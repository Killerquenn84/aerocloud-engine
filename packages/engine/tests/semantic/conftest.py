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
def sample_surfaces() -> list[str]:
    """Five diverse English weather words for semantic test fixtures."""
    return ["cloud", "rain", "sun", "wind", "storm"]
