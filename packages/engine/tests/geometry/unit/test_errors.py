"""Unit tests for aerocloud.geometry.errors — Phase 4 Wave 0.

BDD scenarios (D-08, D-28, D-43):

Given the geometry errors module exists
When I import the error hierarchy
Then all 5 classes are importable and form a correct subclass tree

Given I instantiate EmptyMaskError with a message
When I check its type
Then it is an instance of GeometryError and Exception

Given each subclass
When instantiated with a message
Then it is a subclass of GeometryError

Given settings is loaded
When I check sdf_cache_max_bytes
Then it equals 402653184 (384 MiB) by default

Given geometry/__init__.py Wave 0 stub
When imported
Then it does NOT call _assert_freetype() at import time
"""

from __future__ import annotations


# Test 1: All 5 classes are importable
def test_import_all_five_error_classes() -> None:
    from aerocloud.geometry.errors import (
        EmptyMaskError,
        GeometryEnvironmentError,
        GeometryError,
        MaskFormatError,
        PlacementFailedError,
    )

    assert EmptyMaskError is not None
    assert GeometryEnvironmentError is not None
    assert GeometryError is not None
    assert MaskFormatError is not None
    assert PlacementFailedError is not None


# Test 2: EmptyMaskError is instance of GeometryError and Exception
def test_empty_mask_error_is_geometry_error_and_exception() -> None:
    from aerocloud.geometry.errors import EmptyMaskError, GeometryError

    err = EmptyMaskError("mask has no inside pixels")
    assert isinstance(err, GeometryError)
    assert isinstance(err, Exception)
    assert str(err) == "mask has no inside pixels"


# Test 3: All subclasses are subclasses of GeometryError
def test_all_subclasses_inherit_from_geometry_error() -> None:
    from aerocloud.geometry.errors import (
        EmptyMaskError,
        GeometryEnvironmentError,
        GeometryError,
        MaskFormatError,
        PlacementFailedError,
    )

    assert issubclass(MaskFormatError, GeometryError)
    assert issubclass(EmptyMaskError, GeometryError)
    assert issubclass(GeometryEnvironmentError, GeometryError)
    assert issubclass(PlacementFailedError, GeometryError)


# Test 4: settings.sdf_cache_max_bytes == 402653184 (384 MiB)
def test_sdf_cache_max_bytes_default() -> None:
    from aerocloud.config import settings

    assert isinstance(settings.sdf_cache_max_bytes, int)
    assert settings.sdf_cache_max_bytes == 402_653_184  # 384 MiB


# Test 5: geometry __init__.py Wave 0 does NOT raise at import time (no _assert_freetype call)
def test_geometry_init_does_not_call_assert_freetype() -> None:
    """Wave 0 stub: importing geometry should succeed without FreeType version check."""
    import importlib

    # Should not raise GeometryEnvironmentError (FreeType check not active in Wave 0)
    mod = importlib.import_module("aerocloud.geometry")
    assert mod is not None
    # Verify the error types are re-exported
    assert hasattr(mod, "GeometryError")
    assert hasattr(mod, "EmptyMaskError")
    assert hasattr(mod, "MaskFormatError")
    assert hasattr(mod, "GeometryEnvironmentError")
    assert hasattr(mod, "PlacementFailedError")
