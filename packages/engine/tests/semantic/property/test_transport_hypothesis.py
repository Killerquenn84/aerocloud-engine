"""Property-based tests for compute_transport (Phase 8, SEM-05, SEM-06).

Hypothesis property: for any (N, N) cost matrix (N in [2, 20]),
the transport_matrix is doubly stochastic with rows and columns
each summing to approximately 1/N (atol=1e-3).

This invariant must hold regardless of:
- Matrix size N
- Random seed / cost distribution
- Internal epsilon adaptation choices
"""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from aerocloud.semantic.transport import compute_transport


@given(
    n=st.integers(min_value=2, max_value=20),
    seed=st.integers(min_value=0, max_value=999),
)
@h_settings(max_examples=50, deadline=30_000)
def test_transport_is_doubly_stochastic(n: int, seed: int) -> None:
    """Test 10 (hypothesis): For any random (N, N) cost matrix (N in [2, 20]),
    transport_matrix is doubly stochastic with atol=1e-3.

    Invariant:
    - Row sums == 1/N (marginal constraint: each word mapped to full mass)
    - Column sums == 1/N (marginal constraint: each position receives full mass)
    - All values >= 0 (no negative mass transfer)
    """
    rng = np.random.default_rng(seed)
    cost = rng.uniform(0.0, 1.0, size=(n, n)).astype(np.float64)

    plan = compute_transport(cost, eps_init=0.1, max_iter=1000)
    T = plan.transport_matrix

    expected = np.ones(n) / n

    row_sums = T.sum(axis=1)
    col_sums = T.sum(axis=0)

    np.testing.assert_allclose(
        row_sums,
        expected,
        atol=1e-3,
        err_msg=f"Row sums not 1/N for N={n}, seed={seed}",
    )
    np.testing.assert_allclose(
        col_sums,
        expected,
        atol=1e-3,
        err_msg=f"Column sums not 1/N for N={n}, seed={seed}",
    )
    assert np.all(T >= -1e-10), (
        f"Transport matrix has negative values for N={n}, seed={seed}"
    )
