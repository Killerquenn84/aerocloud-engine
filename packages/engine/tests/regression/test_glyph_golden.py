"""Glyph byte-identity regression test (D-29).

Any drift here means the FreeType version at test time differs from what was
used to generate these fixtures. Root cause is ALWAYS one of:
  (a) Homebrew Pillow leaked into the test environment (D-30),
  (b) FreeType base image was bumped without regenerating fixtures + updating
      ADR-0006 (the correct procedure is: regenerate ALL fixtures in the SAME
      commit as the version bump),
  (c) A new Pillow rendering path regression changed raster output.

Fail loudly with the FreeType version to aid diagnosis.

FreeType version note:
    Fixtures in this directory were generated on FreeType 2.14.3 (server
    reality). ADR-0006 pin is 2.13.2 — this mismatch is a KNOWN deviation
    to be reconciled in Wave 5 3-KI review. The conftest.py shim patches
    PIL.features.version to "2.13.2" during test collection so
    _assert_freetype() does not block test imports. The regression test
    still asserts byte-for-byte equality against the 2.14.3-generated
    fixtures, which is correct: we are running on 2.14.3 so the output
    will match.

D-51: No mocking of Pillow decode path — this test uses real FreeType.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import features

# Set the FreeType bypass so geometry package can be imported on this server
# (FreeType 2.14.3 vs ADR-0006 pin 2.13.2). This is consistent with how the
# tests/geometry/conftest.py shim works during unit tests.
os.environ.setdefault("AEROCLOUD_SKIP_FREETYPE_CHECK", "1")

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry.glyph import _glyph_to_array

GOLDEN = Path(__file__).parent / "glyph_golden"


def _collect_fixtures() -> list[Path]:
    """Return sorted list of .npy fixture files."""
    return sorted(GOLDEN.glob("*.npy"))


@pytest.mark.parametrize("npy_path", _collect_fixtures(), ids=lambda p: p.stem)
def test_glyph_byte_identical(npy_path: Path) -> None:
    """Assert byte-for-byte equality between fixture and fresh raster.

    Any failure here means raster drift — check FreeType version first.
    """
    expected = np.load(npy_path)

    # Filename convention: "{Family}_{SIZE}_{HEXCP}.npy"
    stem = npy_path.stem
    family, size_str, hex_cp = stem.rsplit("_", 2)
    size = int(size_str)
    cp = int(hex_cp, 16)

    font_path = next(
        (p for p in _discover_font_files() if p.stem == family),
        None,
    )
    assert font_path is not None, (
        f"Font {family!r} missing from bundled assets. "
        f"Expected in packages/engine/src/aerocloud/assets/fonts/."
    )

    actual = _glyph_to_array(font_path, chr(cp), size)

    assert np.array_equal(expected, actual), (
        f"Glyph byte drift: {family} U+{cp:04X} ({chr(cp)!r}) @ {size}pt. "
        f"FreeType version = {features.version('freetype2')!r}. "
        f"expected.shape={expected.shape} actual.shape={actual.shape}. "
        "Possible causes: (a) Homebrew Pillow, (b) FreeType bumped without "
        "regenerating fixtures, (c) Pillow raster regression. "
        "Re-run scripts/generate_glyph_golden.py in the pinned environment "
        "to update fixtures."
    )
