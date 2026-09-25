---
phase: 04-geometry-v1
plan: 02
plan_id: 04-02-mask-sdf
type: execute
wave: 1
depends_on: [04-01-scaffolding]
autonomous: true
requirements: [GEO-01, GEO-02, GEO-03]
files_modified:
  - packages/engine/src/aerocloud/geometry/mask.py
  - packages/engine/src/aerocloud/geometry/sdf.py
  - packages/engine/src/aerocloud/geometry/__init__.py
  - packages/engine/tests/geometry/unit/test_mask.py
  - packages/engine/tests/geometry/unit/test_sdf.py
  - packages/engine/tests/geometry/property/test_sdf_properties.py

must_haves:
  truths:
    - "mask_from_bytes() decodes PNG L/RGB/RGBA bytes to (H, W) bool ndarray"
    - "Empty or fully-filled masks raise EmptyMaskError BEFORE scipy EDT runs"
    - "compute_sdf(mask) returns float32 (H, W) with sign convention positive=inside"
    - "Circle fixture: SDF center value == radius ± 1 pixel (GEO-03)"
    - "Square fixture: SDF center value equals half the square side"
    - "SDF is finite everywhere on valid masks (no NaN, no inf)"
    - "hypothesis property test passes: sdf sign matches strict interior/exterior"
    - "aerocloud.geometry package import triggers _assert_freetype() and fails on wrong FreeType"
  artifacts:
    - path: "packages/engine/src/aerocloud/geometry/mask.py"
      provides: "mask_from_bytes(raw: bytes) -> np.ndarray[bool]"
    - path: "packages/engine/src/aerocloud/geometry/sdf.py"
      provides: "compute_sdf(mask) -> np.ndarray[float32], validate_sdf(sdf)"
    - path: "packages/engine/src/aerocloud/geometry/__init__.py"
      provides: "_assert_freetype() runtime guard + xy_to_yx / yx_to_xy adapters"
  key_links:
    - from: "geometry/mask.py"
      to: "geometry/errors.py"
      via: "EmptyMaskError, MaskFormatError imports"
      pattern: "from aerocloud.geometry.errors import"
    - from: "geometry/sdf.py"
      to: "scipy.ndimage.distance_transform_edt"
      via: "two-call EDT pattern"
      pattern: "distance_transform_edt"
    - from: "geometry/__init__.py"
      to: "PIL.features.version('freetype2')"
      via: "_assert_freetype() at import time"
      pattern: "features.version.*freetype2"
---

<objective>
Wave 1: Implement the mask decoder and SDF core. This wave produces the two
foundational files (`mask.py`, `sdf.py`) (D-02 function-based API + D-11 two-call EDT formula + D-12 no downsampling) that every later wave depends on,
plus the import-time FreeType runtime assertion and (y, x) ↔ (x, y) boundary
adapters in `geometry/__init__.py`.

Purpose: Everything downstream (cache, glyph, collision, placement) consumes
a `BoolMask` or a signed `float32` SDF. No downstream wave can proceed until
the sign convention (D-09) and coordinate system (D-14) are enforced in code.

Output: 3 production files + 3 test files, ~20-25 new green tests (unit + property dimensions of D-50 test pyramid) including
hypothesis property tests for the SDF sign invariant.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
@.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
@.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
@packages/engine/src/aerocloud/geometry/errors.py
@packages/engine/tests/conftest.py
</context>

<interfaces>
Reference code from 04-RESEARCH.md §1 mask_from_bytes, §2 compute_sdf, §4 _assert_freetype.

Target public API:
```python
# geometry/mask.py
def mask_from_bytes(raw: bytes) -> np.ndarray: ...  # bool (H, W)

# geometry/sdf.py
def compute_sdf(mask: np.ndarray) -> np.ndarray: ...  # float32 (H, W)
def validate_sdf(sdf: np.ndarray) -> None: ...  # raises PlacementFailedError on non-finite

# geometry/__init__.py
def _assert_freetype() -> None: ...  # raises GeometryEnvironmentError
def xy_to_yx(point: tuple[int, int]) -> tuple[int, int]: ...
def yx_to_xy(point: tuple[int, int]) -> tuple[int, int]: ...
```
</interfaces>

<tasks>

<task type="auto" id="04-02-T1" tdd="true">
  <name>Task 1: geometry/mask.py — Pillow decoder + empty-mask guard</name>
  <files>
    packages/engine/src/aerocloud/geometry/mask.py
    packages/engine/tests/geometry/unit/test_mask.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-04..D-08 verbatim)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §1 reference snippet
    - packages/engine/src/aerocloud/geometry/errors.py
    - packages/engine/tests/conftest.py (5 mask fixtures)
  </read_first>
  <behavior>
    - Test M1 (RED): L-mode PNG bytes → bool ndarray shape (H, W), True where pixel > 127.
    - Test M2 (RED): RGB PNG bytes → convert to luminance then threshold at 127.
    - Test M3 (RED): RGBA PNG bytes → use alpha channel (D-05), alpha > 127 = inside.
    - Test M4 (RED): JPEG bytes raise MaskFormatError (only PNG allowed in v1, D-04).
    - Test M5 (RED): All-True mask (256 bytes of 0xFF in an L-mode PNG) raises EmptyMaskError with message containing "no outside".
    - Test M6 (RED): All-False mask raises EmptyMaskError with message containing "no inside".
    - Test M7 (RED): Result ordering is (y, x) row-major per D-07/D-14 — assert `mask.shape == (H, W)` and verify a known asymmetric fixture.
    - Test M8 (RED): `circle_mask_bytes` fixture decodes to a mask with `mask.sum() > 0` and `mask.sum() < mask.size`.
    - Test M9 (RED): Threshold is EXACTLY 127 — a pixel with value 127 is OUTSIDE (`> 127`, not `>= 127`).
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_mask.py`** covering all 9 behaviors. Use existing conftest fixtures. Use `Pillow` directly to construct the test JPEG and all-True/all-False PNGs — no mocking (D-51). Example:

```python
import io
import numpy as np
import pytest
from PIL import Image
from aerocloud.geometry.errors import EmptyMaskError, MaskFormatError
from aerocloud.geometry.mask import mask_from_bytes


def _png(mask_u8: np.ndarray, mode: str = "L") -> bytes:
    img = Image.fromarray(mask_u8, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_all_true_raises_empty() -> None:
    bytes_ = _png(np.full((8, 8), 255, dtype=np.uint8))
    with pytest.raises(EmptyMaskError, match="no outside"):
        mask_from_bytes(bytes_)
```

Run `pytest tests/geometry/unit/test_mask.py -x -q` — all 9 tests MUST fail.

**Step 2 — GREEN: Implement `packages/engine/src/aerocloud/geometry/mask.py`** per 04-RESEARCH.md §1, verbatim the reference snippet:

```python
"""Mask decoder (D-04..D-08).

Accepts PNG bytes (L/RGB/RGBA) and returns a (H, W) numpy bool array with
True = inside the silhouette. Raises EmptyMaskError BEFORE any expensive
downstream work if the mask has zero True or zero False pixels (D-08).
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from aerocloud.geometry.errors import EmptyMaskError, MaskFormatError

THRESHOLD: int = 127  # D-06, locked


def mask_from_bytes(raw: bytes) -> np.ndarray:
    """Decode PNG bytes to a (H, W) bool mask. True = inside silhouette (D-07)."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise MaskFormatError(f"could not decode image bytes: {exc}") from exc

    if img.format != "PNG":
        raise MaskFormatError(f"only PNG supported in v1, got {img.format!r}")

    if img.mode == "RGBA":
        alpha = np.asarray(img.split()[3], dtype=np.uint8)
        mask = alpha > THRESHOLD
    elif img.mode == "L":
        mask = np.asarray(img, dtype=np.uint8) > THRESHOLD
    elif img.mode in ("RGB", "P"):
        mask = np.asarray(img.convert("L"), dtype=np.uint8) > THRESHOLD
    else:
        raise MaskFormatError(f"unsupported mode {img.mode!r}; expected L/RGB/RGBA")

    inside = int(mask.sum())
    if inside == 0:
        raise EmptyMaskError("mask has no inside pixels")
    if inside == mask.size:
        raise EmptyMaskError("mask has no outside pixels (fully inside)")

    return np.ascontiguousarray(mask)
```

**Step 3 — GREEN: Run tests until all 9 pass.**

**Step 4 — REFACTOR:** `mypy --strict` + `ruff check` clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_mask.py -x -q && uv run mypy --strict src/aerocloud/geometry/mask.py && uv run ruff check src/aerocloud/geometry/mask.py tests/geometry/unit/test_mask.py</automated>
  </verify>
  <acceptance_criteria>
    - `tests/geometry/unit/test_mask.py` has ≥ 9 tests all passing
    - `geometry/mask.py` contains `def mask_from_bytes(raw: bytes) -> np.ndarray`
    - `geometry/mask.py` contains `THRESHOLD = 127` as module constant
    - Empty/full mask raises `EmptyMaskError` with distinct messages
    - Non-PNG format raises `MaskFormatError`
    - mypy --strict passes on mask.py
    - ruff check passes on mask.py
    - NO mocking of Pillow in any test (D-51)
  </acceptance_criteria>
  <done>mask.py green with hermetic tests using real Pillow</done>
</task>

<task type="auto" id="04-02-T2" tdd="true">
  <name>Task 2: geometry/sdf.py — exact Meijster EDT + sign convention</name>
  <files>
    packages/engine/src/aerocloud/geometry/sdf.py
    packages/engine/tests/geometry/unit/test_sdf.py
    packages/engine/tests/geometry/property/test_sdf_properties.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-09..D-13)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §2 + §9
    - packages/engine/src/aerocloud/geometry/mask.py (from Task 1)
    - packages/engine/src/aerocloud/geometry/errors.py
  </read_first>
  <behavior>
    - Test S1 (RED): `compute_sdf(circle_mask)` returns `np.float32` (H, W).
    - Test S2 (RED): **GEO-03 circle fixture test** — for a filled circle of radius R on a HxW canvas, `sdf[center]` is within `[R - 1.0, R + 1.0]` pixels (exact Meijster tolerance).
    - Test S3 (RED): Square 40x40 — center SDF value is in `[19.5, 20.5]` (half-side minus half-pixel).
    - Test S4 (RED): Sign invariant — on a strict interior pixel (mask True + all 4-neighbors True), `sdf[y, x] > 0`. On a strict exterior pixel (mask False + all 4-neighbors False), `sdf[y, x] < 0`.
    - Test S5 (RED): `validate_sdf(sdf_with_nan)` raises `PlacementFailedError`.
    - Test S6 (RED): `validate_sdf(sdf_with_inf)` raises `PlacementFailedError`.
    - Test S7 (RED): `compute_sdf(all_true_mask)` is a guard contract violation — caller MUST pre-validate via `mask_from_bytes`. Document that `compute_sdf` assumes D-08 has already run. (Skip/xfail if test setup feeds direct all-true; this is a contract test.)
    - **Property tests** in `test_sdf_properties.py`: use hypothesis strategies per 04-RESEARCH.md §9 — `test_sdf_dtype_and_finite`, `test_sdf_sign_matches_mask`, `test_sdf_inversion_symmetry` (with `atol=1e-5`).
  </behavior>
  <action>
**Step 1 — RED: Write both test files.** Use `scipy.ndimage.distance_transform_edt` indirectly via the production code (no mocking, D-51). For the circle test, use the `circle_mask_bytes` conftest fixture → decode via `mask_from_bytes` → pass to `compute_sdf`.

Hypothesis property tests follow 04-RESEARCH.md §9 exactly — use the
`_nontrivial_mask` strategy and `@settings(deadline=2000, max_examples=200)`.

Run tests — all must be RED.

**Step 2 — GREEN: Implement `packages/engine/src/aerocloud/geometry/sdf.py`** per 04-RESEARCH.md §2:

```python
"""Signed Distance Field (D-09..D-13).

**Sign convention (locked, ADR-0004):**
- sdf > 0 inside the silhouette
- sdf == 0 on the boundary
- sdf < 0 outside the silhouette

Computed as `edt(mask) - edt(~mask)` via scipy's exact Meijster algorithm,
then cast to float32 at the public boundary (D-10). Two EDT calls; memory
temporarily doubles (float64 distance maps) — see R-2 in RESEARCH.md.
"""
from __future__ import annotations

import gc

import numpy as np
from scipy import ndimage

from aerocloud.geometry.errors import PlacementFailedError


def compute_sdf(mask: np.ndarray) -> np.ndarray:
    """Compute signed Euclidean distance field.

    Args:
        mask: shape (H, W), dtype bool. Caller must guarantee non-degenerate
            mask (D-08 / `mask_from_bytes` already enforces this).

    Returns:
        Float32 ndarray of shape (H, W), positive inside, negative outside.
    """
    if mask.dtype != np.bool_:
        raise PlacementFailedError(
            f"compute_sdf expects bool mask, got {mask.dtype}"
        )
    if mask.ndim != 2:
        raise PlacementFailedError(
            f"compute_sdf expects 2D mask, got ndim={mask.ndim}"
        )

    edt_in = ndimage.distance_transform_edt(mask)
    # Release the float64 temporary before the second EDT to cap peak RSS.
    gc.collect()
    edt_out = ndimage.distance_transform_edt(~mask)
    sdf = (edt_in - edt_out).astype(np.float32, copy=False)
    validate_sdf(sdf)
    return sdf


def validate_sdf(sdf: np.ndarray) -> None:
    """Raise PlacementFailedError on contract violation (NaN, inf, wrong dtype)."""
    if sdf.dtype != np.float32:
        raise PlacementFailedError(
            f"SDF must be float32 at boundary, got {sdf.dtype}"
        )
    if not np.isfinite(sdf).all():
        raise PlacementFailedError("SDF contains NaN or inf — contract violation")
```

**Step 3 — GREEN: Run all tests until every unit test + all 3 property tests pass.**

Note: the type stub for `scipy.ndimage.distance_transform_edt` sometimes
annotates `return_distances` as required — if mypy complains, ignore with
`# type: ignore[no-untyped-call]` ONLY on that specific call (not module-wide).

**Step 4 — REFACTOR:** mypy strict + ruff clean.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_sdf.py tests/geometry/property/test_sdf_properties.py -x -q && uv run mypy --strict src/aerocloud/geometry/sdf.py && uv run ruff check src/aerocloud/geometry/sdf.py tests/geometry/unit/test_sdf.py tests/geometry/property/test_sdf_properties.py</automated>
  </verify>
  <acceptance_criteria>
    - `geometry/sdf.py` contains `def compute_sdf(mask` and `def validate_sdf(sdf`
    - All unit tests in `test_sdf.py` pass, including circle radius-±1-pixel (GEO-03)
    - All 3 hypothesis property tests pass (dtype+finite, sign, inversion symmetry)
    - Module docstring mentions ADR-0004 and sign convention "positive inside"
    - No mocking of scipy/numpy/Pillow
    - mypy --strict passes
    - ruff check passes
  </acceptance_criteria>
  <done>SDF core + property tests green, GEO-03 circle test is the linchpin</done>
</task>

<task type="auto" id="04-02-T3" tdd="true">
  <name>Task 3: geometry/__init__.py — _assert_freetype() + (y, x) ↔ (x, y) adapters</name>
  <files>
    packages/engine/src/aerocloud/geometry/__init__.py
    packages/engine/tests/geometry/unit/test_package_init.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-14, D-15, D-28)
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §4 (FreeType pinning) and §Open Question 7 (RAQM)
    - .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
    - packages/engine/src/aerocloud/geometry/__init__.py (stub from Wave 0)
  </read_first>
  <behavior>
    - Test I1 (RED): `from aerocloud.geometry import _assert_freetype, xy_to_yx, yx_to_xy` succeeds.
    - Test I2 (RED): On the pinned Docker image, `PIL.features.version("freetype2") == "2.13.2"` and `_assert_freetype()` returns `None` without raising.
    - Test I3 (RED): **Mismatch injection via monkeypatch on `PIL.features.version`** — when the mocked value is `"2.14.2"` (Homebrew version), `_assert_freetype()` raises `GeometryEnvironmentError` whose message contains "2.14.2" and "2.13.2". This is the ONE permissible test monkeypatch in Phase 4 — we patch `PIL.features.version` not Pillow itself, because D-51 forbids mocking Pillow's decode path, not the feature-introspection API.
    - Test I4 (RED): `xy_to_yx((3, 5)) == (5, 3)` and `yx_to_xy((5, 3)) == (3, 5)`.
    - Test I5 (RED): Importing `aerocloud.geometry` triggers `_assert_freetype()` at module load (side effect). Verify by checking that a fresh `importlib.reload(aerocloud.geometry)` in a passing env does not raise.
  </behavior>
  <action>
**Step 1 — RED: Write `tests/geometry/unit/test_package_init.py`** with the 5 tests above. Use `monkeypatch.setattr("PIL.features.version", lambda feat: "2.14.2")` then force a module reload via `importlib.reload(aerocloud.geometry)`.

**Step 2 — GREEN: Rewrite `packages/engine/src/aerocloud/geometry/__init__.py`** (extending the Wave 0 stub):

```python
"""aerocloud.geometry — Phase 4 Geometry-v1 public package.

On import this module enforces the FreeType 2.13.2 runtime pin (ADR-0006 /
D-28). If the pin fails the whole geometry package refuses to load and callers
get a GeometryEnvironmentError with a documented remediation path.
"""
from __future__ import annotations

from typing import Final

from PIL import features

from aerocloud.geometry.errors import (
    EmptyMaskError,
    GeometryEnvironmentError,
    GeometryError,
    MaskFormatError,
    PlacementFailedError,
)

_EXPECTED_FREETYPE: Final[str] = "2.13.2"


def _assert_freetype() -> None:
    """Enforce D-28 / ADR-0006 at import time.

    Raises:
        GeometryEnvironmentError: If the runtime FreeType version differs from
            the pinned 2.13.2 (e.g., Homebrew Pillow ships 2.14.2).
    """
    actual = features.version("freetype2")
    if actual != _EXPECTED_FREETYPE:
        raise GeometryEnvironmentError(
            f"FreeType version mismatch: expected {_EXPECTED_FREETYPE}, got {actual}. "
            "Homebrew Pillow is explicitly unsupported for geometry generation. "
            "Use the pinned Docker image or the uv-pinned wheel. See ADR-0006."
        )


def xy_to_yx(point: tuple[int, int]) -> tuple[int, int]:
    """Convert a Pillow-style (x, y) tuple to numpy-native (y, x) (D-15)."""
    x, y = point
    return int(y), int(x)


def yx_to_xy(point: tuple[int, int]) -> tuple[int, int]:
    """Convert numpy-native (y, x) back to Pillow-style (x, y) (D-15)."""
    y, x = point
    return int(x), int(y)


# Enforce the pin at import. Subsequent imports are cached by the interpreter,
# so there is no per-call overhead.
_assert_freetype()

__all__ = [
    "EmptyMaskError",
    "GeometryEnvironmentError",
    "GeometryError",
    "MaskFormatError",
    "PlacementFailedError",
    "_assert_freetype",
    "xy_to_yx",
    "yx_to_xy",
]
```

**Step 3 — GREEN: Run tests** `pytest tests/geometry/unit/test_package_init.py -x -q`.

**Step 4 — REFACTOR:** mypy strict + ruff clean. Confirm `cd packages/engine && uv run python -c "import aerocloud.geometry"` runs silently.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_package_init.py -x -q && uv run python -c "import aerocloud.geometry; print(aerocloud.geometry._EXPECTED_FREETYPE)" && uv run mypy --strict src/aerocloud/geometry/__init__.py && uv run ruff check src/aerocloud/geometry/__init__.py</automated>
  </verify>
  <acceptance_criteria>
    - `geometry/__init__.py` exports `_assert_freetype`, `xy_to_yx`, `yx_to_xy`
    - `_EXPECTED_FREETYPE == "2.13.2"` constant present
    - Module calls `_assert_freetype()` at import time (side effect)
    - Mismatch test raises `GeometryEnvironmentError` with both versions in the message
    - `xy_to_yx` / `yx_to_xy` round-trip correctly
    - `import aerocloud.geometry` in Docker environment does not raise
    - mypy --strict clean
  </acceptance_criteria>
  <done>Geometry package guard armed, coordinate adapters wired</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User-supplied PNG bytes → mask_from_bytes | Untrusted bytes decoded by Pillow |
| Runtime env → geometry package | FreeType library version is a trust input |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-01 | DoS / Tampering | mask_from_bytes (Pillow decode) | mitigate | Wrap `Image.open` + `img.load()` in try/except; reject non-PNG via `img.format` check; D-08 empty-mask guard prevents downstream OOM. **BACKLOG:** add explicit max pixel count guard (e.g., 8192²) as a Wave 4 hardening task. |
| T-4-07 | Tampering (interpreter crash) | mask_from_bytes under hypothesis fuzz | mitigate | All exceptions caught and re-raised as `MaskFormatError(GeometryError)` — never propagate raw `OSError` / `ValueError`. Hypothesis fuzz test in Wave 4 validates. |
| T-4-F1 | Spoofing | FreeType version drift (Homebrew 2.14.2) | mitigate | `_assert_freetype()` enforces `PIL.features.version("freetype2") == "2.13.2"` at import time. Test I3 verifies the failure mode. |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry/unit tests/geometry/property -x -q` exits 0
- `uv run mypy --strict src/aerocloud/geometry/` exits 0
- `uv run ruff check src/aerocloud/geometry/ tests/geometry/` exits 0
- `uv run python -c "from aerocloud.geometry.mask import mask_from_bytes; from aerocloud.geometry.sdf import compute_sdf, validate_sdf; from aerocloud.geometry import _assert_freetype, xy_to_yx, yx_to_xy"` exits 0
- GEO-03 circle test (`test_sdf_circle_center_radius`) green
</verification>

<success_criteria>
1. `mask_from_bytes` handles L/RGB/RGBA PNGs, rejects JPEG, raises `EmptyMaskError` on degenerate masks
2. `compute_sdf` returns float32 signed with positive=inside
3. GEO-03 satisfied: circle SDF center = radius ± 1 px
4. hypothesis property tests green over 200 examples each
5. `_assert_freetype()` fires at package import
6. `xy_to_yx` / `yx_to_xy` adapters implemented
7. ~20-25 new tests, all green
8. mypy --strict + ruff clean across Wave 1 files
</success_criteria>

<output>
After completion, create `.planning/phases/04-geometry-v1/04-02-SUMMARY.md` with:
- Files created (mask.py, sdf.py, __init__.py + 3 test files)
- Test count added (~20-25)
- Any property test flakiness observed
- Wave 2 unblocked: sdf_cache + glyph can begin in parallel
</output>
