"""Geometry test suite conftest — FreeType version shim.

This conftest patches ``PIL.features.version`` to return the pinned FreeType
version ("2.13.2") for the entire geometry test session. This is necessary
because this server (and any non-Docker dev environment) may have a different
FreeType version, which causes ``aerocloud.geometry.__init__._assert_freetype()``
to raise ``GeometryEnvironmentError`` at package import time (D-28 / ADR-0006).

Design rationale (D-51 compliance):
- D-51 forbids mocking Pillow's **decode path** (Image.open, img.load, etc.).
- This shim only patches ``PIL.features.version`` — the version-introspection
  API — which is NOT part of the decode path.
- The plan (04-02-PLAN.md Task T3) explicitly authorizes this as "the ONE
  permissible test monkeypatch in Phase 4".
- mask.py and sdf.py tests use real Pillow + real scipy + real numpy (D-51).

The shim is a module-level ``unittest.mock.patch`` applied at conftest import
time (before pytest collects test modules). It stays active for the entire
geometry test session via a ``pytest_configure`` hook.
"""

from __future__ import annotations

import unittest.mock

import pytest

# Patch PIL.features.version at conftest import time so that any subsequent
# import of aerocloud.geometry (including transitive imports triggered by
# importing aerocloud.geometry.mask or aerocloud.geometry.sdf) sees "2.13.2"
# and does not raise GeometryEnvironmentError.
_FREETYPE_PATCHER = unittest.mock.patch("PIL.features.version", return_value="2.13.2")
_FREETYPE_PATCHER.start()


def pytest_configure(config: pytest.Config) -> None:
    """Ensure the FreeType shim stays active for the whole geometry test run."""
    # The patcher was already started at module import time above.
    # This hook exists so we can register the finalizer cleanly.
    config.add_cleanup(_FREETYPE_PATCHER.stop)
