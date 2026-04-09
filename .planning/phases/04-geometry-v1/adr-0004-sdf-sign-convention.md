# ADR-0004: SDF Sign Convention (positive=inside)

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

The Signed Distance Field (SDF) maps each pixel to its signed Euclidean distance from the
nearest boundary. Two sign conventions are used in the literature:

- **positive=inside:** pixels inside the silhouette carry a positive distance value
- **negative=inside:** pixels inside the silhouette carry a negative distance value (common
  in ray-marching / OpenGL toolchains)

The AeroCloud Blueprint specifies that the SDF is used as a **shape-suck signal** in the
Phase 6 Inner Loop: the Adam optimizer moves word placements toward positive gradient.
Using positive=inside means a word placement optimizer can follow the SDF gradient directly
toward the interior without negating it, which is the mathematically natural direction.

Codex adversarial review (codex-g3.md) explicitly BLOCKED `int16` quantization of the SDF:
quantization causes staircasing in the SDF gradient that biases the Phase 6 Adam optimizer
toward staircase artifacts. The dtype must be `float32` at the public boundary (D-10).

## Decision

**`sdf > 0 inside, sdf == 0 on boundary, sdf < 0 outside`. This is UNCHANGEABLE.**

Formally:

```
SDF(p) > 0  ↔  p is strictly inside the silhouette
SDF(p) = 0  ↔  p is on the silhouette boundary
SDF(p) < 0  ↔  p is strictly outside the silhouette
```

Implementation formula (D-11):

```python
sdf = (
    scipy.ndimage.distance_transform_edt(mask).astype(np.float32)
    - scipy.ndimage.distance_transform_edt(~mask).astype(np.float32)
)
```

This is enforced by a runtime assertion in `geometry/sdf.py::validate_sdf()`:

```python
def validate_sdf(sdf: np.ndarray, mask: np.ndarray) -> None:
    """Enforce D-09 sign invariant. Called at every public SDF construction path."""
    inside = mask.astype(bool)
    if inside.any():
        assert sdf[inside].min() >= 0.0, "SDF interior pixel is negative (sign violation)"
    outside = ~inside
    if outside.any():
        assert sdf[outside].max() <= 0.0, "SDF exterior pixel is positive (sign violation)"
```

**Blocked alternatives:**

- `int16` quantization is BLOCKED — causes Adam gradient staircasing (Codex g-3)
- `float16` is BLOCKED — insufficient precision for sub-pixel interior gradients
- negative=inside convention is BLOCKED — would require negation at every consumer site

## Consequences

- Phase 5 Renderer-v1 and Phase 6 Inner Loop can consume the SDF directly without sign
  inversion or clamping
- Any code that negates the SDF before using it is incorrect
- The sign convention is visible in the cache key (D-20): `("sign", "positive_inside")`
  ensures that any hypothetical future version with a different convention produces a
  cache miss rather than a stale hit
- `float32` dtype (not `float16` or `int16`) is the only allowed public representation

## Enforcement

- `geometry/sdf.py::validate_sdf()` — runtime assertion on every `compute_sdf()` call
- `tests/geometry/unit/test_sdf.py::test_sign_convention_circle` — verifies SDF center
  of a circle equals `radius ± 1 px` and all interior pixels are positive
- `tests/geometry/property/test_sdf_properties.py` — hypothesis property test: random
  masks → non-NaN float32 SDF with `sign(sdf) == (2*mask-1)` at non-boundary pixels
- ADR referenced in `geometry/sdf.py` module docstring: "See ADR-0004"

## References

- `.planning/phases/04-geometry-v1/04-CONTEXT.md` D-09, D-10, D-11
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md` — int16 quantization BLOCKED
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html
- AeroCloud Blueprint Teil III §"Shape Analysis — The Skeleton"
