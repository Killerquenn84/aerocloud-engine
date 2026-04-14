"""Unit tests for FONT_REGISTRY — the (font_family, size_pt) registration set.

BDD Scenarios (D-12, REND-04):
  Given a fresh registry
  When I register a (font_family, size_pt) pair
  Then the registry contains exactly one entry

  Given a registry with one entry
  When I register the same pair again
  Then the registry still contains exactly one entry (no growth)

  Given a registry with N entries
  When I register any of those same pairs again
  Then the count does not change (idempotent under concurrent access)
"""

from __future__ import annotations

import threading

import pytest

from aerocloud.renderer._sprites import get_font_registry, register_glyph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buffer_4x4() -> "import numpy as np; np.ndarray":
    import numpy as np
    return np.arange(16, dtype=np.uint8).reshape(4, 4)


def _register(font_family: str, size_pt: int) -> None:
    """Register a font pair using a dummy glyph buffer (codepoint 65 = 'A')."""
    import numpy as np
    import torch

    buf = np.zeros((4, 4), dtype=np.uint8)
    register_glyph(font_family, size_pt, 65, buf, torch.device("cpu"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_single_font() -> None:
    """Registering one (font_family, size_pt) pair → registry has 1 entry."""
    _register("Inter", 24)
    reg = get_font_registry()
    assert len(reg) == 1
    assert ("Inter", 24) in reg


def test_register_duplicate_font() -> None:
    """Registering the same pair twice → registry still has 1 entry."""
    _register("Inter", 24)
    _register("Inter", 24)
    assert len(get_font_registry()) == 1


def test_register_multiple_fonts() -> None:
    """Registering two distinct pairs → registry has 2 entries."""
    _register("Inter", 24)
    _register("Inter", 48)
    reg = get_font_registry()
    assert len(reg) == 2
    assert ("Inter", 24) in reg
    assert ("Inter", 48) in reg


def test_font_registry_count_stable_after_100_calls() -> None:
    """Registering the same pair 100 times → count stays at 1."""
    for _ in range(100):
        _register("Roboto", 32)
    assert len(get_font_registry()) == 1


def test_font_registry_thread_safety() -> None:
    """16 threads each registering the same pair → count is exactly 1 (no corruption)."""
    barrier = threading.Barrier(16)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            barrier.wait()
            _register("ThreadFont", 12)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"
    reg = get_font_registry()
    assert len(reg) == 1
    assert ("ThreadFont", 12) in reg
