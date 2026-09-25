"""Sprint P24 Scenario 9 — Smoke suite over multiple real-world PSDs.

Parametrised over fixtures dropped into ``tests/fixtures/`` (gitignored). Each
PSD is rendered via ``MockupEngine`` WITHOUT an explicit ``layer_name`` —
auto-detect must pick the right Smart Object and produce a non-blank PNG.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from psd_tools import PSDImage

from aerocloud_worker.mockup import MockupEngine, locate_smart_object

_REPO_ROOT = Path(__file__).resolve().parents[6]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "expected_layer"),
    [
        ("poster-frame-test.psd", "Replace me"),
        ("photo-frame-008.psd", "Your artwork here"),
    ],
)
def test_auto_detect_against_real_psd(
    fixture_name: str,
    expected_layer: str,
    design_png: Path,
) -> None:
    psd_path = _FIXTURE_DIR / fixture_name
    if not psd_path.exists():
        pytest.skip(
            f"Fixture {fixture_name} missing — see tests/fixtures/README.md"
        )

    # 1. Auto-detect picks the expected layer.
    psd = PSDImage.open(psd_path)
    info = locate_smart_object(psd, layer_name=None)
    assert info.layer_name == expected_layer, (
        f"auto-detect picked {info.layer_name!r}, expected {expected_layer!r}"
    )

    # 2. Full render with auto-detect produces a non-blank composite.
    engine = MockupEngine(cache={})
    result = engine.render(psd_path, design_png)

    assert result.size == (psd.width, psd.height)
    assert result.mode == "RGBA"

    arr = np.array(result)
    x1, y1, x2, y2 = info.bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    patch = arr[max(0, cy - 50) : cy + 50, max(0, cx - 50) : cx + 50, :3]
    assert patch.size > 0, "patch sampled outside canvas"
    assert patch.std() > 20, (
        f"{fixture_name}: auto-detect render at smart-object centre is blank "
        f"(std={patch.std():.2f})"
    )


def test_auto_detect_picks_replace_me_smoke(
    poster_frame_psd: Path,
) -> None:
    """Lightweight smoke (always runs when poster_frame_psd is present)."""
    psd = PSDImage.open(poster_frame_psd)
    info = locate_smart_object(psd)  # default layer_name=None
    assert info.layer_name == "Replace me"
