# geometry/placement.py

**Module:** `aerocloud.geometry.placement`
**Phase:** 04-geometry-v1
**Decisions:** D-38, D-39, D-40, D-41, D-42, D-43, D-44, D-45, D-46, D-47, D-48, D-49
**ADRs:** ADR-0004, ADR-0005

## Purpose

Places words into a silhouette mask using a per-word adaptive POI spiral search.
Returns a structured `PlacementResult` with placed words, dropped words (with
machine-readable `DropReason`), and placement statistics. Fully deterministic
given the same input and seed (D-45).

## Public API

```python
def place_words(request: PlacementRequest) -> PlacementResult:
    """Place words using per-word adaptive POI spiral (D-38..D-46).

    Calls set_seed(request.seed) at entry for determinism (D-45).
    Logs placement lifecycle via structlog (D-48).
    Records PLACEMENT_SECONDS histogram + DROPPED_WORDS counter (D-49).
    Calls dump_geometry_debug() on dropped-word paths when AEROCLOUD_DEBUG_GEO=1 (D-47).

    Raises:
        PlacementFailedError: ONLY on contract violations (NaN/inf SDF)
        EmptyMaskError:        if decoded mask has no inside or no outside pixels
    """

def feasibility_field(sdf, occupied, h, w) -> np.ndarray:
    """Compute feasibility SDF for a word AABB of size (h, w) (D-39)."""

def select_origin(feasible_sdf, mask_centroid) -> tuple[int, int] | None:
    """Pick best anchor from eps-band max with centroid Manhattan + (y,x) lex tiebreak (D-39)."""

def archimedean_offsets(step, max_iters) -> list[tuple[int, int]]:
    """Generate deduplicated integer (dy, dx) Archimedean spiral offsets (D-40)."""
```

## Key invariants

- **Per-word adaptive origin** (NOT single global POI) — single-origin is O(4×10^7)
  probes for 200 words at 2048² (D-38, Codex g-5 math).
- Spiral offsets are integer (dy, dx) tuples; FP is used only for feasibility
  field (scipy float32) and SDF lookup → immediately floored to int (D-46).
- `MAX_STEP=16` (aliasing guard), `MIN_STEP=1`, `MAX_ITERATIONS_PER_SEED=500`,
  `MAX_SEEDS_PER_WORD=3`, `MAX_WALL_CLOCK_PER_WORD=1.0 s` (D-41/D-42).
- Ordinary unplaceable word → `DroppedWord(reason=DropReason.*)`, never an exception (D-43).
- `PlacementFailedError` only for NaN/inf SDF or internal invariant failures (D-43).

## Drop reasons

| DropReason | Meaning |
|---|---|
| `NO_FEASIBLE_ANCHOR` | No positive-valued pixel in feasibility field |
| `ITERATION_BUDGET_EXCEEDED` | All seeds exhausted 500-iter spiral |
| `TOO_LARGE_FOR_MASK` | h or w exceeds canvas dimensions |
| `WALL_CLOCK_EXCEEDED` | Word exceeded 1.0 s per-word walltime budget |

## Dependencies

- `scipy.ndimage` (minimum_filter, binary_dilation)
- `numpy`
- `aerocloud.geometry.{collision, debug, mask, metrics, sdf_cache}`
- `aerocloud.models.geometry` (AABB, DropReason, PlacementRequest/Result)
- `aerocloud.utils.determinism` (set_seed)

## Tests

- `tests/geometry/unit/test_placement.py` — deterministic tiebreak, DropReason paths
- `tests/geometry/integration/test_pipeline.py` — end-to-end on circle/square/C-shape
- `tests/geometry/determinism/test_byte_identical.py` — 10-run byte identity (Nyquist dim 6)
- `tests/geometry/performance/test_sdf_benchmark.py` — 100-word 1024² < 5 s (Nyquist dim 8)

## Related

- `wiki/code/geometry-sdf-cache.md` — SDF sourced here
- `wiki/code/geometry-collision.md` — AABB collision called in hot loop
- `.planning/phases/04-geometry-v1/04-CONTEXT.md` — D-38 through D-49
