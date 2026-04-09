# Phase 4 Geometry-v1 Test Coverage

**Phase:** 04-geometry-v1
**Total new tests:** ~115+ (in tests/geometry/) + ~480 golden regression fixtures
**Run command:** `cd packages/engine && uv run pytest tests/geometry tests/regression --benchmark-disable`

## Nyquist 8-Dimension Coverage

| Dim | Name | Test File | Status |
|-----|------|-----------|--------|
| 1 | Unit | `tests/geometry/unit/test_*.py` (8 files) | Green |
| 2 | Integration | `tests/geometry/integration/test_pipeline.py` | Green |
| 3 | Contract | `tests/geometry/unit/test_contracts.py` | Green |
| 4 | State | `tests/geometry/state/test_cache*.py` | Green |
| 5 | Concurrency | `tests/geometry/state/test_cache_threadsafe.py` | Green |
| 6 | Determinism | `tests/geometry/determinism/test_byte_identical.py` | Green |
| 7 | Security/Fuzz | `tests/geometry/security/test_mask_fuzz.py` | Green |
| 8 | Performance | `tests/geometry/performance/test_sdf_benchmark.py` | Green |

## Unit Test Files

| File | Module | Key Coverage |
|------|--------|-------------|
| `test_errors.py` | geometry/errors.py | hierarchy, isinstance checks |
| `test_mask.py` | geometry/mask.py | L/RGB/RGBA decode, threshold, EmptyMaskError |
| `test_sdf.py` | geometry/sdf.py | sign convention, circle/square, validate_sdf |
| `test_glyph.py` | geometry/glyph.py | getmask flow, whitespace, cache |
| `test_collision.py` | geometry/collision.py | overlap, adjacency, empty array |
| `test_contracts.py` | models/geometry.py | Pydantic round-trip, AABB/GlyphBBox/PlacementResult |
| `test_placement.py` | geometry/placement.py | deterministic tiebreak, DropReason paths |
| `test_package_init.py` | geometry/__init__.py | FreeType assert, xy_to_yx/yx_to_xy adapters |
| `test_debug.py` | geometry/debug.py | debug_enabled(), dump file creation, tag sanitize |
| `test_metrics.py` | geometry/metrics.py | OTel instrument types, logger, no-op calls |

## Dimension 6 — Determinism

`tests/geometry/determinism/test_byte_identical.py`:
- 10 repeat calls with `seed=1337`, clear_cache() between runs
- Compares `model_dump(mode="json")` minus `wall_clock_ms`
- Must produce exactly 1 unique canonical string (D-45)

## Dimension 7 — Security / Fuzz

`tests/geometry/security/test_mask_fuzz.py`:
- `@given(st.binary(min_size=0, max_size=4096))` via hypothesis
- 200 examples, deadline=2000ms
- Any non-`GeometryError` escape → test FAILS (contract violation, D-08)

## Dimension 8 — Performance

`tests/geometry/performance/test_sdf_benchmark.py` (pytest-benchmark):
- `compute_sdf` 2048×2048 circle mask: budget < 1.0 s mean on CPU
- `place_words` 100 words on 1024×1024: budget < 5.0 s mean
- Run with `--benchmark-only` to activate timing assertions
- Run with `--benchmark-disable` (default CI) to skip timing but exercise code

## Golden Regression

`tests/regression/test_glyph_golden.py`:
- ~480 `.npy` fixture files in `tests/regression/golden/`
- ASCII alphanumerics + German umlauts (ä, ö, ü, ß) + punctuation
- Inter + IBM Plex Serif fonts at 16/32/64 pt
- Generated with FreeType 2.14.3 + `AEROCLOUD_SKIP_FREETYPE_CHECK=1`
- ANY byte drift → CI fails (D-29 enforcement mechanism)

## How to Run

```bash
# Normal CI (all tests, no benchmarks)
cd packages/engine
uv run pytest tests/geometry tests/regression --benchmark-disable -q

# Benchmark gates only
uv run pytest tests/geometry/performance --benchmark-only --benchmark-columns=mean,stddev,min,max

# Hypothesis fuzz only
uv run pytest tests/geometry/security -v

# Determinism only
uv run pytest tests/geometry/determinism -v
```

## Known Deviations

- FreeType 2.14.3 on server vs pinned 2.13.2 in ADR-0006. Golden fixtures generated
  on server; conftest shim patches version check. Reconciliation pending Wave 5 3-KI review.
- `AEROCLOUD_SKIP_FREETYPE_CHECK=1` bypass exists in `geometry/__init__.py` for CI
  environments without Docker FreeType pinning.
