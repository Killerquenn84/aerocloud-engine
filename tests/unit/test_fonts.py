"""Verifies font registration is idempotent and discovers bundled TTFs.

As of Wave 6 the bundled fonts are:
  - Inter/Inter-Variable.ttf
  - IBM-Plex-Serif/IBMPlexSerif-Regular.ttf
  - IBM-Plex-Serif/IBMPlexSerif-Bold.ttf
  - IBM-Plex-Serif/IBMPlexSerif-Italic.ttf
"""

from __future__ import annotations

from aerocloud.fonts import (
    _reset_for_tests,
    register_fonts,
    registered_font_count,
)

EXPECTED_FONTS = {
    "Inter-Variable",
    "IBMPlexSerif-Regular",
    "IBMPlexSerif-Bold",
    "IBMPlexSerif-Italic",
}


def test_register_fonts_returns_set() -> None:
    _reset_for_tests()
    result = register_fonts()
    assert isinstance(result, set)


def test_register_fonts_discovers_bundled_files() -> None:
    _reset_for_tests()
    result = register_fonts()
    assert EXPECTED_FONTS.issubset(result), f"missing fonts: {EXPECTED_FONTS - result}"


def test_register_fonts_is_idempotent() -> None:
    _reset_for_tests()
    first = register_fonts()
    count_after_first = registered_font_count()

    second = register_fonts()
    count_after_second = registered_font_count()

    assert first == second
    assert count_after_first == count_after_second


def test_registered_font_count_matches_set() -> None:
    _reset_for_tests()
    result = register_fonts()
    assert registered_font_count() == len(result)
    assert registered_font_count() >= len(EXPECTED_FONTS)
