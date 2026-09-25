"""Unit tests for SelfPlayConfig (TDD RED phase).

Given: SelfPlayConfig Pydantic model defining self-play hyperparameters
When: Constructing with valid/invalid arguments
Then: Correct defaults, validation errors, and frozen immutability
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aerocloud.self_play.config import SelfPlayConfig


class TestSelfPlayConfigDefaults:
    """Tests for default field values."""

    def test_default_n_iterations(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.n_iterations == 1000

    def test_default_soft_time_limit(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.soft_time_limit == 28800

    def test_default_dominance_margin(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.dominance_margin == pytest.approx(0.01)

    def test_default_sigma_xy(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.sigma_xy == pytest.approx(0.05)

    def test_default_sigma_scale(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.sigma_scale == pytest.approx(0.02)

    def test_default_sigma_theta(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.sigma_theta == pytest.approx(0.1)

    def test_default_crossover_p(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.crossover_p == pytest.approx(0.5)

    def test_default_kl_threshold(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.kl_threshold == pytest.approx(0.5)

    def test_default_kl_n_bins(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.kl_n_bins == 10

    def test_default_mutation_ratio(self) -> None:
        cfg = SelfPlayConfig()
        assert cfg.mutation_ratio == pytest.approx(0.7)


class TestSelfPlayConfigFrozen:
    """Tests for frozen immutability."""

    def test_frozen_raises_on_assign(self) -> None:
        cfg = SelfPlayConfig()
        with pytest.raises((TypeError, ValidationError)):
            cfg.n_iterations = 999  # type: ignore[misc]

    def test_frozen_raises_on_model_copy_update(self) -> None:
        """Frozen models cannot be updated via attribute assignment.
        model_copy(update=...) is the correct way to get a new instance.
        """
        cfg = SelfPlayConfig()
        # model_copy works (returns NEW instance, original unchanged)
        updated = cfg.model_copy(update={"sigma_xy": 0.99})
        assert updated.sigma_xy == pytest.approx(0.99)
        assert cfg.sigma_xy == pytest.approx(0.05)  # original unchanged


class TestSelfPlayConfigExtraFields:
    """Tests for extra field rejection."""

    def test_extra_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(unknown_field="oops")  # type: ignore[call-arg]

    def test_extra_field_nested_raises(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(n_iterations=1000, foo=42)  # type: ignore[call-arg]


class TestSelfPlayConfigValidation:
    """Tests for field-level validation."""

    def test_sigma_xy_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(sigma_xy=0.0)

    def test_sigma_xy_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(sigma_xy=-0.01)

    def test_sigma_scale_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(sigma_scale=0.0)

    def test_sigma_theta_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(sigma_theta=0.0)

    def test_dominance_margin_zero_allowed(self) -> None:
        # ge=0 means zero is valid
        cfg = SelfPlayConfig(dominance_margin=0.0)
        assert cfg.dominance_margin == pytest.approx(0.0)

    def test_dominance_margin_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(dominance_margin=-0.001)

    def test_kl_threshold_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(kl_threshold=0.0)

    def test_kl_n_bins_minimum_2(self) -> None:
        with pytest.raises(ValidationError):
            SelfPlayConfig(kl_n_bins=1)

    def test_kl_n_bins_2_is_valid(self) -> None:
        cfg = SelfPlayConfig(kl_n_bins=2)
        assert cfg.kl_n_bins == 2


class TestSelfPlayConfigRoundtrip:
    """Tests for custom value construction and roundtrip."""

    def test_custom_values_preserved(self) -> None:
        cfg = SelfPlayConfig(
            n_iterations=500,
            soft_time_limit=14400,
            dominance_margin=0.05,
            sigma_xy=0.1,
            sigma_scale=0.05,
            sigma_theta=0.2,
            crossover_p=0.3,
            kl_threshold=0.8,
            kl_n_bins=20,
            mutation_ratio=0.6,
        )
        assert cfg.n_iterations == 500
        assert cfg.soft_time_limit == 14400
        assert cfg.dominance_margin == pytest.approx(0.05)
        assert cfg.sigma_xy == pytest.approx(0.1)
        assert cfg.sigma_scale == pytest.approx(0.05)
        assert cfg.sigma_theta == pytest.approx(0.2)
        assert cfg.crossover_p == pytest.approx(0.3)
        assert cfg.kl_threshold == pytest.approx(0.8)
        assert cfg.kl_n_bins == 20
        assert cfg.mutation_ratio == pytest.approx(0.6)

    def test_model_dump_roundtrip(self) -> None:
        cfg = SelfPlayConfig()
        dumped = cfg.model_dump()
        restored = SelfPlayConfig(**dumped)
        assert cfg == restored
