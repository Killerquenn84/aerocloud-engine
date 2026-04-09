# geometry/mask.py

**Module:** `aerocloud.geometry.mask`
**Phase:** 04-geometry-v1
**Decisions:** D-04, D-05, D-06, D-07, D-08
**ADRs:** (none specific — documented in 04-CONTEXT.md)

## Purpose

Decodes raw PNG bytes into a `(H, W)` boolean NumPy mask where `True` = inside
the silhouette. Enforces D-04 (PNG-only in v1), D-05 (alpha channel priority),
D-06 (threshold=127), and D-07 (bool dtype, (y, x) row-major order). Raises
`EmptyMaskError` fail-fast before any SDF allocation if the mask has zero `True`
or zero `False` pixels (D-08).

## Public API

```python
THRESHOLD: int = 127  # D-06, locked

def mask_from_bytes(raw: bytes) -> np.ndarray:
    """Decode PNG bytes to (H, W) bool mask. True = inside silhouette (D-07).

    Supported modes: L (greyscale), RGB, RGBA, P (palette → converted to L).
    RGBA: uses alpha channel as silhouette (D-05).
    L / RGB / P: threshold at THRESHOLD (D-06).

    Raises:
        MaskFormatError: not a valid PNG, or unsupported mode
        EmptyMaskError:  zero True pixels OR zero False pixels (D-08)
    """
```

## Key invariants

- Output dtype is always `bool`, shape `(H, W)` in (y, x) row-major order (D-14).
- JPEG, WebP, SVG are not accepted in v1 (D-04).
- `THRESHOLD = 127` is a module constant — never adaptive (D-06).
- `EmptyMaskError` is raised before SDF allocation to prevent silent EDT failure.

## Dependencies

- `Pillow` (Image.open, Image.split, Image.convert)
- `numpy`
- `aerocloud.geometry.errors` (MaskFormatError, EmptyMaskError)

## Tests

- `tests/geometry/unit/test_mask.py` — all decode modes, threshold edge cases, empty mask
- `tests/geometry/security/test_mask_fuzz.py` — hypothesis 200 examples (Nyquist dim 7)
- `tests/geometry/integration/test_pipeline.py` — end-to-end fixture usage

## Related

- `wiki/code/geometry-sdf.md` — consumes the bool mask output
- `wiki/code/geometry-errors.md` — error types raised here
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-04 through D-08
