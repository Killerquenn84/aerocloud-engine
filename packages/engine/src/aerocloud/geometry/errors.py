"""Typed error hierarchy for the geometry package.

All errors derive from `GeometryError`. Downstream Phase 5 (Renderer) and
Phase 6 (Inner Loop) pattern-match on `GeometryError` subclasses rather than
parsing log messages.

Design decisions:
- D-08: EmptyMaskError raised fail-fast BEFORE scipy EDT allocation
- D-28: GeometryEnvironmentError covers FreeType version mismatch (ADR-0006)
- D-43: PlacementFailedError raised ONLY for contract violations; ordinary
  unplaceable words go into PlacementResult.dropped_words with a DropReason

See ADR-0004 (sign convention), ADR-0005 (coordinate system), ADR-0006 (FreeType).
"""

from __future__ import annotations


class GeometryError(Exception):
    """Base class for all aerocloud.geometry exceptions."""


class MaskFormatError(GeometryError):
    """Raised when a mask input does not conform to the v1 PNG contract (D-04)."""


class EmptyMaskError(GeometryError):
    """Raised when a decoded mask has zero True OR zero False pixels (D-08).

    This is a fail-fast guard BEFORE scipy EDT allocation.
    """


class GeometryEnvironmentError(GeometryError):
    """Raised when the runtime environment violates a locked assumption (D-28).

    Currently covers: FreeType version mismatch (Homebrew Pillow drift).
    See ADR-0006.
    """


class PlacementFailedError(GeometryError):
    """Raised ONLY on placement contract violations (D-43).

    Examples: NaN/non-finite SDF, dimension mismatch between mask and glyph
    buffer, negative budgets, internal invariant failure. An *ordinary*
    unplaceable word is NEVER an exception — it goes into
    `PlacementResult.dropped_words` with a `DropReason`.
    """
