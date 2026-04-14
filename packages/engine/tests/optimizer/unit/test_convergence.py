"""Unit tests for check_convergence (Rolling-window plateau detection).

check_convergence(loss_history, window=10, epsilon=0.001) -> bool

Given: flat loss history (all same value) with >= window entries.
When: check_convergence is called.
Then: returns True (converged).

Given: diverging/oscillating loss history.
When: check_convergence is called.
Then: returns False (not converged).

Given: history shorter than window.
When: check_convergence is called.
Then: returns False (not enough data).
"""

from __future__ import annotations

import pytest

from aerocloud.optimizer.convergence import check_convergence


class TestConvergenceFlat:
    """Flat histories should trigger convergence."""

    def test_flat_history_converges(self) -> None:
        """10 identical values => converged."""
        history = [0.5] * 10
        assert check_convergence(history, window=10, epsilon=0.001) is True

    def test_near_flat_within_epsilon(self) -> None:
        """Very small oscillation within epsilon => converged."""
        # range = 0.0001, max = 0.5, ratio = 0.0002 < 0.001
        history = [0.5 + 0.00005 * (i % 2) for i in range(10)]
        assert check_convergence(history, window=10, epsilon=0.001) is True


class TestConvergenceNotFlat:
    """Diverging or oscillating histories should not trigger convergence."""

    def test_linearly_decreasing_not_converged(self) -> None:
        """Steadily decreasing loss => not converged."""
        history = [10.0 - i * 0.5 for i in range(10)]  # 10, 9.5, 9, ...
        assert check_convergence(history, window=10, epsilon=0.001) is False

    def test_large_oscillation_not_converged(self) -> None:
        """Large oscillation => not converged."""
        history = [1.0 if i % 2 == 0 else 0.5 for i in range(10)]
        # range = 0.5, max ~ 1.0, ratio = 0.5 >> 0.001
        assert check_convergence(history, window=10, epsilon=0.001) is False


class TestConvergenceShortHistory:
    """Short histories (< window) should never trigger convergence."""

    def test_empty_history(self) -> None:
        """Empty history => False."""
        assert check_convergence([], window=10) is False

    def test_one_entry(self) -> None:
        """Single entry => False (< window)."""
        assert check_convergence([0.5], window=10) is False

    def test_exactly_window_minus_one(self) -> None:
        """window - 1 entries => False."""
        history = [0.5] * 9
        assert check_convergence(history, window=10) is False


class TestConvergenceWindowSlice:
    """check_convergence uses only the last `window` entries."""

    def test_uses_last_window_only(self) -> None:
        """Long history with diverging prefix but flat suffix => converged."""
        # First 20 entries are widely scattered, last 10 are flat
        history = list(range(20)) + [5.0] * 10
        assert check_convergence(history, window=10) is True

    def test_long_history_not_converged_at_tail(self) -> None:
        """Long history, flat prefix, diverging suffix => not converged."""
        history = [5.0] * 20 + list(range(10))  # last 10: 0,1,...,9
        assert check_convergence(history, window=10) is False
