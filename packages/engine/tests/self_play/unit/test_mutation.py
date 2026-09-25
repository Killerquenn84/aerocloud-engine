"""Unit tests for mutation operators (Plan 10-02, Task 1 — TDD RED).

Tests: structure_aware_mutate, uniform_crossover, sample_parents
Design: D-04 (Gaussian perturbation on flat array), D-05 (uniform crossover
        p=0.5, Monte-Carlo parent sampling), D-06 (structure-aware reshape (N,4)
        with per-column sigma).

TDD approach: All tests written before implementation. Tests describe the
expected contract; mutation.py must satisfy them.
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.self_play.config import SelfPlayConfig
from aerocloud.self_play.mutation import (
    sample_parents,
    structure_aware_mutate,
    uniform_crossover,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_solution(n_words: int = 10, seed: int = 0) -> np.ndarray:
    """Create a flat solution array of shape (n_words * 4,) with values in (0, 1)."""
    rng = np.random.default_rng(seed)
    return rng.random(n_words * 4).astype(np.float64)


def _make_config(**kwargs: float | int) -> SelfPlayConfig:
    """Create SelfPlayConfig, optionally overriding fields."""
    return SelfPlayConfig(**kwargs)


def _make_archive_data(n_elites: int = 5, n_words: int = 10) -> dict:  # type: ignore[type-arg]
    """Build a minimal archive data dict mimicking ArchiveWrapper.data()."""
    rng = np.random.default_rng(7)
    solutions = rng.random((n_elites, n_words * 4)).astype(np.float64)
    measures = rng.random((n_elites, 4)).astype(np.float64)
    objectives = rng.random(n_elites).astype(np.float64)
    return {
        "solution": solutions,
        "measures": measures,
        "objective": objectives,
    }


# ---------------------------------------------------------------------------
# Tests: structure_aware_mutate
# ---------------------------------------------------------------------------


def test_structure_aware_mutate_shape_preserved() -> None:
    """Output shape must equal input shape after mutation."""
    solution = _make_solution(n_words=10)
    config = _make_config()
    rng = np.random.default_rng(42)

    result = structure_aware_mutate(solution, config, rng)

    assert result.shape == solution.shape, (
        f"Expected shape {solution.shape}, got {result.shape}"
    )


def test_structure_aware_mutate_deterministic() -> None:
    """Same seed must produce identical output."""
    solution = _make_solution(n_words=8, seed=1)
    config = _make_config()

    rng1 = np.random.default_rng(42)
    result1 = structure_aware_mutate(solution, config, rng1)

    rng2 = np.random.default_rng(42)
    result2 = structure_aware_mutate(solution, config, rng2)

    np.testing.assert_array_equal(result1, result2, err_msg="Results should be identical for same seed")


def test_structure_aware_mutate_changes_values() -> None:
    """Output must differ from input (noise must be added with nonzero sigma)."""
    solution = _make_solution(n_words=20, seed=5)
    config = _make_config()  # default sigmas > 0
    rng = np.random.default_rng(42)

    result = structure_aware_mutate(solution, config, rng)

    # With nonzero sigma and a 80-element array, not all elements should be unchanged
    assert not np.array_equal(result, solution), "Mutated solution should differ from input"


def test_structure_aware_mutate_per_column_sigma() -> None:
    """Position columns (0,1) should have larger noise magnitude than scale column (2).

    sigma_xy=0.05 > sigma_scale=0.02, so the std of noise across position
    columns should be larger than on the scale column when tested over many runs.
    """
    solution = np.zeros(10 * 4, dtype=np.float64)  # all zeros baseline
    config = _make_config()  # sigma_xy=0.05, sigma_scale=0.02, sigma_theta=0.1

    n_runs = 1000
    noises = np.zeros((n_runs, len(solution)))
    for i in range(n_runs):
        rng = np.random.default_rng(i)
        noises[i] = structure_aware_mutate(solution, config, rng) - solution

    # Reshape to (n_runs, n_words, 4) to compare per-column noise
    n_words = 10
    noises_3d = noises.reshape(n_runs, n_words, 4)

    std_xy_col0 = float(np.std(noises_3d[:, :, 0]))
    std_scale_col2 = float(np.std(noises_3d[:, :, 2]))
    std_theta_col3 = float(np.std(noises_3d[:, :, 3]))

    # sigma_xy=0.05 > sigma_scale=0.02  ⟹ position noise std > scale noise std
    assert std_xy_col0 > std_scale_col2, (
        f"Position noise std ({std_xy_col0:.4f}) should exceed scale noise std ({std_scale_col2:.4f})"
    )
    # sigma_theta=0.1 > sigma_xy=0.05  ⟹ theta noise std > position noise std
    assert std_theta_col3 > std_xy_col0, (
        f"Theta noise std ({std_theta_col3:.4f}) should exceed position noise std ({std_xy_col0:.4f})"
    )


# ---------------------------------------------------------------------------
# Tests: uniform_crossover
# ---------------------------------------------------------------------------


def test_uniform_crossover_p0_returns_parent_b() -> None:
    """p=0.0 means mask is always False → result is parent_b."""
    rng = np.random.default_rng(42)
    parent_a = np.ones(20, dtype=np.float64)
    parent_b = np.zeros(20, dtype=np.float64)

    result = uniform_crossover(parent_a, parent_b, rng, p=0.0)

    np.testing.assert_array_equal(result, parent_b)


def test_uniform_crossover_p1_returns_parent_a() -> None:
    """p=1.0 means mask is always True → result is parent_a."""
    rng = np.random.default_rng(42)
    parent_a = np.ones(20, dtype=np.float64)
    parent_b = np.zeros(20, dtype=np.float64)

    result = uniform_crossover(parent_a, parent_b, rng, p=1.0)

    np.testing.assert_array_equal(result, parent_a)


def test_uniform_crossover_deterministic() -> None:
    """Same seed must produce identical crossover result."""
    parent_a = np.arange(20, dtype=np.float64)
    parent_b = np.arange(20, dtype=np.float64) + 100.0

    rng1 = np.random.default_rng(42)
    result1 = uniform_crossover(parent_a, parent_b, rng1)

    rng2 = np.random.default_rng(42)
    result2 = uniform_crossover(parent_a, parent_b, rng2)

    np.testing.assert_array_equal(result1, result2)


# ---------------------------------------------------------------------------
# Tests: sample_parents
# ---------------------------------------------------------------------------


def test_sample_parents_returns_two_solutions() -> None:
    """Both returned parents must have the correct shape (solution_dim,)."""
    n_words = 10
    archive_data = _make_archive_data(n_elites=5, n_words=n_words)
    rng = np.random.default_rng(42)

    parent_a, parent_b = sample_parents(archive_data, rng)

    assert parent_a.shape == (n_words * 4,), f"parent_a shape mismatch: {parent_a.shape}"
    assert parent_b.shape == (n_words * 4,), f"parent_b shape mismatch: {parent_b.shape}"


def test_sample_parents_single_elite_returns_same_twice() -> None:
    """If archive has only 1 elite, both parents should be that elite."""
    archive_data = _make_archive_data(n_elites=1, n_words=10)
    rng = np.random.default_rng(99)

    parent_a, parent_b = sample_parents(archive_data, rng)

    # Both must equal the single elite in the archive
    np.testing.assert_array_equal(
        parent_a,
        archive_data["solution"][0],
        err_msg="parent_a should be the only elite",
    )
    np.testing.assert_array_equal(
        parent_b,
        archive_data["solution"][0],
        err_msg="parent_b should be the only elite",
    )
