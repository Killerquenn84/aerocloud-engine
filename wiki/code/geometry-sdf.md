# geometry/sdf.py

**Module:** `aerocloud.geometry.sdf`
**Phase:** 04-geometry-v1
**Decisions:** D-09, D-10, D-11, D-12, D-13
**ADRs:** ADR-0004 (sign convention — UNCHANGEABLE)

## Purpose

Computes a signed Euclidean Distance Field from a boolean mask using two scipy
EDT calls. The sign convention is locked by ADR-0004: `sdf > 0 inside`,
`sdf == 0 on boundary`, `sdf < 0 outside`. Phase 5 (Renderer) and Phase 6
(Inner Loop / Adam) consume this SDF directly without sign inversion.

## Public API

```python
def compute_sdf(mask: np.ndarray) -> np.ndarray:
    """Compute signed EDT. Result is float32 (H, W), positive inside (D-09/D-11).

    Formula: edt(mask) - edt(~mask)   [scipy exact Meijster algorithm]

    Raises:
        PlacementFailedError: wrong dtype, wrong ndim, or NaN/inf in result
    """

def validate_sdf(sdf: np.ndarray) -> None:
    """Assert sdf is float32 and finite everywhere. Raises PlacementFailedError."""
```

## Key invariants

- `sdf > 0` inside the silhouette, `sdf < 0` outside (ADR-0004 — UNCHANGEABLE).
- Output dtype is `float32` at the public boundary; internal scipy work is float64
  then cast (D-10). `int16` and `float16` are both blocked.
- No downsampling (D-12); resolution = input resolution.
- `gc.collect()` is called between the two EDT calls to cap peak RSS (D-11, R-2).

## Dependencies

- `scipy.ndimage.distance_transform_edt`
- `numpy`
- `aerocloud.geometry.errors` (PlacementFailedError)

## Tests

- `tests/geometry/unit/test_sdf.py` — sign convention, dtype, circle/square correctness
- `tests/geometry/property/test_sdf_properties.py` — hypothesis: sign(sdf) == 2*mask-1
- `tests/geometry/performance/test_sdf_benchmark.py` — 2048x2048 < 1.0 s (Nyquist dim 8)

## Performance notes

Two EDT calls on a 2048x2048 mask: ~0.4–0.8 s on a single CPU core (RESEARCH.md §12 R-4).
Peak RSS doubles temporarily (two float64 arrays). gc.collect() releases edt_in before
allocating edt_out to constrain peak usage.

## Related

- `wiki/code/geometry-sdf-cache.md` — caches compute_sdf output
- `wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md` — ADR-0004 mirror
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-09 through D-13
