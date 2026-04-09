# Decision Mirror: ADR-0005 Coordinate System (y, x) Canonical

**Canonical source:** `.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md`
**Date:** 2026-04-09 (mirrored from ADR accepted 2026-04-10)
**Phase:** 04-geometry-v1

> This is a wiki mirror for `wiki:query` discoverability. The canonical ADR is
> the source of truth. Update the ADR first; then re-mirror here.

---

# ADR-0005: Coordinate System — (y, x) Canonical Internally

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

NumPy arrays are row-major: `arr[y, x]` is the natural indexing convention.
Pillow uses `(x, y)` / `(left, top, right, bottom)` matching traditional screen
coordinates. Mixing these causes silent, hard-to-debug transposition bugs in the
placement loop.

## Decision

**(y, x) is canonical internally. (x, y) accepted only at the Pydantic boundary.**

### D-14: Internal convention

Every internal function takes and returns `(y, x)` tuples. Every NumPy array
index is `arr[y, x]`. Files inside `geometry/` MUST NOT use `(x, y)` ordering.

### D-15: Boundary adapters in geometry/__init__.py

```python
def xy_to_yx(x: int, y: int) -> tuple[int, int]: return (y, x)
def yx_to_xy(y: int, x: int) -> tuple[int, int]: return (x, y)
```

### D-16: AABB field names

```python
class AABB(AeroCloudBase):
    y_min: int; x_min: int; y_max: int; x_max: int
```

Pillow-style `(left, top, right, bottom)` naming is NEVER used in internal models.

## Consequences

- All internal geometry uses `arr[y, x]` without translation overhead.
- External callers (Phase 5, Phase 6) receive `(x, y)` Pydantic models via adapters.
- AABB serialization produces `{"y_min": ..., "x_min": ..., ...}` — unambiguous.

## References

- `.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md` — canonical ADR
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-14, D-15, D-16
- `wiki/code/geometry-collision.md`
- `wiki/code/geometry-placement.md`
