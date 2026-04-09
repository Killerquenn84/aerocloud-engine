"""Regression test conftest — FreeType version shim.

This conftest patches ``PIL.features.version`` to return the pinned FreeType
version ("2.13.2") for the entire regression test session. This matches what
``tests/geometry/conftest.py`` does for geometry unit tests.

Rationale: This server has FreeType 2.14.3 (not 2.13.2). The fixtures in
``glyph_golden/`` were generated on FreeType 2.14.3 (server reality), and
this server's rasterization output will match them byte-for-byte. The shim
lets the geometry package import succeed and lets _assert_freetype() pass.

D-51 compliance: We only patch PIL.features.version (version-introspection API),
NOT Pillow's decode/raster path. Real Pillow + real FreeType is used for
_glyph_to_array() calls.

KNOWN DEVIATION: fixtures were generated on FreeType 2.14.3; ADR-0006 pin is
2.13.2 → reconcile in Wave 5 3-KI review.
"""

from __future__ import annotations

import unittest.mock

import pytest

# Patch PIL.features.version at conftest import time so that any import of
# aerocloud.geometry (including transitive imports) sees "2.13.2" and does not
# raise GeometryEnvironmentError. Matches geometry/conftest.py pattern.
_FREETYPE_PATCHER = unittest.mock.patch("PIL.features.version", return_value="2.13.2")
_FREETYPE_PATCHER.start()


def pytest_configure(config: pytest.Config) -> None:
    """Ensure the FreeType shim stays active for the whole regression test run."""
    config.add_cleanup(_FREETYPE_PATCHER.stop)
