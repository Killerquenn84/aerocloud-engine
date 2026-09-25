---
phase: 04-geometry-v1
plan: 01
plan_id: 04-01-scaffolding
type: execute
wave: 0
depends_on: []
autonomous: true
requirements: [GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07]
files_modified:
  - .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
  - .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
  - .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
  - packages/engine/src/aerocloud/geometry/__init__.py
  - packages/engine/src/aerocloud/geometry/errors.py
  - packages/engine/src/aerocloud/config.py
  - packages/engine/pyproject.toml
  - packages/engine/tests/geometry/__init__.py
  - packages/engine/tests/geometry/unit/__init__.py
  - packages/engine/tests/geometry/integration/__init__.py
  - packages/engine/tests/geometry/property/__init__.py
  - packages/engine/tests/geometry/state/__init__.py
  - packages/engine/tests/geometry/determinism/__init__.py
  - packages/engine/tests/geometry/security/__init__.py
  - packages/engine/tests/geometry/performance/__init__.py
  - packages/engine/tests/regression/glyph_golden/.gitkeep
  - packages/engine/tests/conftest.py

must_haves:
  truths:
    - "adr-0004/0005/0006 exist and are citeable from production code"
    - "`from aerocloud.geometry.errors import EmptyMaskError, MaskFormatError, GeometryEnvironmentError, PlacementFailedError, GeometryError` succeeds"
    - "cachetools>=7.0.0 and blake3>=1.0.0 are in pyproject.toml [project.optional-dependencies] geometry"
    - "`uv sync --extra geometry` installs blake3 and cachetools"
    - "`settings.sdf_cache_max_bytes` is available with default 402653184 (384 MiB)"
    - "tests/geometry subtree exists with 7 sub-packages and all glyph_golden/ directory present"
    - "conftest.py exposes circle_mask_bytes, square_mask_bytes, c_shape_mask_bytes, crescent_mask_bytes, tiny_mask_bytes fixtures"
  artifacts:
    - path: ".planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md"
      provides: "SDF sign convention lock (positive=inside)"
    - path: ".planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md"
      provides: "(y, x) canonical ordering lock"
    - path: ".planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md"
      provides: "FreeType 2.13.2 runtime assertion lock"
    - path: "packages/engine/src/aerocloud/geometry/errors.py"
      provides: "GeometryError + EmptyMaskError + MaskFormatError + GeometryEnvironmentError + PlacementFailedError"
    - path: "packages/engine/tests/conftest.py"
      provides: "shared mask fixtures for all geometry tests"
  key_links:
    - from: "packages/engine/src/aerocloud/config.py"
      to: "sdf_cache (Wave 2a)"
      via: "settings.sdf_cache_max_bytes"
      pattern: "sdf_cache_max_bytes"
    - from: "packages/engine/pyproject.toml"
      to: "geometry runtime"
      via: "cachetools + blake3 deps"
      pattern: "cachetools|blake3"
---

<objective>
Wave 0: Lay down the immovable scaffolding. Commit the three ADRs that lock
D-09 / D-14 / D-28, create the `geometry/errors.py` error hierarchy, add
`cachetools>=7.0.0` + `blake3>=1.0.0` to `[geometry]` optional deps, extend the
Pydantic `Settings` loader with `sdf_cache_max_bytes`, create the full
`tests/geometry/` sub-tree with `conftest.py` fixtures, and commit the
`tests/regression/glyph_golden/` directory.

Purpose: Every downstream wave depends on these files. Without them, no wave
can even import correctly. This wave is serial and blocks everything else.

Output: ADRs committed, errors module importable, deps installed, test
scaffolding present.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/04-VALIDATION.md
@packages/engine/pyproject.toml
@packages/engine/src/aerocloud/config.py
@packages/engine/src/aerocloud/nlp/tokenize.py
</context>

<interfaces>
From packages/engine/src/aerocloud/nlp/tokenize.py (RLock registry template):
```python
import threading
_registry: dict[str, Any] = {}
_registry_lock = threading.RLock()

class MissingSpacyModelError(RuntimeError): ...
```

Error class hierarchy to create (per CONTEXT.md D-08, D-28, D-43):
```python
class GeometryError(Exception): ...
class MaskFormatError(GeometryError): ...
class EmptyMaskError(GeometryError): ...
class GeometryEnvironmentError(GeometryError): ...
class PlacementFailedError(GeometryError): ...
```
</interfaces>

<tasks>

<task type="auto" id="04-01-T1">
  <name>Task 1: Write ADR-0004, ADR-0005, ADR-0006 lock files</name>
  <files>
    .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
    .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
    .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-09, D-14, D-28 verbatim)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §2, §4
  </read_first>
  <action>
Create three markdown ADR files. Each must follow the structure:
```
# ADR-NNNN: <title>
Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context
## Decision
## Consequences
## Enforcement
## References
```

**ADR-0004 (sdf-sign-convention):** Copy D-09 verbatim into Decision:
"sdf > 0 inside, sdf == 0 on boundary, sdf < 0 outside. UNCHANGEABLE." State
that int16 quantization is BLOCKED (Codex g-3) and dtype is float32 at the
boundary (D-10). Enforcement: `validate_sdf()` runtime assertion in
`geometry/sdf.py`. Reference Codex g-3 findings file + 04-CONTEXT.md D-09.

**ADR-0005 (coordinate-system-yx):** Copy D-14/D-15/D-16. Decision: "(y, x) is
canonical internally; (x, y) only at the Pydantic boundary via `xy_to_yx()` /
`yx_to_xy()` adapters in `geometry/__init__.py`. AABB Pydantic model uses
`y_min, x_min, y_max, x_max` NOT `left, top, right, bottom`." Enforcement:
Pydantic validators + unit tests on boundary adapters. Reference 04-CONTEXT.md
D-14..D-16.

**ADR-0006 (freetype-pinning):** Copy D-28/D-30. Decision:
`_EXPECTED_FREETYPE = "2.13.2"` asserted via `PIL.features.version("freetype2")`
at `aerocloud.geometry` package import. Homebrew Pillow is explicitly
unsupported (Homebrew ships FreeType 2.14.2). CI matrix runs on Docker only for
the geometry test job. `freetype.__version__` is NOT used — only
`PIL.features.version("freetype2")`. Reference Codex g-4 findings file +
04-CONTEXT.md D-28 + https://pillow.readthedocs.io/en/stable/reference/features.html
  </action>
  <verify>
    <automated>test -f .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md && test -f .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md && test -f .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md && grep -q "positive_inside\|positive=inside\|sdf > 0 inside" .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md && grep -q "y_min" .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md && grep -q "2.13.2" .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md</automated>
  </verify>
  <acceptance_criteria>
    - All three ADR files exist
    - adr-0004 contains the phrase "sdf > 0 inside" or "positive=inside"
    - adr-0005 contains "y_min" (AABB field naming)
    - adr-0006 contains "2.13.2" and "PIL.features.version"
  </acceptance_criteria>
  <done>Three ADR markdown files committed to .planning/phases/04-geometry-v1/</done>
</task>

<task type="auto" id="04-01-T2" tdd="true">
  <name>Task 2: Create geometry/errors.py + geometry/__init__.py skeleton + extend config.py with sdf_cache_max_bytes</name>
  <files>
    packages/engine/src/aerocloud/geometry/__init__.py
    packages/engine/src/aerocloud/geometry/errors.py
    packages/engine/src/aerocloud/config.py
    packages/engine/tests/geometry/unit/test_errors.py
  </files>
  <read_first>
    - packages/engine/src/aerocloud/geometry/__init__.py (currently empty or missing)
    - packages/engine/src/aerocloud/config.py (to extend Settings)
    - packages/engine/src/aerocloud/nlp/tokenize.py (RLock registry template)
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-01, D-08, D-18, D-28, D-43)
  </read_first>
  <behavior>
    - Test 1 (RED): `from aerocloud.geometry.errors import GeometryError, EmptyMaskError, MaskFormatError, GeometryEnvironmentError, PlacementFailedError` succeeds.
    - Test 2 (RED): `EmptyMaskError("msg")` is an instance of `GeometryError` and `Exception`.
    - Test 3 (RED): `MaskFormatError`, `GeometryEnvironmentError`, `PlacementFailedError` all subclass `GeometryError`.
    - Test 4 (RED): `from aerocloud.config import settings; isinstance(settings.sdf_cache_max_bytes, int) and settings.sdf_cache_max_bytes == 402653184` (384 MiB default).
    - Test 5: `from aerocloud.geometry import __init__` does NOT yet call `_assert_freetype()` — that is Wave 1 (only declare the import structure now; the stub raises NotImplementedError if invoked in Wave 0).
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_errors.py`** with the 5 behaviors above.

**Step 2 — GREEN: Create `packages/engine/src/aerocloud/geometry/errors.py`** per D-08 / D-28 / D-43:

```python
"""Typed error hierarchy for the geometry package.

All errors derive from `GeometryError`. Downstream Phase 5 (Renderer) and
Phase 6 (Inner Loop) pattern-match on `GeometryError` subclasses rather than
parsing log messages.
"""
from __future__ import annotations


class GeometryError(Exception):
    """Base class for all aerocloud.geometry exceptions."""


class MaskFormatError(GeometryError):
    """Raised when a mask input does not conform to the v1 PNG contract (D-04)."""


class EmptyMaskError(GeometryError):
    """Raised when a decoded mask has zero True OR zero False pixels (D-08).

    This is a fail-fast guard BEFORE scipy EDT allocation.
    """


class GeometryEnvironmentError(GeometryError):
    """Raised when the runtime environment violates a locked assumption (D-28).

    Currently covers: FreeType version mismatch (Homebrew Pillow drift).
    """


class PlacementFailedError(GeometryError):
    """Raised ONLY on placement contract violations (D-43).

    Examples: NaN/non-finite SDF, dimension mismatch between mask and glyph
    buffer, negative budgets, internal invariant failure. An *ordinary*
    unplaceable word is NEVER an exception — it goes into
    `PlacementResult.dropped_words` with a `DropReason`.
    """
```

**Step 3 — GREEN: Create `packages/engine/src/aerocloud/geometry/__init__.py`** as a minimal stub:

```python
"""aerocloud.geometry — Phase 4 Geometry-v1.

Wave 0 stub: exposes error types only. `_assert_freetype()` and the (y, x)
boundary adapters land in Wave 1.
"""
from __future__ import annotations

from aerocloud.geometry.errors import (
    EmptyMaskError,
    GeometryEnvironmentError,
    GeometryError,
    MaskFormatError,
    PlacementFailedError,
)

__all__ = [
    "EmptyMaskError",
    "GeometryEnvironmentError",
    "GeometryError",
    "MaskFormatError",
    "PlacementFailedError",
]
```

**Step 4 — GREEN: Extend `packages/engine/src/aerocloud/config.py` Settings** by
adding a new field (keep existing fields; do NOT reorder):

```python
# Geometry cache budget (Phase 4 D-18). 384 MiB = 402653184 bytes.
sdf_cache_max_bytes: int = Field(
    default=402_653_184,
    description="Per-worker bytes budget for the SDF LRU cache (D-18).",
    ge=1_048_576,  # minimum 1 MiB sanity floor
)
```

Use the exact `pydantic_settings` / `Field` import pattern already in the file;
do not rewrite the imports.

**Step 5 — GREEN: Run `cd packages/engine && uv run pytest tests/geometry/unit/test_errors.py -x -q`** and confirm all 5 tests pass.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_errors.py -x -q && uv run python -c "from aerocloud.geometry.errors import GeometryError, EmptyMaskError, MaskFormatError, GeometryEnvironmentError, PlacementFailedError; assert issubclass(EmptyMaskError, GeometryError); from aerocloud.config import settings; assert settings.sdf_cache_max_bytes == 402653184"</automated>
  </verify>
  <acceptance_criteria>
    - `packages/engine/src/aerocloud/geometry/errors.py` exists and defines all 5 error classes
    - `packages/engine/src/aerocloud/geometry/__init__.py` re-exports all 5
    - `settings.sdf_cache_max_bytes == 402653184`
    - `tests/geometry/unit/test_errors.py` passes
    - `ruff check packages/engine/src/aerocloud/geometry/` exits 0
    - `mypy --strict packages/engine/src/aerocloud/geometry/` exits 0
  </acceptance_criteria>
  <done>Error module + config field + first green test committed</done>
</task>

<task type="auto" id="04-01-T3">
  <name>Task 3: Add cachetools + blake3 to pyproject [geometry], create test subtree, conftest fixtures, pytest-benchmark verification</name>
  <files>
    packages/engine/pyproject.toml
    packages/engine/tests/geometry/__init__.py
    packages/engine/tests/geometry/unit/__init__.py
    packages/engine/tests/geometry/integration/__init__.py
    packages/engine/tests/geometry/property/__init__.py
    packages/engine/tests/geometry/state/__init__.py
    packages/engine/tests/geometry/determinism/__init__.py
    packages/engine/tests/geometry/security/__init__.py
    packages/engine/tests/geometry/performance/__init__.py
    packages/engine/tests/regression/glyph_golden/.gitkeep
    packages/engine/tests/conftest.py
  </files>
  <read_first>
    - packages/engine/pyproject.toml (current [geometry] extra at line 33)
    - packages/engine/tests/conftest.py (existing fixtures — extend, do not replace)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §Standard Stack (verified versions 2026-04-09)
    - .planning/phases/04-geometry-v1/04-VALIDATION.md §Wave 0 Requirements
  </read_first>
  <action>
**Step 1 — Edit `packages/engine/pyproject.toml`**. In the existing `[project.optional-dependencies]` block, append to `geometry = [...]`:
```toml
    "cachetools>=7.0.0",  # Phase 4 D-17: bytes-bounded LRU cache
    "blake3>=1.0.0",      # Phase 4 D-21: strong content digest for cache key
```

**Step 2 — Verify `pytest-benchmark` presence.** Run
`cd packages/engine && uv run python -c "import pytest_benchmark; print(pytest_benchmark.__version__)"`.
If this exits non-zero, add `"pytest-benchmark>=4.0.0"` to the dev/test deps
group used by the engine (check `[tool.uv]` `dev-dependencies` or a `[dependency-groups]` section in the root pyproject). Document the choice inline
in a comment.

**Step 3 — Run `uv sync --extra geometry`** at repo root. Confirm blake3 and
cachetools install cleanly.

**Step 4 — Create test subtree.** For each of the 7 subdirs under
`packages/engine/tests/geometry/` (`unit`, `integration`, `property`, `state`,
`determinism`, `security`, `performance`) create an empty `__init__.py` with
a one-line docstring. Also create `tests/geometry/__init__.py`. Create
`tests/regression/glyph_golden/.gitkeep` so the empty directory is tracked.

**Step 5 — Extend `tests/conftest.py`** with mask fixtures. Read the existing
file first; then APPEND (do not overwrite existing fixtures):

```python
import io
import numpy as np
import pytest
from PIL import Image


def _png_bytes_from_bool_mask(mask: np.ndarray) -> bytes:
    """Encode a (H, W) bool mask as an L-mode PNG bytes payload."""
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def circle_mask_bytes() -> bytes:
    """64x64 filled circle, radius 24, center (32, 32)."""
    y, x = np.ogrid[:64, :64]
    mask = (y - 32) ** 2 + (x - 32) ** 2 <= 24 ** 2
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def square_mask_bytes() -> bytes:
    """64x64 filled square, 40x40 centered."""
    mask = np.zeros((64, 64), dtype=bool)
    mask[12:52, 12:52] = True
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def c_shape_mask_bytes() -> bytes:
    """64x64 concave C-shape (square with notch)."""
    mask = np.zeros((64, 64), dtype=bool)
    mask[8:56, 8:56] = True
    mask[20:44, 32:56] = False  # notch on right side
    return _png_bytes_from_bool_mask(mask)


@pytest.fixture()
def crescent_mask_bytes() -> bytes:
    """64x64 concave crescent (difference of two circles)."""
    y, x = np.ogrid[:64, :64]
    outer = (y - 32) ** 2 + (x - 32) ** 2 <= 24 ** 2
    inner = (y - 32) ** 2 + (x - 40) ** 2 <= 18 ** 2
    return _png_bytes_from_bool_mask(outer & ~inner)


@pytest.fixture()
def tiny_mask_bytes() -> bytes:
    """4x4 with a single True pixel — edge of empty-mask guard."""
    mask = np.zeros((4, 4), dtype=bool)
    mask[2, 2] = True
    return _png_bytes_from_bool_mask(mask)
```

**Step 6 — Verify.** Run
`cd packages/engine && uv run pytest tests/geometry/unit/test_errors.py -x -q --collect-only`
and
`cd packages/engine && uv run python -c "import cachetools, blake3; print(cachetools.__version__, blake3.__version__)"`.
  </action>
  <verify>
    <automated>cd packages/engine && uv run python -c "import cachetools, blake3, pytest_benchmark" && uv run pytest tests/geometry/unit/test_errors.py -x -q && test -f tests/regression/glyph_golden/.gitkeep && test -f tests/geometry/__init__.py && test -f tests/geometry/performance/__init__.py</automated>
  </verify>
  <acceptance_criteria>
    - `pyproject.toml [geometry]` contains both `cachetools>=7.0.0` and `blake3>=1.0.0`
    - `import cachetools, blake3, pytest_benchmark` all succeed in the engine env
    - All 7 `tests/geometry/*/` subdirs have `__init__.py`
    - `tests/regression/glyph_golden/.gitkeep` exists
    - `tests/conftest.py` defines 5 fixtures: `circle_mask_bytes`, `square_mask_bytes`, `c_shape_mask_bytes`, `crescent_mask_bytes`, `tiny_mask_bytes`
    - pytest collects `tests/geometry/unit/test_errors.py` without collection errors
  </acceptance_criteria>
  <done>Dependencies installed, fixtures available, test subtree ready for Wave 1</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pyproject deps → engine runtime | New deps (blake3, cachetools) enter the supply chain |
| config.py → runtime | New tunable `sdf_cache_max_bytes` is operator-controllable |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-02 | Tampering/Repudiation | blake3 availability downgrade to sha256 | mitigate | Explicit `import blake3` smoke test in Task 3; both paths tested in Wave 2a; CI verifies blake3 is importable |
| T-4-W0-01 | DoS (resource exhaustion) | `sdf_cache_max_bytes` operator override | mitigate | `Field(default=402_653_184, ge=1_048_576)` enforces a 1 MiB floor so a typo cannot set budget to 0 |
| T-4-W0-02 | Supply-chain tampering | new deps cachetools + blake3 | accept | uv lockfile + version floors; Phase 12 adds full supply-chain audit |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry -x -q` exits 0 (only test_errors.py runs)
- `cd packages/engine && uv run mypy --strict src/aerocloud/geometry/` exits 0
- `cd packages/engine && uv run ruff check src/aerocloud/geometry/ tests/geometry/` exits 0
- `uv run python -c "import cachetools, blake3, pytest_benchmark"` exits 0
- `uv run python -c "from aerocloud.config import settings; assert settings.sdf_cache_max_bytes == 402653184"` exits 0
- All three ADR files committed
</verification>

<success_criteria>
1. Three ADR files (0004/0005/0006) exist and are referenced from CONTEXT.md
2. `aerocloud.geometry.errors` module importable with 5 exception classes
3. `settings.sdf_cache_max_bytes` exists with 384 MiB default
4. `cachetools>=7.0.0` + `blake3>=1.0.0` installed via `uv sync --extra geometry`
5. `pytest-benchmark` importable
6. Full `tests/geometry/` subtree (7 subdirs) + `tests/regression/glyph_golden/` directory present
7. 5 mask fixtures in `tests/conftest.py`
8. First green test (`test_errors.py`) runs
</success_criteria>

<output>
After completion, create `.planning/phases/04-geometry-v1/04-01-SUMMARY.md` listing:
- ADR files committed
- Error class hierarchy tree
- New pyproject.toml deps
- New conftest fixtures
- Any Wave 0 gaps still open (e.g., pytest-benchmark already present vs newly added)
</output>
