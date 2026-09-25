"""Unit tests for geometry/debug.py (D-47).

Covers:
- debug_enabled() returns False without env var
- debug_enabled() returns True with AEROCLOUD_DEBUG_GEO=1
- dump_geometry_debug returns None when disabled
- dump_geometry_debug creates expected files when enabled (mask.png, placement.json, env.json)
- matplotlib ImportError is handled gracefully (no crash, .MISSING sentinel written)
- Tag sanitization (special chars become underscores)

D-51 compliance: No mocking of PIL image operations. dump_geometry_debug uses
real PIL Image.fromarray() — but matplotlib IS allowed to be monkeypatched
since it is a dev-only dep (R-7 lazy import). Tests run in a tmp_path so the
output directory is isolated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.debug import debug_enabled, dump_geometry_debug

_ENV_VAR = "AEROCLOUD_DEBUG_GEO"


def test_debug_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """debug_enabled() is False when env var is absent."""
    monkeypatch.delenv(_ENV_VAR, raising=False)
    monkeypatch.delenv("AEROCLOUD_DEBUG_GEO_ALWAYS", raising=False)
    assert debug_enabled() is False


def test_debug_enabled_with_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """debug_enabled() is True when AEROCLOUD_DEBUG_GEO=1."""
    monkeypatch.setenv(_ENV_VAR, "1")
    assert debug_enabled() is True


def test_debug_disabled_with_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """debug_enabled() is False when AEROCLOUD_DEBUG_GEO=0."""
    monkeypatch.setenv(_ENV_VAR, "0")
    assert debug_enabled() is False


def test_debug_disabled_with_false_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """debug_enabled() is False when AEROCLOUD_DEBUG_GEO=false."""
    monkeypatch.setenv(_ENV_VAR, "false")
    assert debug_enabled() is False


def test_debug_enabled_with_true_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """debug_enabled() is True when AEROCLOUD_DEBUG_GEO=true."""
    monkeypatch.setenv(_ENV_VAR, "true")
    assert debug_enabled() is True


def test_dump_returns_none_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """dump_geometry_debug returns None when env var is not set."""
    monkeypatch.delenv(_ENV_VAR, raising=False)
    monkeypatch.delenv("AEROCLOUD_DEBUG_GEO_ALWAYS", raising=False)

    mask = np.zeros((16, 16), dtype=bool)
    mask[4:12, 4:12] = True
    sdf = np.zeros((16, 16), dtype=np.float32)

    result = dump_geometry_debug(
        mask=mask,
        sdf=sdf,
        placement_json={"placed": [], "dropped_words": [], "stats": {}},
    )
    assert result is None


@pytest.fixture()
def _enable_debug(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Enable debug dump and change cwd to tmp_path so output lands there."""
    monkeypatch.setenv(_ENV_VAR, "1")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _small_mask_and_sdf() -> tuple[np.ndarray, np.ndarray]:
    """Create a 16x16 bool mask and matching float32 SDF for tests."""
    mask = np.zeros((16, 16), dtype=bool)
    mask[4:12, 4:12] = True
    # Simple fake SDF (not a real EDT, but sufficient for dump tests)
    sdf = np.full((16, 16), -1.0, dtype=np.float32)
    sdf[4:12, 4:12] = 1.0
    return mask, sdf


def test_dump_creates_mask_png(_enable_debug: Path) -> None:
    """dump creates mask.png in the output directory."""
    mask, sdf = _small_mask_and_sdf()
    out = dump_geometry_debug(
        mask=mask,
        sdf=sdf,
        placement_json={"placed": []},
        tag="test",
    )
    assert out is not None
    assert (out / "mask.png").exists()


def test_dump_creates_placement_json(_enable_debug: Path) -> None:
    """dump creates placement.json with the supplied dict."""
    mask, sdf = _small_mask_and_sdf()
    payload = {"placed": [{"word": "hello"}], "stats": {"total_words": 1}}
    out = dump_geometry_debug(mask=mask, sdf=sdf, placement_json=payload, tag="test")
    assert out is not None
    data = json.loads((out / "placement.json").read_text())
    assert data["placed"][0]["word"] == "hello"


def test_dump_creates_env_json(_enable_debug: Path) -> None:
    """dump creates env.json with required keys."""
    mask, sdf = _small_mask_and_sdf()
    out = dump_geometry_debug(mask=mask, sdf=sdf, placement_json={}, tag="test")
    assert out is not None
    env = json.loads((out / "env.json").read_text())
    for key in ("python", "platform", "numpy", "pillow", "freetype"):
        assert key in env, f"env.json missing key {key!r}"


def test_dump_mask_png_is_readable(_enable_debug: Path) -> None:
    """mask.png written by dump_geometry_debug is a valid L-mode PNG."""
    mask, sdf = _small_mask_and_sdf()
    out = dump_geometry_debug(mask=mask, sdf=sdf, placement_json={}, tag="test")
    assert out is not None
    img = Image.open(out / "mask.png")
    assert img.mode == "L"
    assert img.size == (16, 16)


def test_dump_tag_sanitization(_enable_debug: Path) -> None:
    """Special characters in tag are sanitized to underscore."""
    mask, sdf = _small_mask_and_sdf()
    out = dump_geometry_debug(
        mask=mask,
        sdf=sdf,
        placement_json={},
        tag="bad/tag!test",
    )
    assert out is not None
    # Directory name must not contain the slash
    assert "/" not in out.name


def test_dump_matplotlib_import_error_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
    _enable_debug: Path,
) -> None:
    """If matplotlib is not importable, dump continues and writes .MISSING sentinel."""
    # Force ImportError for matplotlib by temporarily hiding it from sys.modules
    monkeypatch.setitem(sys.modules, "matplotlib", None)  # type: ignore[arg-type]

    mask, sdf = _small_mask_and_sdf()
    # Should not raise even with matplotlib unavailable
    out = dump_geometry_debug(mask=mask, sdf=sdf, placement_json={}, tag="nomat")
    assert out is not None
    # mask.png and placement.json must still be present
    assert (out / "mask.png").exists()
    assert (out / "placement.json").exists()
    # MISSING sentinel is written
    assert (out / "sdf_heatmap.MISSING").exists()


def test_dump_with_spiral_trace(_enable_debug: Path) -> None:
    """dump with a spiral_trace list does not crash (matplotlib may or may not exist)."""
    mask, sdf = _small_mask_and_sdf()
    trace = [(4, 4), (5, 5), (6, 6), (7, 7)]
    out = dump_geometry_debug(
        mask=mask,
        sdf=sdf,
        placement_json={},
        spiral_trace=trace,
        tag="trace",
    )
    assert out is not None
    assert (out / "mask.png").exists()
