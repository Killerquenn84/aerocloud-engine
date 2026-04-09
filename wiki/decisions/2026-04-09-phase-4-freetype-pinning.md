# Decision Mirror: ADR-0006 FreeType Runtime Pinning (v2)

**Canonical source:** `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md`
**Date:** 2026-04-09 · **Revised 2026-04-09 (Wave 5 3-KI review)**
**Phase:** 04-geometry-v1

> This is a wiki mirror for `wiki:query` discoverability. The canonical ADR is
> the source of truth. Update the ADR first; then re-mirror here.

---

# ADR-0006 v2: FreeType Runtime Pinning at Geometry Package Import

Status: Accepted 2026-04-10 · **Revised 2026-04-09 (Wave 5 3-KI review)**
Phase: 04-geometry-v1

## Context

Glyph rasterization via `ImageFont.FreeTypeFont.getmask()` depends on the FreeType
library version linked into Pillow. Different environments ship different versions:

| Environment | FreeType version |
|---|---|
| Docker base image (production) | **2.14.3** (updated to match server) |
| Homebrew Pillow on macOS (arm64, 2026) | 2.14.2 (drift!) |
| Ubuntu 22.04 Pillow wheel | 2.13.2 (old) |
| **This server (Hostinger VPS)** | **2.14.3 (canonical)** |
| CI runner (Docker-based) | **2.14.3** (updated) |

A single-pixel glyph shift in `ä` at 32 pt causes Phase 9 MAP-Elites to assign the
word to a different archive cell, breaking reproducibility.

## Decision (v2 — Wave 5 3-KI review, 2026-04-09)

`_EXPECTED_FREETYPE = "2.14.3"` is asserted via `PIL.features.version("freetype2")`
at `aerocloud.geometry` package import time.

**Key changes from v1:**
- Pin updated from `"2.13.2"` → `"2.14.3"` to align with server reality and golden fixtures
- `AEROCLOUD_SKIP_FREETYPE_CHECK` env bypass **removed** (transitional measure no longer needed)
- `conftest.py` monkeypatches in `tests/geometry/` and `tests/regression/` **removed**
- 595/595 tests pass without bypass on this server (FreeType 2.14.3)

## 3-KI Review Outcome

All 3 reviewers agreed to update the pin:
- Claude: APPROVED-WITH-NOTES (update ADR-0006 before phase exit)
- Codex: APPROVED-WITH-FIXES (ADR/runtime/fixtures must all align on one version)
- Gemini: APPROVED-WITH-FIXES (update ADR-0006 to 2.14.3)

Jens approved Option A (update to 2.14.3) on 2026-04-09.

## Blocked alternatives

- `freetype.__version__` — reads the Python binding version, NOT the native library (D-26)
- `hint_style` parameter to `truetype()` — does NOT exist in Pillow 12.1.1 (hallucination)
- `Image.resize()` 4x-supersample trick — FP math not byte-identical across libc/libm (D-31)
- Homebrew Pillow — explicitly unsupported for geometry generation (D-30)

## References

- `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md` — canonical ADR
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-28, D-29, D-30
- `wiki/code/geometry-glyph.md`
- `.planning/phases/04-geometry-v1/04-3ki-review/consensus.md` — ratification record
