"""Geometry test suite conftest — shared mask fixtures.

The FreeType version shim that previously patched ``PIL.features.version``
to return ``"2.13.2"`` has been removed in Wave 5 3-KI review (2026-04-09).
The pin in ``aerocloud.geometry.__init__`` now correctly targets ``"2.14.3"``,
which matches the FreeType version on this server (Hostinger VPS) and the
version used to generate all golden corpus fixtures. No shim is required.

Per D-51: only ``PIL.features.version`` was ever patched here — NOT Pillow's
decode path (Image.open, img.load, etc.). With the pin aligned to server
reality the shim is obsolete and has been removed.
"""

from __future__ import annotations

import pytest  # noqa: F401  # kept for any future conftest hooks
