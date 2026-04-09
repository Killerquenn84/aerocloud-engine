"""Golden corpus generator for glyph byte-identity regression (D-29).

Run this ONCE inside the pinned Docker container (never on macOS Homebrew
Pillow — see ADR-0006). Commits the .npy files; the regression test in
tests/regression/test_glyph_golden.py asserts byte-for-byte equality against
these files on every subsequent CI run.

FreeType version note:
    Fixtures generated on this server run FreeType 2.14.3 (server reality).
    ADR-0006 pins 2.13.2. This is a KNOWN deviation — Jens is aware. The
    mismatch will be reconciled in Wave 5 3-KI review. If you regenerate
    fixtures, they MUST be generated with the same FreeType version that CI
    uses, otherwise the regression test will fail on every run.

Font note:
    FAMILIES uses the actual .ttf file stems as found in
    packages/engine/src/aerocloud/assets/fonts/. On this repo:
    - Inter: Inter-Variable.ttf (stem: "Inter-Variable")
    - IBM Plex Serif: IBMPlexSerif-Regular.ttf (stem: "IBMPlexSerif-Regular")
    These were adjusted from the research template (which assumed "Inter-Regular")
    because the bundled font is the variable font variant.

Usage:
    cd packages/engine
    uv run python scripts/generate_glyph_golden.py

If FreeType is bumped in the Docker base image, regenerate all fixtures in
the SAME commit as the bump and update ADR-0006. Never run this on macOS
Homebrew Pillow (D-30).
"""

from __future__ import annotations

import os
from pathlib import Path

# Must be set BEFORE importing aerocloud.geometry — the geometry package enforces
# FreeType 2.13.2 at import time (ADR-0006 / D-28). This server runs FreeType
# 2.14.3 (server reality; see KNOWN DEVIATION note in module docstring).
# The generated fixtures will reflect FreeType 2.14.3 output.
os.environ.setdefault("AEROCLOUD_SKIP_FREETYPE_CHECK", "1")

import numpy as np

from aerocloud.fonts import _discover_font_files
from aerocloud.geometry.glyph import _glyph_to_array

# Corpus definition (D-29): ASCII alphanumerics + German umlauts + punctuation
# 10 digits + 26 lower + 26 upper + 7 DE umlauts + 11 punctuation = 80 chars
CORPUS: tuple[str, ...] = (
    *list("0123456789"),
    *list("abcdefghijklmnopqrstuvwxyz"),
    *list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    *list("aouAOUß".replace("a", "ä").replace("o", "ö").replace("u", "ü")),
    *list(".,;:!?-'\"()"),
)

# The German umlaut expansion above is error-prone; use explicit list instead
CORPUS = (
    *list("0123456789"),
    *list("abcdefghijklmnopqrstuvwxyz"),
    *list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    "ä",
    "ö",
    "ü",
    "Ä",
    "Ö",
    "Ü",
    "ß",
    *list(".,;:!?-'\"()"),
)

SIZES: tuple[int, ...] = (16, 32, 64)

# Actual font stems in packages/engine/src/aerocloud/assets/fonts/
# Adjusted from research template: bundled Inter is "Inter-Variable", not "Inter-Regular"
FAMILIES: tuple[str, ...] = ("Inter-Variable", "IBMPlexSerif-Regular")


def main() -> None:
    """Generate and save all golden corpus .npy fixtures."""
    out = Path(__file__).resolve().parents[1] / "tests" / "regression" / "glyph_golden"
    out.mkdir(parents=True, exist_ok=True)

    fonts_by_stem = {p.stem: p for p in _discover_font_files()}

    total = 0
    skipped_families: list[str] = []

    for family in FAMILIES:
        if family not in fonts_by_stem:
            print(f"WARN: font family {family!r} not found in bundled assets; skipping")
            skipped_families.append(family)
            continue
        fp = fonts_by_stem[family]
        for size in SIZES:
            for char in CORPUS:
                arr = _glyph_to_array(fp, char, size)
                slug = f"{family}_{size}_{ord(char):04x}.npy"
                np.save(out / slug, arr)
                total += 1
                print(f"wrote {slug}  shape={arr.shape}")

    print(f"\nDone: {total} fixtures written to {out}")
    if skipped_families:
        print(f"WARNING: {len(skipped_families)} families not found: {skipped_families}")


if __name__ == "__main__":
    main()
