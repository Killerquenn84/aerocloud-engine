"""Mutation operators for the Self-Play training loop (Plan 10-02, Task 1).

Implements:
    - structure_aware_mutate: Gaussian perturbation on flat solution array,
      applying per-column sigma values derived from SelfPlayConfig (D-06).
    - uniform_crossover: Per-element coin-flip merge of two parent solutions (D-05).
    - sample_parents: Uniform random selection from archive elites (D-05).

Design decisions:
    D-04: Gaussian perturbation adds zero-mean noise with configurable sigma.
    D-05: Uniform crossover uses per-element Bernoulli mask; parent sampling
          draws two indices uniformly from archive["solution"].
    D-06: Structure-aware mutation reshapes flat array to (N,4) to apply
          separate sigma per column: [sigma_xy, sigma_xy, sigma_scale, sigma_theta].

Security:
    T-10-05: No bounds clamping here; archive tell() does clamping at insertion.
    T-10-06: solution_dim bounded by max_words * 4 = 800 max (O(N) operation).
"""

from __future__ import annotations

import numpy as np

from aerocloud.self_play.config import SelfPlayConfig

# Column indices in the (N, 4) reshaped layout
_COL_X: int = 0  # x position  → sigma_xy
_COL_Y: int = 1  # y position  → sigma_xy
_COL_SCALE: int = 2  # word scale  → sigma_scale
_COL_THETA: int = 3  # rotation    → sigma_theta


def structure_aware_mutate(
    solution: np.ndarray,
    config: SelfPlayConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply structure-aware Gaussian perturbation to a flat solution vector.

    Reshapes the flat solution to (N, 4), applies different sigma values per
    column (position x/y, scale, theta), then flattens back to 1D.

    Per-column sigma values:
        col 0 (x):     sigma_xy
        col 1 (y):     sigma_xy
        col 2 (scale): sigma_scale
        col 3 (theta): sigma_theta

    Args:
        solution: Flat ndarray of shape (max_words * 4,) representing word
                  layout parameters [x, y, scale, theta] per word.
        config:   SelfPlayConfig carrying sigma_xy, sigma_scale, sigma_theta.
        rng:      Seeded numpy random Generator for reproducibility.

    Returns:
        Mutated solution with the same shape as input.
    """
    n_total = solution.shape[0]
    if n_total % 4 != 0:
        raise ValueError(
            f"solution length must be divisible by 4 (got {n_total}). "
            "Expected shape: (max_words * 4,)"
        )
    n_words = n_total // 4

    # Reshape to (N, 4) for per-column noise application (D-06)
    params = solution.reshape(n_words, 4)

    # Build per-column sigma array: [sigma_xy, sigma_xy, sigma_scale, sigma_theta]
    sigma_per_col = np.array(
        [config.sigma_xy, config.sigma_xy, config.sigma_scale, config.sigma_theta],
        dtype=np.float64,
    )

    # Sample noise: shape (n_words, 4), each column scaled by its sigma
    noise = rng.standard_normal((n_words, 4)) * sigma_per_col

    mutated = params + noise

    return mutated.reshape(n_total)


def uniform_crossover(
    parent_a: np.ndarray,
    parent_b: np.ndarray,
    rng: np.random.Generator,
    p: float = 0.5,
) -> np.ndarray:
    """Produce a child via per-element uniform crossover of two parents.

    For each element i, the child takes parent_a[i] if rng.random() < p,
    otherwise parent_b[i].

    Special cases:
        p=0.0  → returns parent_b entirely (mask always False)
        p=1.0  → returns parent_a entirely (mask always True)

    Args:
        parent_a: First parent solution (1D ndarray).
        parent_b: Second parent solution (1D ndarray, same shape as parent_a).
        rng:      Seeded numpy random Generator for reproducibility.
        p:        Probability of selecting each gene from parent_a (default 0.5).

    Returns:
        Child solution of the same shape as the parents.
    """
    mask = rng.random(parent_a.shape) < p
    return np.where(mask, parent_a, parent_b)


def sample_parents(
    archive_data: dict,  # type: ignore[type-arg]
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample two parent solutions uniformly at random from archive elites.

    Uses rng.integers(0, n_elites, size=2) for two independent uniform draws.
    If n_elites < 2, both parents are the same (single) elite.

    Args:
        archive_data: Dict as returned by ArchiveWrapper.data(), must contain
                      key "solution" with shape (n_elites, solution_dim).
        rng:          Seeded numpy random Generator for reproducibility.

    Returns:
        Tuple of (parent_a, parent_b), each a 1D ndarray of shape (solution_dim,).
    """
    solutions: np.ndarray = archive_data["solution"]
    n_elites = solutions.shape[0]

    if n_elites < 2:
        # Edge case: return the single elite twice
        idx_a = 0
        idx_b = 0
    else:
        indices = rng.integers(0, n_elites, size=2)
        idx_a = int(indices[0])
        idx_b = int(indices[1])

    return solutions[idx_a], solutions[idx_b]
