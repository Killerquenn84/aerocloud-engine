# ADR-0006: FreeType Runtime Pinning at Geometry Package Import

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

Word cloud glyph rasterization (D-24..D-31) relies on Pillow's `ImageFont.FreeTypeFont.getmask()`
to produce pixel-exact bounding boxes for every character. The exact pixel layout of each
glyph depends on the FreeType library version linked into Pillow at build time.

**The cross-platform drift problem (D-29, D-30):**

Different environments ship different FreeType versions:

| Environment | FreeType version |
|-------------|-----------------|
| Docker base image (Phase 1, production) | 2.13.2 (pinned) |
| Homebrew Pillow on macOS (arm64, 2026) | 2.14.2 (drift!) |
| Ubuntu 22.04 Pillow wheel | 2.13.2 (matches) |
| CI runner (Docker-based) | 2.13.2 (matches) |

A single-pixel shift in a glyph AABB (e.g., `ä` at 32 pt) causes Phase 9 MAP-Elites
to assign the word to a different archive cell, which pollutes the archive with entries
that cannot be reproduced from the stored seed + version. The Phase 1 determinism
requirement `(input, seed, version) → output` is violated.

Codex adversarial review (codex-g4.md) confirmed that `PIL.features.version("freetype2")`
is the correct check — NOT `freetype.__version__` (which reads the `freetype-py` binding
version, NOT the native library version). The Pillow docs reference:
https://pillow.readthedocs.io/en/stable/reference/features.html

## Decision

**`_EXPECTED_FREETYPE = "2.13.2"` is asserted via `PIL.features.version("freetype2")`
at `aerocloud.geometry` package import time.**

```python
# In geometry/__init__.py (added in Wave 1 after errors.py is stable)
from PIL import features as _pil_features
from aerocloud.geometry.errors import GeometryEnvironmentError

_EXPECTED_FREETYPE = "2.13.2"

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

**Blocked alternatives:**

- `freetype.__version__` — reads the Python binding version, NOT the native library (Codex g-4)
- `Pillow.__version__` — the Pillow Python version is independent of the bundled FreeType
- `Image.resize()` 4x-supersample trick — BLOCKED (D-31): adds a second FP raster stage
  with no byte-identity guarantee across libc/libm (`Resample.c` uses `double`/`sin`/`cos`)
- `hint_style` parameter to `ImageFont.truetype()` — does NOT exist in Pillow 12.1.1
  (D-26, Codex g-4 hallucination kill)
- Homebrew Pillow — explicitly unsupported for geometry generation runs (D-30)

**Note on Wave 0:** The `_assert_freetype()` call is added in Wave 1 after `errors.py` is
stable. The Wave 0 `geometry/__init__.py` stub imports error types only and does NOT call
`_assert_freetype()` — this is intentional to allow the error hierarchy tests to run
without requiring a pinned FreeType environment.

## Consequences

- Any developer who runs geometry code with Homebrew Pillow (macOS + Homebrew FreeType 2.14.2)
  gets an immediate, actionable `GeometryEnvironmentError` at import time — not a silent
  byte drift that only appears days later in archive comparisons
- CI is Docker-only for the geometry test job, which guarantees FreeType 2.13.2
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
