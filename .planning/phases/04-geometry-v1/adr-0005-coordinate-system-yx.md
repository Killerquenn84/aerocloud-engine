# ADR-0005: Coordinate System — (y, x) Canonical Internally

Status: Accepted 2026-04-10
Phase: 04-geometry-v1

## Context

NumPy arrays are row-major (C order): the first axis is rows (vertical / `y`), the second
axis is columns (horizontal / `x`). This means `arr[y, x]` is the natural NumPy indexing
convention.

Pillow, on the other hand, uses `(x, y)` / `(left, top, right, bottom)` pixel coordinates
in all its APIs, matching the traditional screen coordinate convention used in 2D graphics
(origin at top-left, x increases rightward, y increases downward).

The aerocloud geometry package bridges these two worlds. Mixing conventions causes subtle,
hard-to-debug bugs: an `(x, y)` swap in a tight placement loop will silently transpose the
entire word cloud. The fix is a clean boundary: one canonical convention internally,
one well-defined conversion layer at every external input/output point.

## Decision

**(y, x) is canonical internally. (x, y) is accepted only at the Pydantic boundary.**

### D-14: Internal convention

Every internal function takes and returns `(y, x)` tuples. Every NumPy array index is
`arr[y, x]`. Files inside `geometry/` MUST NOT use `(x, y)` ordering for coordinate
tuples.

### D-15: Boundary adapters

Two adapter functions live in `geometry/__init__.py`:

```python
def xy_to_yx(x: int, y: int) -> tuple[int, int]:
    """Convert Pillow-style (x, y) input to internal (y, x). Use at every API entry."""
    return (y, x)

def yx_to_xy(y: int, x: int) -> tuple[int, int]:
    """Convert internal (y, x) to Pillow-style (x, y) output. Use at every API exit."""
    return (x, y)
```

Mis-ordered inputs MUST be caught by Pydantic validators, not silently accepted.

### D-16: AABB Pydantic model field names

The `AABB` Pydantic model carries:

```python
class AABB(AeroCloudBase):
    y_min: int
    x_min: int
    y_max: int
    x_max: int
```

This uses `y_min, x_min, y_max, x_max` — NOT the Pillow `(left, top, right, bottom)`
naming — to make the NumPy-native convention syntactically obvious and grep-able.

### D-32: GlyphBBox field names

`GlyphBBox` carries the pixel-scanned AABB in `(y_min, x_min, y_max, x_max)` ordering
(same as `AABB` above), plus `advance_width`, `pixel_buffer`, and identity tuple.

## Consequences

- All internal geometry computations can use `arr[y, x]` directly without translation
- The two boundary adapters are the sole points where coordinate order changes
- Tests for the boundary adapters are mandatory (they are the firewall)
- External callers (Phase 5 Renderer, Phase 6 Inner Loop) receive and return `(x, y)`
  Pydantic models — they are unaffected by the internal convention
- `AABB` serialization (orjson) produces `{"y_min": ..., "x_min": ..., "y_max": ..., "x_max": ...}`
  which is unambiguous and differs from any Pillow-style serialization

## Enforcement

- Pydantic validators on `AABB` and `GlyphBBox` enforce field names at construction time
- `tests/geometry/unit/test_package_init.py::test_xy_to_yx_roundtrip` and
  `test_yx_to_xy_roundtrip` — verify the adapters are inverses of each other
- `tests/geometry/unit/test_contracts.py` — Pydantic round-trip tests on all geometry
  models with `y_min, x_min, y_max, x_max` field ordering
- Ruff lint rule `N802` / `ARG` catches undeclared parameter reordering at static analysis
  time (imperfect, but combined with test coverage it is sufficient)

## References

- `.planning/phases/04-geometry-v1/04-CONTEXT.md` D-14, D-15, D-16
- AeroCloud Blueprint Teil IV §"Collision Detection" (AABB conventions)
- NumPy array indexing: https://numpy.org/doc/stable/user/basics.indexing.html
