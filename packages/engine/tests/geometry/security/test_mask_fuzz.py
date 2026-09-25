"""Nyquist dim 7: mask_from_bytes must only raise typed GeometryError subclasses.

hypothesis fuzz test: sends random bytes of varying sizes to mask_from_bytes()
and asserts that the ONLY exceptions raised are GeometryError subclasses (or
one of its concrete subtypes: MaskFormatError, EmptyMaskError).

A non-GeometryError escape (e.g., raw OSError, ValueError, struct.error from
Pillow) is a contract violation — Phase 5 and Phase 6 rely on catching
GeometryError to handle bad inputs cleanly.

D-51 compliance: real Pillow is used throughout. No mocking.

References:
    - D-08: EmptyMaskError is the expected response to truly empty masks
    - .planning/phases/04-geometry-v1/04-CONTEXT.md
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §10 (Nyquist dim 7)
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aerocloud.geometry.errors import GeometryError
from aerocloud.geometry.mask import mask_from_bytes


@given(st.binary(min_size=0, max_size=4096))
@settings(
    max_examples=200,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_random_bytes_only_raise_geometry_errors(raw: bytes) -> None:
    """mask_from_bytes(random bytes) must raise only GeometryError subclasses or succeed."""
    try:
        mask_from_bytes(raw)
    except GeometryError:
        pass  # typed failure — this is the expected error mode
    except Exception as exc:  # pragma: no cover — a non-GeometryError is the bug
        raise AssertionError(
            f"mask_from_bytes leaked untyped {type(exc).__name__}: {exc!r}"
        ) from exc
