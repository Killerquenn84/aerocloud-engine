# geometry/errors.py

**Module:** `aerocloud.geometry.errors`
**Phase:** 04-geometry-v1
**Decisions:** D-08, D-28, D-43
**ADRs:** ADR-0006

## Purpose

Typed exception hierarchy for the geometry package. All geometry errors derive
from `GeometryError` so Phase 5 (Renderer) and Phase 6 (Inner Loop) can catch
them with a single `except GeometryError` clause rather than parsing log messages.

## Public API

```python
class GeometryError(Exception): ...
class MaskFormatError(GeometryError): ...   # D-04: invalid PNG or unsupported mode
class EmptyMaskError(GeometryError): ...    # D-08: zero True OR zero False pixels
class GeometryEnvironmentError(GeometryError): ...  # D-28: FreeType version mismatch
class PlacementFailedError(GeometryError): ...      # D-43: contract violation only
```

## Key invariants

- `EmptyMaskError` is raised **before** any SDF allocation (D-08 fail-fast).
- `PlacementFailedError` is raised **only** for internal contract violations
  (NaN/inf SDF, dimension mismatch). An ordinary unplaceable word is NOT an
  exception — it goes into `PlacementResult.dropped_words` with a `DropReason`.
- `GeometryEnvironmentError` fires at import time when FreeType version mismatches
  the pin `"2.13.2"` (see ADR-0006). Bypass via `AEROCLOUD_SKIP_FREETYPE_CHECK=1`.

## Error modes

This module IS the error mode definition for the geometry package.

## Performance notes

No performance considerations — this is a pure data hierarchy.

## Related

- `wiki/code/geometry-mask.md` — raises `MaskFormatError`, `EmptyMaskError`
- `wiki/code/geometry-sdf.md` — raises `PlacementFailedError` on NaN SDF
- `wiki/code/geometry-placement.md` — raises `PlacementFailedError` on contract violation
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-08, D-28, D-43
