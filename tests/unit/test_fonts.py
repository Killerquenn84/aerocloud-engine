"""Verifies font registration is idempotent and returns a stable set.

Note: Wave 6 adds the actual font files. Until then, register_fonts()
returns an empty set (tracked in Phase 1 knowledge as expected behavior).
"""
from __future__ import annotations

from aerocloud.fonts import (
    _reset_for_tests,
    register_fonts,
    registered_font_count,
)


def test_register_fonts_returns_set() -> None:
    _reset_for_tests()
    result = register_fonts()
    assert isinstance(result, set)


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
