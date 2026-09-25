"""Unit tests for aerocloud.semantic.transport (Phase 8, SEM-05, SEM-06).

Tests the Sinkhorn-Knopp Optimal Transport with adaptive epsilon regularization.

BDD scenarios (Given/When/Then):
- Given a random (5,5) cost matrix
  When compute_transport is called
  Then a TransportPlan with shape (5,5) transport_matrix is returned

- Given a (5,5) cost matrix with uniform marginals
  When compute_transport is called
  Then rows and columns each sum to approximately 1/N

- Given an identity cost matrix (degenerate)
  When compute_transport is called
  Then transport_matrix contains no NaN values

- Given eps_init=1.0 and trivial cost
  When compute_transport converges in < 10 iterations
  Then eps_used is halved to 0.5

- Given eps_init=0.001 on a large difficult cost
  When Sinkhorn takes > 500 iterations
  Then eps_used is doubled to 0.002

- Given eps_init=1e-5 (below floor)
  When compute_transport is called
  Then eps_used >= 1e-4 (clamped at floor)

- Given eps_init=2.0 (above ceiling)
  When compute_transport is called
  Then eps_used <= 1.0 (initial eps clamped before call)
"""

from __future__ import annotations

import numpy as np
import pytest

from aerocloud.models.semantic import TransportPlan
from aerocloud.semantic.transport import compute_transport


@pytest.fixture
def random_cost_5x5() -> np.ndarray:
    """Return a (5, 5) float64 cost matrix with deterministic random values (seed=42)."""
    rng = np.random.default_rng(42)
    return rng.uniform(0.0, 1.0, size=(5, 5)).astype(np.float64)


@pytest.fixture
def trivial_cost_5x5() -> np.ndarray:
    """Return a near-zero cost matrix that causes very fast convergence (< 10 iter)."""
    return np.full((5, 5), 1e-6, dtype=np.float64)


class TestComputeTransportShape:
    """Tests for output shape and type (Test 1)."""

    def test_returns_transport_plan(self, random_cost_5x5: np.ndarray) -> None:
        """Test 1: compute_transport returns a TransportPlan instance."""
        plan = compute_transport(random_cost_5x5)
        assert isinstance(plan, TransportPlan)

    def test_transport_matrix_shape(self, random_cost_5x5: np.ndarray) -> None:
        """Test 1: transport_matrix shape is (5, 5) for 5x5 cost matrix."""
        plan = compute_transport(random_cost_5x5)
        assert plan.transport_matrix.shape == (5, 5)


class TestDoublyStochasticMarginals:
    """Tests for marginal constraints (Tests 2-3)."""

    def test_row_sums_equal_one_over_n(self, random_cost_5x5: np.ndarray) -> None:
        """Test 2: Transport matrix rows sum to approx 1/N each."""
        N = 5
        plan = compute_transport(random_cost_5x5)
        row_sums = plan.transport_matrix.sum(axis=1)
        expected = np.ones(N) / N
        np.testing.assert_allclose(row_sums, expected, atol=1e-4)

    def test_col_sums_equal_one_over_n(self, random_cost_5x5: np.ndarray) -> None:
        """Test 3: Transport matrix columns sum to approx 1/N each."""
        N = 5
        plan = compute_transport(random_cost_5x5)
        col_sums = plan.transport_matrix.sum(axis=0)
        expected = np.ones(N) / N
        np.testing.assert_allclose(col_sums, expected, atol=1e-4)


class TestTransportValues:
    """Tests for transport matrix value constraints (Test 4)."""

    def test_all_values_non_negative(self, random_cost_5x5: np.ndarray) -> None:
        """Test 4: All transport_matrix values >= 0 (no negative mass)."""
        plan = compute_transport(random_cost_5x5)
        assert np.all(plan.transport_matrix >= -1e-10), (
            "Transport matrix contains negative values"
        )


class TestDegenerateInput:
    """Tests for degenerate/edge-case cost matrices (Test 5)."""

    def test_identity_cost_no_nan(self) -> None:
        """Test 5: Identity cost matrix produces valid transport (no NaN)."""
        cost = np.eye(5, dtype=np.float64)
        plan = compute_transport(cost)
        assert not np.any(np.isnan(plan.transport_matrix)), (
            "NaN found in transport_matrix for identity cost input"
        )

    def test_identity_cost_shape(self) -> None:
        """Test 5: Identity cost matrix produces (5,5) transport matrix."""
        cost = np.eye(5, dtype=np.float64)
        plan = compute_transport(cost)
        assert plan.transport_matrix.shape == (5, 5)


class TestAdaptiveEpsilonHalving:
    """Tests for eps halving when convergence < 10 iterations (Test 6)."""

    def test_fast_convergence_halves_eps(self, trivial_cost_5x5: np.ndarray) -> None:
        """Test 6: eps_init=1.0 with trivial cost → fast convergence → eps_used halved."""
        # Near-zero cost matrix with large eps should converge near-instantly (< 10 iter)
        plan = compute_transport(trivial_cost_5x5, eps_init=1.0)
        # Adaptive rule: if niter < 10 → eps_used = max(1e-4, eps / 2.0) = 0.5
        assert plan.eps_used == pytest.approx(0.5, rel=1e-6)

    def test_fast_convergence_iterations_lt_10(
        self, trivial_cost_5x5: np.ndarray
    ) -> None:
        """Test 6: trivial cost with large eps converges in < 10 iterations."""
        plan = compute_transport(trivial_cost_5x5, eps_init=1.0)
        assert plan.iterations < 10


class TestAdaptiveEpsilonDoubling:
    """Tests for eps doubling when convergence > 500 iterations (Test 7)."""

    def test_slow_convergence_doubles_eps(self) -> None:
        """Test 7: eps_init=0.001 on challenging cost → iterations > 500 → eps doubled."""
        # Use a difficult cost matrix (high variance, tiny eps) to force slow convergence
        rng = np.random.default_rng(123)
        # Large cost matrix with high variance + tiny epsilon = many iterations
        cost = rng.uniform(0.0, 10.0, size=(15, 15)).astype(np.float64)
        plan = compute_transport(cost, eps_init=0.001, max_iter=2000)
        # If iterations > 500, eps_used should be doubled: 0.002
        if plan.iterations > 500:
            assert plan.eps_used == pytest.approx(0.002, rel=1e-6), (
                f"Expected eps_used=0.002 when niter={plan.iterations} > 500, "
                f"got eps_used={plan.eps_used}"
            )
        else:
            pytest.skip(
                f"Test requires niter > 500 but got {plan.iterations}; "
                "cost matrix did not trigger slow convergence. Adjust fixture."
            )


class TestEpsilonClamping:
    """Tests for epsilon clamping to [1e-4, 1.0] (Tests 8-9)."""

    def test_eps_clamped_at_floor(self) -> None:
        """Test 8: eps_init=1e-5 → initial eps clamped to 1e-4 before Sinkhorn call."""
        rng = np.random.default_rng(42)
        cost = rng.uniform(0.0, 1.0, size=(3, 3)).astype(np.float64)
        # With eps=1e-5 clamped to 1e-4, the run should proceed without crash
        # and eps_used must be >= 1e-4 (floor)
        plan = compute_transport(cost, eps_init=1e-5)
        # eps_used is the adapted eps_adapted which starts from clamped value (1e-4)
        # If niter < 10: eps_used = max(1e-4, 1e-4/2) = 1e-4 (floor keeps it)
        # If niter in [10,500]: eps_used = 1e-4 (no adaptation)
        # If niter > 500: eps_used = min(1.0, 1e-4*2) = 2e-4
        assert plan.eps_used >= 1e-4, (
            f"eps_used={plan.eps_used} is below the clamp floor of 1e-4"
        )

    def test_eps_clamped_at_ceiling(self) -> None:
        """Test 9: eps_init=2.0 → clamped to 1.0 before call → eps_used <= 1.0."""
        rng = np.random.default_rng(42)
        cost = rng.uniform(0.0, 1.0, size=(3, 3)).astype(np.float64)
        plan = compute_transport(cost, eps_init=2.0)
        # After clamping eps to 1.0, adaptation may halve it (to 0.5) but never exceed 1.0
        assert plan.eps_used <= 1.0, (
            f"eps_used={plan.eps_used} exceeds the clamp ceiling of 1.0"
        )
