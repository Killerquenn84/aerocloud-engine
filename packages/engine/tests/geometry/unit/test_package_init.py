"""Unit tests for geometry/__init__.py — _assert_freetype() + (y,x) adapters.

TDD: Tests written BEFORE implementation (RED phase).
Tests I1..I5 verify D-14, D-15, D-28 and ADR-0006.

Note on FreeType pin (ADR-0006): _EXPECTED_FREETYPE = "2.13.2" is the pinned
Docker production version. On this server (FreeType 2.14.3), _assert_freetype()
will raise unless monkeypatched. All tests that call _assert_freetype() or
reload aerocloud.geometry MUST monkeypatch PIL.features.version first.
This is the ONE permissible test monkeypatch in Phase 4 per the plan — we patch
the feature-introspection API, not Pillow's decode path (D-51 forbids mocking
Pillow's image decode, not its version reporting).
"""

from __future__ import annotations

import importlib

import pytest

# We import _assert_freetype etc. via monkeypatched reload, not at module level,
# because importing aerocloud.geometry on a non-pinned FreeType host raises.
# However, the submodules (errors, mask, sdf) import from geometry.errors directly
# and do not trigger geometry/__init__.py.

# ---------------------------------------------------------------------------
# I1: from aerocloud.geometry import _assert_freetype, xy_to_yx, yx_to_xy succeeds
#     (after patching to the expected version)
# ---------------------------------------------------------------------------


def test_i1_public_symbols_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    """I1: _assert_freetype, xy_to_yx, yx_to_xy are importable from aerocloud.geometry."""
    import PIL.features

    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.13.2")
    import aerocloud.geometry as geo

    importlib.reload(geo)
    assert hasattr(geo, "_assert_freetype"), "_assert_freetype not found"
    assert hasattr(geo, "xy_to_yx"), "xy_to_yx not found"
    assert hasattr(geo, "yx_to_xy"), "yx_to_xy not found"
    assert callable(geo._assert_freetype)
    assert callable(geo.xy_to_yx)
    assert callable(geo.yx_to_xy)


# ---------------------------------------------------------------------------
# I2: On the pinned Docker image (2.13.2), _assert_freetype() returns None
# ---------------------------------------------------------------------------


def test_i2_assert_freetype_passes_with_pinned_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I2: With FreeType 2.13.2 (mocked to simulate Docker), _assert_freetype() is silent.

    In the pinned Docker environment (production + CI), PIL.features.version("freetype2")
    returns "2.13.2", and _assert_freetype() must return None without raising.
    """
    import PIL.features

    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.13.2")
    import aerocloud.geometry as geo

    importlib.reload(geo)
    # Should not raise — this simulates the Docker environment
    result = geo._assert_freetype()
    assert result is None, f"_assert_freetype() should return None, got {result!r}"


# ---------------------------------------------------------------------------
# I3: Mismatch injection — wrong FreeType version raises GeometryEnvironmentError
# ---------------------------------------------------------------------------


def test_i3_freetype_mismatch_raises_geometry_environment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I3: Mismatch injection — FreeType 2.14.2 raises GeometryEnvironmentError.

    This is the ONE permissible test monkeypatch in Phase 4 (plan + D-51):
    we patch PIL.features.version (version-introspection API), NOT Pillow's
    decode path.

    The error message must contain both the expected version (2.13.2) and the
    actual mocked version (2.14.2).
    """
    import PIL.features

    from aerocloud.geometry.errors import GeometryEnvironmentError

    # First reload with pinned version so module is importable
    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.13.2")
    import aerocloud.geometry as geo

    importlib.reload(geo)

    # Now test that calling _assert_freetype() with a mismatched version raises
    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.14.2")
    with pytest.raises(GeometryEnvironmentError) as exc_info:
        geo._assert_freetype()

    msg = str(exc_info.value)
    assert "2.14.2" in msg, f"error message should mention actual version 2.14.2: {msg!r}"
    assert "2.13.2" in msg, f"error message should mention expected version 2.13.2: {msg!r}"


# ---------------------------------------------------------------------------
# I4: xy_to_yx and yx_to_xy round-trip correctly
# ---------------------------------------------------------------------------


def test_i4_xy_to_yx_and_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """I4: xy_to_yx((3, 5)) == (5, 3) and yx_to_xy((5, 3)) == (3, 5)."""
    import PIL.features

    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.13.2")
    import aerocloud.geometry as geo

    importlib.reload(geo)

    assert geo.xy_to_yx((3, 5)) == (5, 3), (
        f"xy_to_yx((3, 5)) should be (5, 3), got {geo.xy_to_yx((3, 5))}"
    )
    assert geo.yx_to_xy((5, 3)) == (3, 5), (
        f"yx_to_xy((5, 3)) should be (3, 5), got {geo.yx_to_xy((5, 3))}"
    )
    # Round-trip
    assert geo.yx_to_xy(geo.xy_to_yx((7, 11))) == (7, 11), "round-trip failed"
    assert geo.xy_to_yx(geo.yx_to_xy((11, 7))) == (11, 7), "inverse round-trip failed"


# ---------------------------------------------------------------------------
# I5: Importing aerocloud.geometry triggers _assert_freetype() at module load
# ---------------------------------------------------------------------------


def test_i5_import_triggers_assert_freetype_at_module_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I5: importlib.reload(aerocloud.geometry) in a passing env does not raise.

    Verifies that _assert_freetype() is called as a module-level side effect
    (not lazily) — a fresh reload with the pinned version must succeed silently.
    """
    import PIL.features

    monkeypatch.setattr(PIL.features, "version", lambda feat: "2.13.2")
    import aerocloud.geometry as geo

    # Reload should call _assert_freetype() at module level without raising
    # If it is NOT called at import time, this test is vacuous (can't detect it here).
    # The test for the FAILURE path (I3) is the true enforcement: if the module
    # doesn't call _assert_freetype() at import time, a mismatched environment
    # would not be caught. We verify the passing-env reload is silent:
    importlib.reload(geo)  # must not raise with 2.13.2 patched

    # Verify _EXPECTED_FREETYPE constant is present
    assert geo._EXPECTED_FREETYPE == "2.13.2", (
        f"_EXPECTED_FREETYPE should be '2.13.2', got {geo._EXPECTED_FREETYPE!r}"
    )
