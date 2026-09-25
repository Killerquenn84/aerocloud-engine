---
phase: 12-production-v1
plan: "02"
subsystem: export
tags: [svg, pdf, lxml, reportlab, security, validators, pydantic, tdd, bezier]

requires:
  - phase: 07-geometry-v2
    provides: BezierCurve and BezierGlyph models consumed by svg_export and pdf_export
  - phase: 12-production-v1/12-01
    provides: export/__init__.py package structure, export test directory structure

provides:
  - export_svg(): BezierGlyph list to SVG XML string via lxml.etree (PROD-03)
  - glyph_to_svg_path(): single BezierGlyph to SVG path d-attribute string
  - _bezier_curve_to_svg_cmd(): BezierCurve to SVG C command with (y,x)→(x,y) flip
  - export_pdf(): BezierGlyph list to PDF bytes via ReportLab at 300 DPI (PROD-04)
  - validate_hex_color(): hex color allow-list via ^#[0-9a-fA-F]{3,8}$ (PROD-15)
  - validate_font_name(): font allow-list from assets/fonts/ directory (PROD-14)
  - validate_no_path_traversal(): rejects ../, ..\, null bytes (PROD-13)
  - get_allowed_fonts(): frozenset of allowed font family names (cached at import)
  - RenderRequest.colors field with hex color validator
  - RenderRequest.font_family and shape_b64 field validators

affects:
  - 12-05 (FastAPI render endpoint — RenderRequest validators are live)
  - 12-06 (Integration tests — SVG/PDF export is testable end-to-end)

tech-stack:
  added:
    - lxml>=5.0.0 (SVG document generation via etree — added to [production] optional group)
  patterns:
    - TDD Red-Green per task: tests written before implementation, verified failing
    - Single flip point: (y,x)→(x,y) coordinate flip happens EXACTLY ONCE per module
    - Pure validators: security.py functions are pure (no I/O at call time), testable in isolation
    - Pydantic field_validator wiring: security functions called from @field_validator callbacks
    - Module-level font cache: _ALLOWED_FONTS frozenset loaded once at import, zero-cost on subsequent calls

key-files:
  created:
    - packages/engine/src/aerocloud/export/svg_export.py
    - packages/engine/src/aerocloud/export/pdf_export.py
    - packages/engine/src/aerocloud/models/security.py
    - packages/engine/tests/export/unit/test_svg_export.py
    - packages/engine/tests/export/unit/test_pdf_export.py
    - packages/engine/tests/unit/__init__.py
    - packages/engine/tests/unit/test_security_validators.py
  modified:
    - packages/engine/src/aerocloud/export/__init__.py (added svg/pdf exports)
    - packages/engine/src/aerocloud/models/api.py (added colors field + 3 field_validators)
    - packages/engine/pyproject.toml (added lxml>=5.0.0 to [production] group)

key-decisions:
  - "lxml.etree used for SVG generation (not svgelements) — more reliable document API per phase 12 research fallback note"
  - "Coordinate flip (y,x)→(x,y) happens in exactly one place per module: _bezier_curve_to_svg_cmd and _build_glyph_path"
  - "HEX_COLOR_RE pattern is ^#[0-9a-fA-F]{3,8}$ exactly as specified in D-15 — 3 to 8 hex chars with leading #"
  - "get_allowed_fonts() uses importlib.resources with Path fallback — works in both editable + wheel installs"
  - "Font allow-list uses directory names under assets/fonts/ — Inter and IBM-Plex-Serif are the current entries"
  - "_ALLOWED_FONTS cached as module-level frozenset at import time — zero I/O overhead per validation call"

patterns-established:
  - "Single coordinate flip point: each export module flips (y,x)→(x,y) in exactly one private function"
  - "Security validators are pure functions, testable without Pydantic, wired via field_validator"
  - "mypy --strict required: all type: ignore comments removed; lxml tostring result cast via assert isinstance"

requirements-completed: [PROD-03, PROD-04, PROD-13, PROD-14, PROD-15]

duration: 6min
completed: 2026-04-21
---

# Phase 12 Plan 02: SVG/PDF Export + Security Validators Summary

**BezierGlyph to SVG (lxml) and PDF (ReportLab 300 DPI) with hex color, font, and path traversal validators wired into RenderRequest — 73 TDD tests, mypy strict clean**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-21T23:47:44Z
- **Completed:** 2026-04-21T23:53:35Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Implemented `svg_export.py`: `_bezier_curve_to_svg_cmd` (C command with 6dp precision), `glyph_to_svg_path` (M/C/Z path per contour), `export_svg` (lxml SVG document with viewBox/width/height/fill, PROD-03)
- Implemented `pdf_export.py`: `export_pdf` via ReportLab pdfgen.Canvas at 300 DPI (PX_TO_PT=0.24), beginPath/moveTo/curveTo/closePath/drawPath per contour, valid %PDF bytes output (PROD-04)
- Implemented `security.py`: `validate_hex_color` (^#[0-9a-fA-F]{3,8}$ regex per D-15), `validate_font_name` (assets/fonts/ directory allow-list per D-16), `validate_no_path_traversal` (rejects ../, .., \x00 per D-17), `get_allowed_fonts` (module-level cached frozenset)
- Updated `api.py` RenderRequest: added `colors: list[str] | None` field, wired three `@field_validator` callbacks for font_family, shape_b64, colors
- 73 unit tests: 21 SVG tests, 11 PDF tests, 43 security/integration tests — all green

## Task Commits

1. **Task 1: SVG + PDF export modules (PROD-03, PROD-04)** — `cf7d0c1` (feat)
2. **Task 2: Security validators — color, font, path traversal (PROD-13, PROD-14, PROD-15)** — `78cbdf5` (feat)

## Files Created/Modified

- `packages/engine/src/aerocloud/export/svg_export.py` — export_svg, glyph_to_svg_path, _bezier_curve_to_svg_cmd
- `packages/engine/src/aerocloud/export/pdf_export.py` — export_pdf, DPI=300, PX_TO_PT=0.24
- `packages/engine/src/aerocloud/models/security.py` — validate_hex_color, validate_font_name, validate_no_path_traversal, get_allowed_fonts
- `packages/engine/src/aerocloud/models/api.py` — RenderRequest.colors field + 3 field_validators
- `packages/engine/src/aerocloud/export/__init__.py` — added export_svg, glyph_to_svg_path, export_pdf, DPI, PX_TO_PT
- `packages/engine/tests/export/unit/test_svg_export.py` — 21 tests (coordinate flip, XML validity, path commands, colors)
- `packages/engine/tests/export/unit/test_pdf_export.py` — 11 tests (magic bytes, length, precision, colors)
- `packages/engine/tests/unit/test_security_validators.py` — 43 tests (color regex, font allow-list, traversal rejection, RenderRequest integration)
- `packages/engine/tests/unit/__init__.py` — new package init
- `packages/engine/pyproject.toml` — added lxml>=5.0.0 to [production] optional group

## Decisions Made

- Used `lxml.etree` for SVG generation (not `svgelements`) — lxml provides a stable document-generation API; svgelements has unreliable document-level serialization per research note
- Coordinate flip `(y,x)→(x,y)` encapsulated in one private function per module (`_bezier_curve_to_svg_cmd` in svg, `_build_glyph_path` in pdf) — prevents double-flip bugs
- `etree.tostring(encoding="unicode")` returns `str` when encoding is "unicode"; `assert isinstance(result, str)` satisfies mypy --strict without `type: ignore`
- `_ALLOWED_FONTS` frozenset loaded once at module import time — font directory scan is O(n) I/O, caching eliminates it from every validation call

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing lxml dependency**
- **Found during:** Task 1 (first test collection)
- **Issue:** `from lxml import etree` failed with `ModuleNotFoundError: No module named 'lxml'`
- **Fix:** `uv pip install lxml` (installed lxml==6.1.0); added `lxml>=5.0.0` to `[production]` optional group in pyproject.toml
- **Files modified:** `packages/engine/pyproject.toml`
- **Verification:** Test collection succeeded; all 30 SVG+PDF tests passed
- **Committed in:** `cf7d0c1` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed mypy --strict violations in svg_export.py, pdf_export.py, security.py**
- **Found during:** Post-task mypy check
- **Issue:** (a) `etree.tostring` returns `bytes | str` — mypy flagged `no-any-return`; (b) `_hex_to_color` missing return type; (c) `type: ignore[attr-defined]` and `type: ignore[union-attr]` unused in security.py (lxml/importlib types resolved cleanly)
- **Fix:** Added `assert isinstance(result, str)` after tostring; typed `_hex_to_color` return as `HexColor`; removed unused `type: ignore` comments from security.py
- **Files modified:** `svg_export.py`, `pdf_export.py`, `security.py`
- **Verification:** `uv run mypy ... --strict` → "Success: no issues found in 3 source files"
- **Committed in:** `78cbdf5` (Task 2 commit, mypy fixes applied before commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both required for correct operation and type safety. No scope creep.

## Issues Encountered

- `importlib.resources.files(...).iterdir()` on editable installs returns traversable objects; `is_dir()` is available but mypy's lxml/importlib stubs initially flagged as `attr-defined` — resolved when mypy ran without errors after removing type: ignore comments (stubs were correct)

## Known Stubs

None — all functions are fully implemented.

## Threat Flags

None — all threat mitigations from STRIDE register applied:
- T-12-02-01: `validate_hex_color` guards fill= SVG attribute against XSS
- T-12-02-02: `validate_font_name` uses assets/fonts/ allow-list (not user-controllable)
- T-12-02-03: `validate_no_path_traversal` on shape_b64 field in RenderRequest
- T-12-02-04: pdf_export processes only internal BezierGlyph data (accepted)

## Next Phase Readiness

- SVG export is ready for Plan 05 (FastAPI render endpoint — RenderResult.svg field)
- PDF export ready for direct use or future endpoint
- RenderRequest security validators are live for all future API plans
- Font allow-list currently contains: Inter, IBM-Plex-Serif

---
*Phase: 12-production-v1*
*Completed: 2026-04-21*
