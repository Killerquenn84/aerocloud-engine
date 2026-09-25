"""Regression test conftest — no FreeType shim required.

The FreeType version shim that previously patched ``PIL.features.version``
to return ``"2.13.2"`` has been removed in Wave 5 3-KI review (2026-04-09).
The pin in ``aerocloud.geometry.__init__`` now correctly targets ``"2.14.3"``,
which matches the FreeType version on this server (Hostinger VPS, 2.14.3)
and the version used to generate all golden corpus fixtures (``.npy`` files).

D-51 compliance is unchanged: this file never patched Pillow's decode/raster
path, only the version-introspection API. With the pin aligned to server
reality the shim is obsolete.
"""

from __future__ import annotations

import pytest  # noqa: F401  # kept for any future conftest hooks
