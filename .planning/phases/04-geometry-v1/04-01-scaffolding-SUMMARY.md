---
phase: 04-geometry-v1
plan: 01
subsystem: geometry
tags: [geometry, sdf, adr, errors, cachetools, blake3, pytest-benchmark, fixtures, python]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: config.py Settings pattern, set_seed determinism, structlog/OTel observability
  - phase: 02-datenmodell-wiki
    provides: AeroCloudBase Pydantic model pattern
  - phase: 03-nlp-v1
    provides: RLock registry pattern (tokenize.py), hermetic test fixture pattern
provides:
  - ADR-0004: SDF sign convention positive=inside locked (D-09, UNCHANGEABLE)
  - ADR-0005: (y,x) canonical coordinate system locked (D-14..D-16)
  - ADR-0006: FreeType 2.13.2 runtime pinning spec (D-28..D-30)
  - aerocloud.geometry.errors: typed 5-class error hierarchy (GeometryError + 4 subclasses)
  - aerocloud.geometry: Wave 0 package stub re-exporting all error types
  - config.sdf_cache_max_bytes: 384 MiB per-worker SDF cache budget (D-18), field + singleton
  - cachetools>=7.0.0 + blake3>=1.0.0: installed in [geometry] optional-dependencies
  - pytest-benchmark>=4.0.0: installed in dev deps
  - packages/engine/tests/geometry/ subtree: 7 subdirs with __init__.py
  - packages/engine/tests/regression/glyph_golden/: empty directory for Wave 2b .npy fixtures
  - packages/engine/tests/conftest.py: 5 mask byte fixtures for all geometry tests
affects:
  - 04-02-mask-sdf (Wave 1 reads errors.py + geometry/__init__)
  - 04-03-sdf-cache-glyph (Wave 2a reads errors.py + config.sdf_cache_max_bytes)
  - 04-04-glyph-golden (Wave 2b reads regression/glyph_golden/ + conftest fixtures)
  - 04-05-collision-placement (Wave 3 reads errors.py + conftest fixtures)
  - 04-06-observability (Wave 4 reads config + errors)
  - 05-renderer-v1 (consumes geometry.errors subclasses)
  - 06-inner-loop-v1 (consumes geometry.errors.PlacementFailedError)

# Tech tracking
tech-stack:
  added:
    - cachetools 7.0.5 (bytes-bounded LRU cache for SDF)
    - blake3 1.0.8 (strong content hash for SDF cache key)
    - pytest-benchmark 5.2.3 (geometry performance tests)
  patterns:
    - ADR as locked-decision prose: 3 ADRs cite D-decisions from CONTEXT.md
    - settings singleton: module-level `settings: Settings = Settings()` in config.py
    - hermetic mask fixtures: PNG-encoded bool arrays via PIL + numpy in conftest.py
    - TDD RED→GREEN: test_errors.py written before errors.py, verified RED then GREEN

key-files:
  created:
    - .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
    - .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
    - .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
    - packages/engine/src/aerocloud/geometry/__init__.py
    - packages/engine/src/aerocloud/geometry/errors.py
    - packages/engine/tests/conftest.py
    - packages/engine/tests/geometry/unit/test_errors.py
    - packages/engine/tests/geometry/{unit,integration,property,state,determinism,security,performance}/__init__.py
    - packages/engine/tests/regression/__init__.py
    - packages/engine/tests/regression/glyph_golden/.gitkeep
  modified:
    - packages/engine/src/aerocloud/config.py (added sdf_cache_max_bytes + settings singleton)
    - packages/engine/pyproject.toml (added cachetools>=7.0.0 + blake3>=1.0.0 to [geometry])
    - pyproject.toml (root, added pytest-benchmark>=4.0.0 to [dependency-groups] dev)
    - uv.lock (updated with new packages)

key-decisions:
  - "settings singleton added to config.py — plan requires `from aerocloud.config import settings` but module only had Settings class + load_settings(); singleton added as Rule 2 (missing critical for test contract)"
  - "pytest-benchmark added to root pyproject.toml dev deps (not engine optional) — benchmark tests run in full workspace context, not per-package"
  - "packages/engine/tests/ structure created under engine package (not root tests/) — plan explicitly places geometry tests under packages/engine/tests/ and verify commands use `cd packages/engine && uv run pytest tests/geometry/...`"

patterns-established:
  - "Typed error hierarchy: GeometryError base + domain subclasses, no string parsing needed by consumers"
  - "Hermetic PNG fixtures: numpy bool mask → PIL Image → PNG bytes in conftest.py, reusable across all geometry waves"
  - "Separate conftest.py per sub-package: packages/engine/tests/conftest.py for geometry-specific fixtures vs. root tests/conftest.py for cross-package"
  - "ADR as decision lock: each locked architect constraint gets its own ADR file with Context/Decision/Consequences/Enforcement/References"

requirements-completed: [GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07]

# Metrics
duration: 7min
completed: 2026-04-09
---

# Phase 4 Plan 01: Scaffolding Summary

**Three ADRs locking D-09/D-14/D-28, typed 5-class geometry error hierarchy, sdf_cache_max_bytes Pydantic setting (384 MiB), cachetools+blake3+pytest-benchmark deps, and 8-directory test subtree with 5 hermetic PNG mask fixtures**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-09T13:47:25Z
- **Completed:** 2026-04-09T13:53:50Z
- **Tasks:** 3/3
- **Files modified:** 13 created, 4 modified

## Accomplishments

- ADR-0004/0005/0006 lock D-09 (positive=inside SDF), D-14..D-16 ((y,x) canonical + AABB naming), and D-28..D-30 (FreeType 2.13.2 pinning) into cited prose
- `aerocloud.geometry.errors` module with `GeometryError`, `EmptyMaskError`, `MaskFormatError`, `GeometryEnvironmentError`, `PlacementFailedError` — 5 tests green, mypy strict, ruff clean
- `config.py` extended with `sdf_cache_max_bytes = 402653184` (384 MiB, 1 MiB floor) + `settings` module-level singleton
- `cachetools 7.0.5` + `blake3 1.0.8` installed in `[geometry]` optional-deps; `pytest-benchmark 5.2.3` in dev deps
- Full `tests/geometry/` subtree (7 subdirs) + `regression/glyph_golden/` + `conftest.py` with 5 hermetic mask fixtures (circle/square/C-shape/crescent/tiny)

## Task Commits

1. **Task T1: ADR-0004/0005/0006 lock files** — `577c933` (feat)
2. **Task T2: geometry/errors.py + __init__ + config sdf_cache_max_bytes + TDD green** — `654b4a3` (feat)
3. **Task T3: deps + test subtree + conftest fixtures** — `16172aa` (feat)

## Files Created/Modified

- `.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md` — D-09 positive=inside SDF lock
- `.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md` — D-14..D-16 (y,x) canonical + AABB naming lock
- `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md` — D-28..D-30 FreeType 2.13.2 lock
- `packages/engine/src/aerocloud/geometry/__init__.py` — Wave 0 stub re-exporting 5 error types
- `packages/engine/src/aerocloud/geometry/errors.py` — typed error hierarchy (5 classes)
- `packages/engine/src/aerocloud/config.py` — added `sdf_cache_max_bytes` + `settings` singleton
- `packages/engine/pyproject.toml` — added `cachetools>=7.0.0` + `blake3>=1.0.0`
- `pyproject.toml` (root) — added `pytest-benchmark>=4.0.0` to dev deps
- `packages/engine/tests/conftest.py` — 5 PNG mask byte fixtures
- `packages/engine/tests/geometry/unit/test_errors.py` — 5 unit tests (all green)
- `packages/engine/tests/geometry/{integration,property,state,determinism,security,performance}/__init__.py`
- `packages/engine/tests/regression/__init__.py` + `glyph_golden/.gitkeep`

## Error Class Hierarchy Tree

```
Exception
└── GeometryError          (base — pattern-matched by Phase 5 + 6)
    ├── MaskFormatError    (PNG-only contract violations, D-04)
    ├── EmptyMaskError     (zero-True or zero-False pixels, D-08 fail-fast before EDT)
    ├── GeometryEnvironmentError  (FreeType version mismatch, D-28/ADR-0006)
    └── PlacementFailedError      (contract violations only — NaN SDF, dim mismatch; D-43)
```

## Decisions Made

1. **settings singleton added** — plan requires `from aerocloud.config import settings` but the module only exposed `Settings` class + `load_settings()`. Added `settings: Settings = Settings()` as a module-level singleton (Rule 2: missing critical for plan contract). All existing tests still pass.

2. **pytest-benchmark added to root dev deps** — benchmark tests will run in the workspace context where all extras are available. Added to root `[dependency-groups] dev` rather than `[geometry]` optional-deps, matching the same pattern as `hypothesis` and `pytest`.

3. **packages/engine/tests/ created as separate subtree** — plan explicitly places geometry tests under `packages/engine/tests/` (not root `tests/`). Verify commands use `cd packages/engine && uv run pytest tests/geometry/...`. The root pytest config's `testpaths = ["tests/unit", "tests/integration"]` still works for root tests; geometry tests are invoked by explicit path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `settings` module-level singleton to config.py**
- **Found during:** Task 2 (test_errors.py test 4)
- **Issue:** `from aerocloud.config import settings` failed with `ImportError` — module only had `Settings` class and `load_settings()` function. Plan's test behavior explicitly requires the singleton import.
- **Fix:** Added `settings: Settings = Settings()` below `load_settings()` with docstring
- **Files modified:** `packages/engine/src/aerocloud/config.py`
- **Verification:** Test 4 passes, `settings.sdf_cache_max_bytes == 402653184` confirmed
- **Committed in:** `654b4a3` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical singleton for plan import contract)
**Impact on plan:** Essential for test contract compliance. No scope creep.

## Issues Encountered

- `uv` binary not on default `PATH` — found at `/home/aerocloud/.local/bin/uv`, used `export PATH="$PATH:/home/aerocloud/.local/bin"` for all commands
- `cd packages/engine && uv run python -c "import cachetools..."` fails without `--extra geometry` flag; running from workspace root with `uv run` works because geometry extras were synced into the shared `.venv`

## Known Stubs

- `packages/engine/src/aerocloud/geometry/__init__.py` — Wave 0 stub: re-exports errors only. `_assert_freetype()` and `xy_to_yx()`/`yx_to_xy()` boundary adapters are intentionally absent and will land in Wave 1 (04-02-PLAN.md).

## Wiki Mirror TODO (Regel 11 — Wave 4 will do the full mirror)

The following pages must exist in `wiki/code/` after Wave 4:

| Wiki Page | Source File | When |
|-----------|-------------|------|
| `wiki/code/geometry-errors.md` | `geometry/errors.py` | Wave 4 (04-06) |
| `wiki/code/geometry-init.md` | `geometry/__init__.py` | Wave 4 (04-06) |
| `wiki/decisions/adr-0004-sdf-sign.md` | ADR-0004 | Wave 4 (04-06) |
| `wiki/decisions/adr-0005-yx.md` | ADR-0005 | Wave 4 (04-06) |
| `wiki/decisions/adr-0006-freetype.md` | ADR-0006 | Wave 4 (04-06) |
| `wiki/tests/test-errors.md` | `test_errors.py` | Wave 4 (04-06) |

## Next Phase Readiness

- Wave 1 (04-02-PLAN.md) can proceed immediately: `errors.py` is importable, geometry package stub is in place, conftest mask fixtures are available
- Wave 1 must add `_assert_freetype()` to `geometry/__init__.py` (per ADR-0006 — Wave 0 explicitly defers this)
- Wave 1 must add `xy_to_yx()` / `yx_to_xy()` boundary adapters (per ADR-0005)
- `tests/regression/glyph_golden/` is empty — Wave 2b generates `.npy` golden fixtures via `scripts/generate_glyph_golden.py`

## Self-Check: PASSED

All files exist and all commits are present in git history.

| Check | Result |
|-------|--------|
| adr-0004-sdf-sign-convention.md | FOUND |
| adr-0005-coordinate-system-yx.md | FOUND |
| adr-0006-freetype-pinning.md | FOUND |
| geometry/errors.py | FOUND |
| geometry/__init__.py | FOUND |
| config.py (modified) | FOUND |
| tests/conftest.py | FOUND |
| tests/geometry/unit/test_errors.py | FOUND |
| tests/regression/glyph_golden/.gitkeep | FOUND |
| commit 577c933 | FOUND |
| commit 654b4a3 | FOUND |
| commit 16172aa | FOUND |

---
*Phase: 04-geometry-v1*
*Completed: 2026-04-09*
