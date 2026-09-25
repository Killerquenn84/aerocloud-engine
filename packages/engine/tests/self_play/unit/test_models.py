"""Unit tests for SelfPlayRunResult and SelfPlayEvent (TDD RED phase).

Given: SelfPlayRunResult and SelfPlayEvent Pydantic models
When: Constructing with valid arguments
Then: Fields are accessible, frozen, and validated correctly
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aerocloud.self_play.models import SelfPlayEvent, SelfPlayRunResult


class TestSelfPlayRunResult:
    """Tests for SelfPlayRunResult model."""

    def _valid_kwargs(self) -> dict:
        return {
            "run_id": "550e8400-e29b-41d4-a716-446655440000",
            "started_at": "2026-04-16T02:00:00Z",
            "ended_at": "2026-04-16T10:00:00Z",
            "n_iterations": 1000,
            "n_accepted": 450,
            "n_rejected": 550,
            "kl_divergence": 0.234,
            "exit_reason": "completed",
        }

    def test_construction_success(self) -> None:
        result = SelfPlayRunResult(**self._valid_kwargs())
        assert result.run_id == "550e8400-e29b-41d4-a716-446655440000"
        assert result.n_iterations == 1000
        assert result.n_accepted == 450
        assert result.exit_reason == "completed"

    def test_kl_divergence_none_allowed(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["kl_divergence"] = None
        result = SelfPlayRunResult(**kwargs)
        assert result.kl_divergence is None

    def test_frozen_immutable(self) -> None:
        result = SelfPlayRunResult(**self._valid_kwargs())
        with pytest.raises((TypeError, ValidationError)):
            result.n_iterations = 999  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["extra_field"] = "nope"
        with pytest.raises(ValidationError):
            SelfPlayRunResult(**kwargs)

    def test_all_fields_accessible(self) -> None:
        result = SelfPlayRunResult(**self._valid_kwargs())
        assert result.run_id is not None
        assert result.started_at is not None
        assert result.ended_at is not None
        assert result.n_iterations is not None
        assert result.n_accepted is not None
        assert result.n_rejected is not None
        assert result.exit_reason is not None


class TestSelfPlayEvent:
    """Tests for SelfPlayEvent model."""

    def _valid_accepted_kwargs(self) -> dict:
        return {
            "iteration": 42,
            "parent_bin_ids": ["bin-001", "bin-002"],
            "mutation_type": "sigma_xy",
            "fitness_before": 0.78,
            "fitness_after": 0.82,
            "accepted": True,
            "reject_reason": "",
        }

    def _valid_rejected_kwargs(self) -> dict:
        return {
            "iteration": 100,
            "parent_bin_ids": ["bin-003"],
            "mutation_type": "crossover",
            "fitness_before": 0.80,
            "fitness_after": 0.75,
            "accepted": False,
            "reject_reason": "fitness_below_threshold",
        }

    def test_accepted_event_construction(self) -> None:
        event = SelfPlayEvent(**self._valid_accepted_kwargs())
        assert event.iteration == 42
        assert event.accepted is True
        assert event.reject_reason == ""

    def test_rejected_event_construction(self) -> None:
        event = SelfPlayEvent(**self._valid_rejected_kwargs())
        assert event.accepted is False
        assert event.reject_reason == "fitness_below_threshold"

    def test_fitness_before_none_allowed(self) -> None:
        kwargs = self._valid_accepted_kwargs()
        kwargs["fitness_before"] = None
        event = SelfPlayEvent(**kwargs)
        assert event.fitness_before is None

    def test_parent_bin_ids_empty_list_allowed(self) -> None:
        kwargs = self._valid_accepted_kwargs()
        kwargs["parent_bin_ids"] = []
        event = SelfPlayEvent(**kwargs)
        assert event.parent_bin_ids == []

    def test_frozen_immutable(self) -> None:
        event = SelfPlayEvent(**self._valid_accepted_kwargs())
        with pytest.raises((TypeError, ValidationError)):
            event.iteration = 999  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        kwargs = self._valid_accepted_kwargs()
        kwargs["extra"] = "bad"
        with pytest.raises(ValidationError):
            SelfPlayEvent(**kwargs)

    def test_reject_reason_empty_for_accepted(self) -> None:
        """Accepted events conventionally have empty reject_reason."""
        event = SelfPlayEvent(**self._valid_accepted_kwargs())
        assert event.accepted is True
        assert event.reject_reason == ""
