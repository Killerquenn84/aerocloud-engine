"""Error hierarchy for the Outer Loop (MAP-Elites) subsystem.

All exceptions inherit from OuterLoopError, which itself inherits from
the built-in Exception so callers can catch with a single handler.
"""

from __future__ import annotations


class OuterLoopError(Exception):
    """Base class for all outer-loop errors."""


class ArchiveSaturationError(OuterLoopError):
    """Raised when the MAP-Elites archive coverage plateaus (< 1% growth
    over the configured window) — signals that the emitter is stuck."""


class EliteDriftError(OuterLoopError):
    """Raised when re-evaluation detects that an elite's fitness has degraded
    by more than the configured drift threshold (default 10%)."""


class SolutionDimMismatchError(OuterLoopError):
    """Raised when a solution array has a dimension that does not match
    config.max_words * 4 (the expected (N, 4) flattened representation)."""
