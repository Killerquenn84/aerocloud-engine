# geometry/collision.py

**Module:** `aerocloud.geometry.collision`
**Phase:** 04-geometry-v1
**Decisions:** D-35, D-36, D-37, D-14, D-16
**ADRs:** ADR-0005 (coordinate system)

## Purpose

Vectorized Stage-1 AABB (Axis-Aligned Bounding Box) collision detection for
the placement hot loop. Integer arithmetic only — no floating-point, no rotation.
Uses half-open interval semantics so adjacent boxes that share only an edge do
NOT collide (D-16).

## Public API

```python
def aabb_overlap(new: np.ndarray, existing: np.ndarray) -> np.ndarray:
    """Return bool[N] mask of which existing AABBs overlap new.

    Args:
        new:      shape (4,) int array — (y_min, x_min, y_max, x_max)
        existing: shape (N, 4) int array, same column ordering (D-35)
    Returns:
        bool ndarray of length N
    """

def has_any_collision(new: np.ndarray, existing: np.ndarray) -> bool:
    """Return True iff new overlaps at least one existing box."""
```

## Key invariants

- Column ordering: `(y_min, x_min, y_max, x_max)` — (y, x) canonical (D-14, D-16).
- Half-open intervals: `[y_min, y_max) × [x_min, x_max)`.
- Coordinates cast to int64 internally to prevent signed-overflow on large masks.
- Rotation deferred to Phase 7 Geometry-v2 (D-37).

## Dependencies

- `numpy`

## Tests

- `tests/geometry/unit/test_collision.py` — overlap variants, edge adjacency, empty existing

## Performance notes

Vectorized NumPy — O(N) per word (N = already-placed words). No tree structure
needed for typical word cloud sizes (< 1000 words). For very large clouds
(> 10 000 words) a BVH/Quadtree would help; deferred to Phase 7.

## Related

- `wiki/code/geometry-placement.md` — calls has_any_collision in the hot loop
- `wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md` — ADR-0005 mirror
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-35 through D-37
