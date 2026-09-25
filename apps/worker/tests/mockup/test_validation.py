"""Sprint P26 — validation guard tests (scenarios 1, 2, 3, 4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from aerocloud_worker.mockup.exceptions import (
    InvalidDesignError,
    InvalidPSDError,
    PSDTooLargeError,
)
from aerocloud_worker.mockup.validation import (
    validate_design,
    validate_psd_header,
    validate_psd_size,
)


# ---------------------------------------------------------------------------
# Scenario 1 — corrupt PSD header
# ---------------------------------------------------------------------------


def test_scenario_1_corrupt_header_is_rejected(corrupt_psd_path: Path) -> None:
    with pytest.raises(InvalidPSDError) as excinfo:
        validate_psd_header(corrupt_psd_path)
    assert "magic" in str(excinfo.value).lower()


def test_scenario_1_truncated_psd_is_rejected(truncated_psd_path: Path) -> None:
    with pytest.raises(InvalidPSDError):
        validate_psd_header(truncated_psd_path)


def test_scenario_1_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidPSDError):
        validate_psd_header(tmp_path / "does-not-exist.psd")


def test_scenario_1_valid_header_passes(minimal_valid_psd_path: Path) -> None:
    # Must not raise.
    validate_psd_header(minimal_valid_psd_path)


# ---------------------------------------------------------------------------
# Scenario 2 — oversized PSD
# ---------------------------------------------------------------------------


def test_scenario_2_huge_psd_rejected_before_parse(huge_psd_path: Path) -> None:
    with pytest.raises(PSDTooLargeError) as excinfo:
        validate_psd_size(huge_psd_path, max_bytes=500_000_000)
    assert excinfo.value.size > excinfo.value.limit


def test_scenario_2_max_bytes_overridable(tmp_path: Path) -> None:
    p = tmp_path / "small.psd"
    p.write_bytes(b"8BPS" + b"\x00" * 100)
    # Tiny limit so a 104-byte file triggers.
    with pytest.raises(PSDTooLargeError):
        validate_psd_size(p, max_bytes=10)


def test_scenario_2_max_bytes_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "small.psd"
    p.write_bytes(b"8BPS" + b"\x00" * 100)
    monkeypatch.setenv("MAX_PSD_BYTES", "10")
    with pytest.raises(PSDTooLargeError):
        validate_psd_size(p)


def test_scenario_2_under_limit_passes(tmp_path: Path) -> None:
    p = tmp_path / "ok.psd"
    p.write_bytes(b"8BPS" + b"\x00" * 100)
    validate_psd_size(p, max_bytes=1_000_000)


# ---------------------------------------------------------------------------
# Scenario 3 — animated GIF rejected
# ---------------------------------------------------------------------------


def test_scenario_3_animated_gif_rejected(animated_gif_path: Path) -> None:
    with pytest.raises(InvalidDesignError) as excinfo:
        validate_design(animated_gif_path)
    assert "animated" in str(excinfo.value).lower()


def test_scenario_3_empty_design_rejected(empty_design_path: Path) -> None:
    with pytest.raises(InvalidDesignError):
        validate_design(empty_design_path)


def test_scenario_3_junk_design_rejected(junk_design_path: Path) -> None:
    with pytest.raises(InvalidDesignError):
        validate_design(junk_design_path)


def test_scenario_3_tiny_design_rejected(tiny_design_path: Path) -> None:
    with pytest.raises(InvalidDesignError) as excinfo:
        validate_design(tiny_design_path)
    assert "small" in str(excinfo.value).lower() or "min" in str(excinfo.value).lower()


def test_scenario_3_oversized_design_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MAX_DESIGN_DIM", "200")
    from PIL import Image

    p = tmp_path / "big.png"
    Image.new("RGBA", (500, 500), (1, 2, 3, 255)).save(p, format="PNG")
    with pytest.raises(InvalidDesignError):
        validate_design(p)


def test_scenario_3_valid_design_passes(valid_design_path: Path) -> None:
    validate_design(valid_design_path)


# ---------------------------------------------------------------------------
# Scenario 4 — unsupported color mode is asserted in test_engine_robustness
# (validation.py only validates *files*; CMYK detection lives inside the
# engine after psd-tools has parsed the file.)
# ---------------------------------------------------------------------------
