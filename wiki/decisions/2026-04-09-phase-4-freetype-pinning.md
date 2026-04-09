# Decision Mirror: ADR-0006 FreeType Runtime Pinning

**Canonical source:** `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md`
**Date:** 2026-04-09 (mirrored from ADR accepted 2026-04-10)
**Phase:** 04-geometry-v1

> This is a wiki mirror for `wiki:query` discoverability. The canonical ADR is
> the source of truth. Update the ADR first; then re-mirror here.

---

# ADR-0006: FreeType Runtime Pinning at Geometry Package Import

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

Glyph rasterization via `ImageFont.FreeTypeFont.getmask()` depends on the FreeType
library version linked into Pillow. Different environments ship different versions:

| Environment | FreeType version |
|---|---|
| Docker base image (production) | 2.13.2 (pinned) |
| Homebrew Pillow on macOS (arm64, 2026) | 2.14.2 (drift!) |
| Ubuntu 22.04 Pillow wheel | 2.13.2 (matches) |
| **This server (Hostinger VPS)** | **2.14.3 (drift!)** |
| CI runner (Docker-based) | 2.13.2 (matches) |

A single-pixel glyph shift in `ä` at 32 pt causes Phase 9 MAP-Elites to assign the
word to a different archive cell, breaking reproducibility.

## Decision

`_EXPECTED_FREETYPE = "2.13.2"` is asserted via `PIL.features.version("freetype2")`
at `aerocloud.geometry` package import time.

```python
def _assert_freetype() -> None:
    actual = _pil_features.version("freetype2")
    if actual != _EXPECTED_FREETYPE:
        raise GeometryEnvironmentError(f"FreeType mismatch: expected {_EXPECTED_FREETYPE!r}, got {actual!r}")
```

**Bypass:** `AEROCLOUD_SKIP_FREETYPE_CHECK=1` environment variable suppresses the
check. Used in the test suite via `conftest.py` monkeypatch of `PIL.features.version`.

## Current reality on this server

The Hostinger VPS runs FreeType **2.14.3** (not 2.13.2). The test suite uses a
`conftest.py` shim that patches `PIL.features.version` to return `"2.13.2"`, so
tests pass. The golden glyph fixtures (`.npy` files) were generated on this server
with FreeType 2.14.3 and the bypass active.

**Consequence:** The `.npy` fixtures do NOT match what a Docker 2.13.2 environment
would generate. This discrepancy is tracked and will be resolved in Wave 5 3-KI
review, either by:
1. Regenerating fixtures in a Docker 2.13.2 container (preferred — aligns with production)
2. Relaxing the pin to accept either 2.13.x or 2.14.x (requires re-assessing Phase 9 risk)

## Blocked alternatives

- `freetype.__version__` — reads the Python binding version, NOT the native library (D-26)
- `hint_style` parameter to `truetype()` — does NOT exist in Pillow 12.1.1 (hallucination)
- `Image.resize()` 4x-supersample trick — FP math not byte-identical across libc/libm (D-31)
- Homebrew Pillow — explicitly unsupported for geometry generation (D-30)

## References

- `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md` — canonical ADR
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-28, D-29, D-30
- `wiki/code/geometry-glyph.md`
