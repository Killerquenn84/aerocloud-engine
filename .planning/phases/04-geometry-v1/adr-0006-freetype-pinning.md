# ADR-0006: FreeType Runtime Pinning at Geometry Package Import

Status: Accepted 2026-04-10 · **Revised 2026-04-09 (Wave 5 3-KI review)**
Phase: 04-geometry-v1

## Context

Word cloud glyph rasterization (D-24..D-31) relies on Pillow's `ImageFont.FreeTypeFont.getmask()`
to produce pixel-exact bounding boxes for every character. The exact pixel layout of each
glyph depends on the FreeType library version linked into Pillow at build time.

**The cross-platform drift problem (D-29, D-30):**

Different environments ship different FreeType versions:

| Environment | FreeType version |
|-------------|-----------------|
| Docker base image (Phase 1, production) | **2.14.3** (updated, matches server) |
| Homebrew Pillow on macOS (arm64, 2026) | 2.14.2 (drift!) |
| Ubuntu 22.04 Pillow wheel | 2.13.2 (old; production Docker now targets 2.14.3) |
| CI runner (Docker-based) | **2.14.3** (updated to match server) |
| **This server (Hostinger VPS)** | **2.14.3** (canonical; golden fixtures generated here) |

A single-pixel shift in a glyph AABB (e.g., `ä` at 32 pt) causes Phase 9 MAP-Elites
to assign the word to a different archive cell, which pollutes the archive with entries
that cannot be reproduced from the stored seed + version. The Phase 1 determinism
requirement `(input, seed, version) → output` is violated.

Codex adversarial review (codex-g4.md) confirmed that `PIL.features.version("freetype2")`
is the correct check — NOT `freetype.__version__` (which reads the `freetype-py` binding
version, NOT the native library version). The Pillow docs reference:
https://pillow.readthedocs.io/en/stable/reference/features.html

## Decision

**`_EXPECTED_FREETYPE = "2.14.3"` is asserted via `PIL.features.version("freetype2")`
at `aerocloud.geometry` package import time.**

```python
# In geometry/__init__.py (Wave 5 revision — bypass removed, pin aligned to server)
from PIL import features as _pil_features
from aerocloud.geometry.errors import GeometryEnvironmentError

_EXPECTED_FREETYPE = "2.14.3"

def _assert_freetype() -> None:
    """Raise GeometryEnvironmentError if FreeType version does not match pin (D-28)."""
    actual = _pil_features.version("freetype2")
    if actual != _EXPECTED_FREETYPE:
        raise GeometryEnvironmentError(
            f"FreeType version mismatch: expected {_EXPECTED_FREETYPE!r}, "
            f"got {actual!r}. "
            f"macOS Homebrew Pillow is NOT supported for geometry generation; "
            f"use the pinned Docker image or the uv-pinned wheel. "
            f"See ADR-0006."
        )
```

**The `AEROCLOUD_SKIP_FREETYPE_CHECK` bypass has been removed** (Wave 5 3-KI review
2026-04-09). It was a transitional measure while the pin was 2.13.2 but the server
ran 2.14.3. With the pin now aligned to server reality, the bypass is obsolete and
its presence posed a CI false-positive risk (someone setting the env var would silently
skip the check). The `conftest.py` monkeypatches in `tests/geometry/` and
`tests/regression/` have also been removed.

**Blocked alternatives:**

- `freetype.__version__` — reads the Python binding version, NOT the native library (Codex g-4)
- `Pillow.__version__` — the Pillow Python version is independent of the bundled FreeType
- `Image.resize()` 4x-supersample trick — BLOCKED (D-31): adds a second FP raster stage
  with no byte-identity guarantee across libc/libm (`Resample.c` uses `double`/`sin`/`cos`)
- `hint_style` parameter to `ImageFont.truetype()` — does NOT exist in Pillow 12.1.1
  (D-26, Codex g-4 hallucination kill)
- Homebrew Pillow — explicitly unsupported for geometry generation runs (D-30)

## Consequences

- Any developer who runs geometry code with Homebrew Pillow (macOS + Homebrew FreeType 2.14.2)
  gets an immediate, actionable `GeometryEnvironmentError` at import time — not a silent
  byte drift that only appears days later in archive comparisons
- CI is Docker-only for the geometry test job, targeting FreeType 2.14.3
- Developer machines that want to run geometry locally MUST use the Docker dev stack
- The golden-corpus regression test (`tests/regression/test_glyph_golden.py`, D-29) is the
  *enforcement* mechanism; this ADR is the *documentation* layer
- `_EXPECTED_FREETYPE` is a module constant, not a config value — changing it requires
  regenerating all `.npy` golden fixtures and is a deliberate, reviewed action

## Enforcement

- `geometry/__init__.py::_assert_freetype()` — raised at package import (Wave 1+)
- `tests/geometry/unit/test_package_init.py::test_assert_freetype_passes_in_ci` — verifies
  no exception on the expected Docker FreeType version
- `tests/regression/test_glyph_golden.py` — byte-identical `.npy` fixture comparison
  catches any drift that slips past the version check (e.g., same version string but
  different build flags)

## References

- `.planning/phases/04-geometry-v1/04-CONTEXT.md` D-28, D-29, D-30, D-31
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md` — `hint_style` hallucination,
  Homebrew drift, `Image.resize` BLOCKED, `PIL.features.version` recommendation
- https://pillow.readthedocs.io/en/stable/reference/features.html — `PIL.features.version`
- https://pillow.readthedocs.io/en/stable/reference/ImageFont.html — `truetype()` signature
- https://formulae.brew.sh/formula/freetype — Homebrew FreeType 2.14.2 (drift source)

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2026-04-10 | Initial acceptance — pin set to 2.13.2, SKIP bypass added as transitional measure | Wave 1 execution |
| 2026-04-09 | **v2: Pin updated to 2.14.3; bypass removed; conftest shims removed.** All 3 KI reviewers agreed (Claude APPROVED-WITH-NOTES, Codex APPROVED-WITH-FIXES, Gemini APPROVED-WITH-FIXES). Jens approved 2026-04-09. | Wave 5 3-KI review |
