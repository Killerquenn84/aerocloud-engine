"""Shared fixtures for the Mockup-Engine pytest suite (Sprints P23 + P26)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

# Repo root: <repo>/server/aerocloud-engine/apps/worker/tests/mockup/conftest.py
#                                   ^5                ^4   ^3    ^2   ^1     ^0
_REPO_ROOT = Path(__file__).resolve().parents[6]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def poster_frame_psd() -> Path:
    """Real-world fixture: 2300x2400 poster-frame PSD with 3 smart objects."""
    path = _FIXTURE_DIR / "poster-frame-test.psd"
    if not path.exists():
        pytest.skip(f"Fixture missing: {path}. See tests/fixtures/README.md")
    return path


@pytest.fixture(scope="session")
def design_png(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a 600x600 checkerboard PNG so visual placement is obvious."""
    out = tmp_path_factory.mktemp("designs") / "test-design.png"
    img = Image.new("RGBA", (600, 600), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    cell = 60
    for y in range(0, 600, cell):
        for x in range(0, 600, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(220, 30, 30, 255))
            else:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(30, 90, 220, 255))
    draw.rectangle([0, 0, 599, 599], outline=(0, 0, 0, 255), width=8)
    draw.line([(0, 0), (599, 599)], fill=(0, 0, 0, 255), width=6)
    draw.line([(599, 0), (0, 599)], fill=(0, 0, 0, 255), width=6)
    img.save(out, format="PNG")
    return out


# ---------------------------------------------------------------------------
# Sprint P26 — pathological inputs for robustness tests
# ---------------------------------------------------------------------------


@pytest.fixture
def corrupt_psd_path(tmp_path: Path) -> Path:
    """A file masquerading as a PSD with random bytes and bad magic."""
    p = tmp_path / "corrupt.psd"
    p.write_bytes(b"NOTAPSD!" + os.urandom(100))
    return p


@pytest.fixture
def truncated_psd_path(tmp_path: Path) -> Path:
    """Smaller than the 4-byte header."""
    p = tmp_path / "trunc.psd"
    p.write_bytes(b"8B")  # only 2 bytes
    return p


@pytest.fixture
def huge_psd_path(tmp_path: Path) -> Path:
    """A valid-looking PSD header on a sparse 600 MB file (no real bytes used).

    We seek + write a single byte so the apparent size exceeds MAX_PSD_BYTES
    but the test does not have to materialise 600 MB.
    """
    p = tmp_path / "huge.psd"
    with p.open("wb") as fh:
        fh.write(b"8BPS")
        fh.seek(600_000_000 - 1)
        fh.write(b"\x00")
    return p


@pytest.fixture
def animated_gif_path(tmp_path: Path) -> Path:
    """Two-frame animated GIF — Pillow reports is_animated=True."""
    p = tmp_path / "animated.gif"
    frame_a = Image.new("RGB", (200, 200), (255, 0, 0))
    frame_b = Image.new("RGB", (200, 200), (0, 0, 255))
    frame_a.save(
        p,
        format="GIF",
        save_all=True,
        append_images=[frame_b],
        duration=100,
        loop=0,
    )
    return p


@pytest.fixture
def tiny_design_path(tmp_path: Path) -> Path:
    """A 1x1 PNG — under MIN_DESIGN_DIM."""
    p = tmp_path / "tiny.png"
    Image.new("RGBA", (1, 1), (255, 255, 255, 255)).save(p, format="PNG")
    return p


@pytest.fixture
def empty_design_path(tmp_path: Path) -> Path:
    """A zero-byte file at the PNG path."""
    p = tmp_path / "empty.png"
    p.write_bytes(b"")
    return p


@pytest.fixture
def junk_design_path(tmp_path: Path) -> Path:
    """A non-image file with a .png extension."""
    p = tmp_path / "junk.png"
    p.write_bytes(b"<html><body>I am not an image</body></html>")
    return p


@pytest.fixture
def valid_design_path(tmp_path: Path) -> Path:
    """A plain 400x400 RGBA PNG that passes all design validations."""
    p = tmp_path / "ok-design.png"
    Image.new("RGBA", (400, 400), (10, 200, 50, 255)).save(p, format="PNG")
    return p


@pytest.fixture
def minimal_valid_psd_path(tmp_path: Path) -> Path:
    """A PSD whose header passes the magic-byte sniff but is otherwise empty.

    Use this to test that header-sniff *alone* succeeds — do not feed it to
    psd-tools, it will fail there.
    """
    p = tmp_path / "header-only.psd"
    p.write_bytes(b"8BPS" + b"\x00" * 256)
    return p
