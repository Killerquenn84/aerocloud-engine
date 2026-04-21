"""Unit tests for compute_kl_divergence and check_distribution_shift (Plan 10-03, Task 1).

TDD RED phase: these tests must FAIL before monitoring.py is implemented.

Design verification:
    - CRITICAL: Uses 4 marginal 1D histograms (NOT joint 4D histogramdd).
    - eps=1e-8 smoothing prevents log(0) errors.
    - scipy.special.rel_entr used for KL computation.
    - check_distribution_shift returns True when KL > threshold (alert condition).
"""

from __future__ import annotations

import numpy as np

from aerocloud.self_play.monitoring import check_distribution_shift, compute_kl_divergence


class TestKLDivergenceIdenticalDistributions:
    """Test 1: identical arrays should produce KL ~= 0."""

    def test_kl_identical_distributions_near_zero(self) -> None:
        """Same array passed twice -> KL divergence should be near 0."""
        rng = np.random.default_rng(42)
        descriptors = rng.uniform(0.0, 1.0, size=(1000, 4))

        kl = compute_kl_divergence(descriptors, descriptors, n_bins=10)

        assert kl < 0.01, f"Expected KL ~= 0.0 for identical inputs, got {kl}"


class TestKLNoDriftUniform:
    """Test 2: two independent samples from same uniform -> KL < 0.1."""

    def test_kl_no_drift_uniform_below_threshold(self) -> None:
        """Two independent large uniform samples -> KL should be small (< 0.1)."""
        rng = np.random.default_rng(123)
        prev = rng.uniform(0.0, 1.0, size=(5000, 4))
        curr = rng.uniform(0.0, 1.0, size=(5000, 4))

        kl = compute_kl_divergence(prev, curr, n_bins=10)

        assert kl < 0.1, (
            f"Two independent uniform samples should have low KL, got {kl}. "
            "Note: joint 4D histogram would give ~11.5."
        )


class TestKLSevereCollapse:
    """Test 3: uniform vs corner-concentrated -> KL >> 0.5."""

    def test_kl_severe_collapse_above_threshold(self) -> None:
        """Uniform prev vs all-corner curr -> KL should be well above threshold."""
        rng = np.random.default_rng(0)
        prev = rng.uniform(0.0, 1.0, size=(5000, 4))

        # Corner-concentrated: all values near (0.0, 0.0, 0.0, 0.0)
        curr = rng.uniform(0.0, 0.3, size=(5000, 4))

        kl = compute_kl_divergence(prev, curr, n_bins=10)

        assert kl > 0.5, f"Severe drift should produce KL > 0.5, got {kl}"


class TestKLOutputType:
    """Test 4: return type must be a Python float."""

    def test_kl_output_shape_is_float(self) -> None:
        """compute_kl_divergence must return a Python float (not np.float64 or ndarray)."""
        rng = np.random.default_rng(99)
        arr = rng.uniform(0.0, 1.0, size=(100, 4))

        kl = compute_kl_divergence(arr, arr)

        assert isinstance(kl, float), f"Expected Python float, got {type(kl)}"


class TestKLSingleDimCollapse:
    """Test 5: one dimension all 0.0 in curr -> KL > 0.5."""

    def test_kl_single_dim_collapse(self) -> None:
        """If curr dimension 0 is all zero (collapsed), KL should exceed threshold."""
        rng = np.random.default_rng(7)
        prev = rng.uniform(0.0, 1.0, size=(5000, 4))

        # Collapse dimension 0: all values at exactly 0.0
        curr = rng.uniform(0.0, 1.0, size=(5000, 4))
        curr[:, 0] = 0.0  # dimension 0 is degenerate

        kl = compute_kl_divergence(prev, curr, n_bins=10)

        assert kl > 0.5, (
            f"Single-dimension collapse (dim 0 all zeros) should give KL > 0.5, got {kl}"
        )


class TestCheckDistributionShiftTrue:
    """Test 6: KL=0.6 > 0.5 -> True (alert)."""

    def test_check_distribution_shift_true(self) -> None:
        """check_distribution_shift returns True when KL exceeds threshold."""
        result = check_distribution_shift(kl_value=0.6, threshold=0.5)

        assert result is True, "KL=0.6 > 0.5 should trigger alert (True)"


class TestCheckDistributionShiftFalse:
    """Test 7: KL=0.3 < 0.5 -> False (no alert)."""

    def test_check_distribution_shift_false(self) -> None:
        """check_distribution_shift returns False when KL is below threshold."""
        result = check_distribution_shift(kl_value=0.3, threshold=0.5)

        assert result is False, "KL=0.3 < 0.5 should not trigger alert (False)"


class TestKLUsesMarginalNotJoint:
    """Test 8: verify marginal (not joint) histogram usage.

    The critical research correction: use 4 independent 1D histograms.
    Joint 4D histogram (histogramdd) on uniform samples gives KL ~= 11.5.
    Marginal 1D histograms on the same uniform samples give KL ~= 0.0.
    """

    def test_kl_uses_marginal_not_joint(self) -> None:
        """Marginal KL on uniform samples must be < 0.1 (joint would give ~11.5)."""
        rng = np.random.default_rng(2024)
        # Large uniform samples — marginal KL ~ 0.0, joint KL >> 10
        prev = rng.uniform(0.0, 1.0, size=(5000, 4))
        curr = rng.uniform(0.0, 1.0, size=(5000, 4))

        kl = compute_kl_divergence(prev, curr, n_bins=10)

        assert kl < 0.1, (
            f"Expected marginal KL < 0.1 for same uniform, got {kl}. "
            "If ~11.5, the implementation is using joint 4D histogram (BUG)."
        )

    def test_kl_function_accepts_n_bins_parameter(self) -> None:
        """compute_kl_divergence must accept n_bins as a parameter (not bins tuple)."""
        rng = np.random.default_rng(42)
        arr = rng.uniform(0.0, 1.0, size=(100, 4))

        # Must not raise — n_bins is a scalar int, not a tuple
        kl = compute_kl_divergence(arr, arr, n_bins=20)
        assert isinstance(kl, float)
