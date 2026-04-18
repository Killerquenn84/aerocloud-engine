"""Tests for outer_loop.errors — OuterLoopError hierarchy.

TDD RED phase.
"""

from __future__ import annotations

from aerocloud.outer_loop.errors import (
    ArchiveSaturationError,
    EliteDriftError,
    OuterLoopError,
    SolutionDimMismatchError,
)


class TestOuterLoopErrors:
    def test_outer_loop_error_is_exception(self) -> None:
        """OuterLoopError must be a subclass of Exception."""
        assert issubclass(OuterLoopError, Exception)

    def test_archive_saturation_error_hierarchy(self) -> None:
        """ArchiveSaturationError is a subclass of OuterLoopError."""
        assert issubclass(ArchiveSaturationError, OuterLoopError)

    def test_elite_drift_error_hierarchy(self) -> None:
        """EliteDriftError is a subclass of OuterLoopError."""
        assert issubclass(EliteDriftError, OuterLoopError)

    def test_solution_dim_mismatch_error_hierarchy(self) -> None:
        """SolutionDimMismatchError is a subclass of OuterLoopError."""
        assert issubclass(SolutionDimMismatchError, OuterLoopError)

    def test_can_raise_and_catch_outer_loop_error(self) -> None:
        """Raising OuterLoopError works and can be caught as Exception."""
        import pytest

        with pytest.raises(Exception):
            raise OuterLoopError("archive full")

    def test_subclass_caught_as_outer_loop_error(self) -> None:
        """ArchiveSaturationError caught by OuterLoopError handler."""
        import pytest

        with pytest.raises(OuterLoopError):
            raise ArchiveSaturationError("saturation detected")
