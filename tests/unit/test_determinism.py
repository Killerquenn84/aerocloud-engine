"""Verifies global seeding produces identical outputs across runs."""

from __future__ import annotations

import numpy as np
import torch

from aerocloud.utils.determinism import set_seed


def _sample() -> tuple[np.ndarray, torch.Tensor]:
    np_arr = np.random.randn(10, 10)
    torch_t = torch.randn(10, 10)
    return np_arr, torch_t


def test_seed_reproducibility() -> None:
    set_seed(42)
    np_a, torch_a = _sample()

    set_seed(42)
    np_b, torch_b = _sample()

    assert np.array_equal(np_a, np_b), "numpy seed not reproducible"
    assert torch.equal(torch_a, torch_b), "torch seed not reproducible"


def test_different_seeds_produce_different_outputs() -> None:
    set_seed(42)
    np_a, torch_a = _sample()

    set_seed(123)
    np_b, torch_b = _sample()

    assert not np.array_equal(np_a, np_b)
    assert not torch.equal(torch_a, torch_b)


def test_set_seed_is_idempotent() -> None:
    # Calling set_seed twice with the same value should produce identical state
    set_seed(42)
    first = np.random.randn(5)
    set_seed(42)
    second = np.random.randn(5)
    assert np.array_equal(first, second)
