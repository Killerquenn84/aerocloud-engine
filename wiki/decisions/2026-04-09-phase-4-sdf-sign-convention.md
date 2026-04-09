# Decision Mirror: ADR-0004 SDF Sign Convention

**Canonical source:** `.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md`
**Date:** 2026-04-09 (mirrored from ADR accepted 2026-04-10)
**Phase:** 04-geometry-v1

> This is a wiki mirror for `wiki:query` discoverability. The canonical ADR is
> the source of truth. Update the ADR first; then re-mirror here.

---

# ADR-0004: SDF Sign Convention (positive=inside)

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

The SDF maps each pixel to its signed Euclidean distance from the nearest boundary.
Two sign conventions exist in the literature:

- **positive=inside:** interior pixels carry a positive distance value
- **negative=inside:** interior pixels carry a negative value (common in ray-marching/OpenGL)

The AeroCloud Phase 6 Inner Loop uses the SDF as a shape-suck signal for the Adam
optimizer. With positive=inside, word placements move toward positive gradient (the
interior) without negation — the mathematically natural direction.

Codex g-3 blocked `int16` quantization: it causes staircasing in the SDF gradient that
biases Phase 6 Adam toward staircase artifacts. dtype must be `float32` at the public
boundary (D-10).

## Decision

**`sdf > 0 inside, sdf == 0 on boundary, sdf < 0 outside`. This is UNCHANGEABLE.**

Implementation formula (D-11):
```python
sdf = (
    scipy.ndimage.distance_transform_edt(mask).astype(np.float32)
    - scipy.ndimage.distance_transform_edt(~mask).astype(np.float32)
)
```

Enforced by `geometry/sdf.py::validate_sdf()` at every `compute_sdf()` call.

## Blocked alternatives

- `int16` quantization — Adam gradient staircasing (Codex g-3)
- `float16` — insufficient precision for sub-pixel interior gradients
- negative=inside — would require negation at every consumer site
- Any quantization that downcasts float32 outputs

## Cache key impact

The sign convention appears in the cache key as `("sign", "positive_inside")` (D-20),
ensuring a hypothetical future convention change causes a cache miss rather than
returning a stale entry.

## References

- `.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md` — canonical ADR
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-09, D-10, D-11
- `wiki/code/geometry-sdf.md`
