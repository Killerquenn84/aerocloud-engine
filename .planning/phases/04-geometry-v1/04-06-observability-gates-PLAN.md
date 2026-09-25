---
phase: 04-geometry-v1
plan: 06
plan_id: 04-06-observability-gates
type: execute
wave: 4
depends_on: [04-05-collision-placement]
autonomous: true
requirements: [GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07]
files_modified:
  - packages/engine/src/aerocloud/geometry/debug.py
  - packages/engine/src/aerocloud/geometry/metrics.py
  - packages/engine/src/aerocloud/geometry/placement.py
  - packages/engine/src/aerocloud/geometry/sdf_cache.py
  - packages/engine/tests/geometry/determinism/test_byte_identical.py
  - packages/engine/tests/geometry/performance/test_sdf_benchmark.py
  - packages/engine/tests/geometry/security/test_mask_fuzz.py
  - wiki/code/geometry-mask.md
  - wiki/code/geometry-sdf.md
  - wiki/code/geometry-sdf-cache.md
  - wiki/code/geometry-collision.md
  - wiki/code/geometry-glyph.md
  - wiki/code/geometry-placement.md
  - wiki/code/geometry-errors.md
  - wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md
  - wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md
  - wiki/decisions/2026-04-09-phase-4-freetype-pinning.md
  - wiki/tests/geometry.md
  - wiki/log.md
  - wiki/index.md

must_haves:
  truths:
    - "AEROCLOUD_DEBUG_GEO=1 enables debug dump on placement failure to ./debug/geometry/<ts>/"
    - "Debug dump writes mask.png, sdf_heatmap.png, spiral_trace.png, placement.json, env.json"
    - "Matplotlib is lazy-imported INSIDE the debug function (not at module import)"
    - "structlog bound context includes geometry.phase, geometry.word, geometry.budget_left"
    - "OpenTelemetry counters: aerocloud_geometry_sdf_cache_hits_total, _misses_total, _dropped_words_total{reason}"
    - "OpenTelemetry histograms: aerocloud_geometry_sdf_build_seconds, _placement_seconds"
    - "pytest-benchmark test: compute_sdf on 2048² mask completes in < 1.0 s on CI CPU"
    - "Determinism test: 10 identical runs produce byte-identical PlacementResult (excluding wall_clock_ms)"
    - "hypothesis fuzz test: mask_from_bytes(random bytes) raises ONLY typed GeometryError subclasses, never OSError/ValueError"
    - "Wiki: 7 code pages, 3 decision mirrors, 1 test summary, log + index updated"
  artifacts:
    - path: "packages/engine/src/aerocloud/geometry/debug.py"
      provides: "dump_geometry_debug(mask, sdf, placement_result, spiral_trace) — gated on AEROCLOUD_DEBUG_GEO"
    - path: "packages/engine/src/aerocloud/geometry/metrics.py"
      provides: "structlog bound logger + OTel counters/histograms"
    - path: "packages/engine/tests/geometry/performance/test_sdf_benchmark.py"
      provides: "pytest-benchmark perf gate (Nyquist dim 8)"
    - path: "packages/engine/tests/geometry/determinism/test_byte_identical.py"
      provides: "10-run byte-identity test (Nyquist dim 6)"
    - path: "packages/engine/tests/geometry/security/test_mask_fuzz.py"
      provides: "hypothesis fuzz of mask_from_bytes (Nyquist dim 7)"
    - path: "wiki/code/geometry-*.md (7 files)"
      provides: "Karpathy wiki pattern — per-module code docs"
    - path: "wiki/decisions/2026-04-09-phase-4-*.md (3 files)"
      provides: "ADR mirrors for discoverability via wiki:query"
  key_links:
    - from: "geometry/placement.py"
      to: "geometry/debug.py"
      via: "dump_geometry_debug call on failure path when env var set"
      pattern: "AEROCLOUD_DEBUG_GEO|dump_geometry_debug"
    - from: "geometry/placement.py"
      to: "geometry/metrics.py"
      via: "histogram.record + structlog bind"
      pattern: "aerocloud_geometry_placement_seconds|structlog"
    - from: "wiki/log.md"
      to: "Phase 4 wave 4 entry"
      via: "dated log entry"
      pattern: "2026-04"
---

<objective>
Wave 4: Close Phase 4 with observability + Nyquist dimensions 6, 7, 8 +
mandatory wiki updates per CLAUDE.md Regel 11.

This wave spans five parallel-ish tasks:
1. Debug dump module (D-47)
2. structlog + OpenTelemetry wiring (D-48, D-49) into sdf_cache + placement
3. Performance benchmark gate (Nyquist dim 8: 2048² SDF < 1 s)
4. Determinism + security tests (Nyquist dims 6 + 7)
5. Wiki mirrors (Regel 11 — 11 new wiki files)

Output: Fully observable Phase 4 + closed Nyquist gates + populated wiki.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/04-VALIDATION.md
@.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
@.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
@.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
@packages/engine/src/aerocloud/observability.py
@packages/engine/src/aerocloud/geometry/placement.py
@packages/engine/src/aerocloud/geometry/sdf_cache.py
@CLAUDE.md
@packages/engine/src/aerocloud/CLAUDE.md
</context>

<tasks>

<task type="auto" id="04-06-T1">
  <name>Task 1: debug.py + metrics.py + wire into sdf_cache + placement</name>
  <files>
    packages/engine/src/aerocloud/geometry/debug.py
    packages/engine/src/aerocloud/geometry/metrics.py
    packages/engine/src/aerocloud/geometry/placement.py
    packages/engine/src/aerocloud/geometry/sdf_cache.py
    packages/engine/tests/geometry/unit/test_debug.py
    packages/engine/tests/geometry/unit/test_metrics.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-CONTEXT.md (D-47, D-48, D-49)
    - packages/engine/src/aerocloud/observability.py (structlog + OTel init pattern)
    - packages/engine/src/aerocloud/geometry/placement.py (from Wave 3)
    - packages/engine/src/aerocloud/geometry/sdf_cache.py (from Wave 2a)
  </read_first>
  <action>
**Step 1 — Create `geometry/metrics.py`:**

```python
"""Phase 4 observability wiring (D-48, D-49).

structlog bound logger + OpenTelemetry counters/histograms. Keeps metric
creation lazy so unit tests that do not exercise these paths do not pay the
OTel init cost.
"""
from __future__ import annotations

from typing import Final

import structlog
from opentelemetry import metrics

logger = structlog.get_logger("aerocloud.geometry")

_meter = metrics.get_meter("aerocloud.geometry")

SDF_CACHE_HITS: Final = _meter.create_counter(
    "aerocloud_geometry_sdf_cache_hits_total",
    description="SDF cache hits",
)
SDF_CACHE_MISSES: Final = _meter.create_counter(
    "aerocloud_geometry_sdf_cache_misses_total",
    description="SDF cache misses",
)
DROPPED_WORDS: Final = _meter.create_counter(
    "aerocloud_geometry_dropped_words_total",
    description="Words dropped during placement by DropReason",
)
SDF_BUILD_SECONDS: Final = _meter.create_histogram(
    "aerocloud_geometry_sdf_build_seconds",
    description="compute_sdf wall clock in seconds",
    unit="s",
)
PLACEMENT_SECONDS: Final = _meter.create_histogram(
    "aerocloud_geometry_placement_seconds",
    description="place_words wall clock in seconds",
    unit="s",
)
```

**Step 2 — Create `geometry/debug.py`:**

```python
"""AEROCLOUD_DEBUG_GEO=1 dump (D-47).

Gated entirely on the env var. Writes mask.png, sdf_heatmap.png,
spiral_trace.png, placement.json, env.json to ./debug/geometry/<ts>/.

Matplotlib is imported LAZILY inside this function to keep it out of the
default import graph (R-7 — 80 MB dep).
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, features

_DEBUG_ENV = "AEROCLOUD_DEBUG_GEO"


def debug_enabled() -> bool:
    return os.environ.get(_DEBUG_ENV, "0") not in ("0", "", "false", "False")


def dump_geometry_debug(
    *,
    mask: np.ndarray,
    sdf: np.ndarray,
    placement_json: dict[str, Any],
    spiral_trace: list[tuple[int, int]] | None = None,
    tag: str = "run",
) -> Path | None:
    """Dump a debug bundle. Returns path or None if not enabled."""
    if not debug_enabled():
        return None

    ts = time.strftime("%Y%m%dT%H%M%S")
    out = Path("./debug/geometry") / f"{ts}-{tag}"
    out.mkdir(parents=True, exist_ok=True)

    # mask.png — plain L-mode
    Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(out / "mask.png")

    # sdf_heatmap.png — lazy matplotlib
    try:
        import matplotlib  # noqa: PLC0415 - deliberate lazy import
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415
        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(sdf, cmap="RdBu_r", origin="upper")
        fig.colorbar(im, ax=ax)
        fig.savefig(out / "sdf_heatmap.png", dpi=72, bbox_inches="tight")
        plt.close(fig)
    except ImportError:
        (out / "sdf_heatmap.MISSING").write_text("matplotlib not installed")

    # spiral_trace.png — overlay on sdf
    if spiral_trace:
        try:
            import matplotlib  # noqa: PLC0415
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt  # noqa: PLC0415
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.imshow(sdf, cmap="gray", origin="upper")
            ys, xs = zip(*spiral_trace, strict=True)
            ax.plot(xs, ys, "r.-", markersize=1, linewidth=0.5)
            fig.savefig(out / "spiral_trace.png", dpi=72, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            pass

    # placement.json
    (out / "placement.json").write_text(json.dumps(placement_json, indent=2))

    # env.json
    env = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pillow": getattr(__import__("PIL"), "__version__", "unknown"),
        "freetype": features.version("freetype2"),
    }
    (out / "env.json").write_text(json.dumps(env, indent=2))

    return out
```

**Step 3 — Wire into `sdf_cache.py`:** Increment `SDF_CACHE_HITS` on cache hit, `SDF_CACHE_MISSES` on miss, record `SDF_BUILD_SECONDS` histogram around `compute_sdf` call. Import `logger` from `metrics`. Emit `logger.info("sdf_cache_hit", shape=...)` on hit.

**Step 4 — Wire into `placement.py`:**
- At `place_words` entry: `log = logger.bind(phase="placement", seed=request.seed, total_words=len(request.words))`
- On dropped word: `log.warning("word_dropped", word=word, reason=reason.value)` + `DROPPED_WORDS.add(1, {"reason": reason.value})`
- Histogram record `PLACEMENT_SECONDS.record(wall_ms/1000.0)` at end
- On `PlacementFailedError`: call `dump_geometry_debug(mask=mask, sdf=sdf, placement_json={...}, tag="failed")` before raising

**Step 5 — Unit tests:**
- `test_metrics.py` — assert all 5 metric instruments exist and `logger` is bound
- `test_debug.py` — assert `debug_enabled()` returns False without env, True with env=1; assert `dump_geometry_debug` returns None when disabled; with env=1 + tmp cwd, assert files are created (mask.png, placement.json, env.json); matplotlib failure path does not crash (use monkeypatch on `sys.modules['matplotlib']` to force ImportError if needed)
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/unit/test_debug.py tests/geometry/unit/test_metrics.py tests/geometry/integration/test_pipeline.py -x -q && uv run mypy --strict src/aerocloud/geometry/debug.py src/aerocloud/geometry/metrics.py && uv run ruff check src/aerocloud/geometry/debug.py src/aerocloud/geometry/metrics.py</automated>
  </verify>
  <acceptance_criteria>
    - `geometry/debug.py` exports `dump_geometry_debug` and `debug_enabled`
    - `geometry/metrics.py` exposes `logger`, 3 counters, 2 histograms
    - `sdf_cache.py` records cache hits/misses + sdf_build_seconds
    - `placement.py` records placement_seconds + dropped_words counter + structlog bind
    - matplotlib import is lazy (inside function, not module level)
    - Unit tests for debug + metrics pass
    - Full `pytest tests/geometry` still green (existing tests not broken by wiring)
  </acceptance_criteria>
  <done>Observability active, debug dump gated on env var</done>
</task>

<task type="auto" id="04-06-T2">
  <name>Task 2: Nyquist dims 6 + 7 + 8 — determinism, security fuzz, performance benchmark</name>
  <files>
    packages/engine/tests/geometry/determinism/test_byte_identical.py
    packages/engine/tests/geometry/security/test_mask_fuzz.py
    packages/engine/tests/geometry/performance/test_sdf_benchmark.py
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-VALIDATION.md §8-Dimension Nyquist Coverage
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §10
    - packages/engine/src/aerocloud/geometry/placement.py
    - packages/engine/src/aerocloud/geometry/sdf.py
    - packages/engine/src/aerocloud/geometry/mask.py
  </read_first>
  <action>
**Step 1 — Determinism test (`test_byte_identical.py`):**

```python
"""Nyquist dim 6: 10 repeat runs produce byte-identical PlacementResult (D-45)."""
from __future__ import annotations

import json
from aerocloud.geometry.placement import place_words
from aerocloud.geometry.sdf_cache import clear_cache
from aerocloud.models.geometry import PlacementRequest


def _canonical(result) -> str:
    payload = result.model_dump(mode="json")
    # Wall clock is non-deterministic; everything else must be stable.
    payload["stats"].pop("wall_clock_ms", None)
    return json.dumps(payload, sort_keys=True)


def test_ten_runs_byte_identical(circle_mask_bytes: bytes) -> None:
    req = PlacementRequest(
        raw_png_bytes=circle_mask_bytes,
        words=[(f"w{i}", 4, 6) for i in range(8)],
        seed=1337,
    )
    canonicals = []
    for _ in range(10):
        clear_cache()
        canonicals.append(_canonical(place_words(req)))
    assert len(set(canonicals)) == 1, (
        f"Non-deterministic across 10 runs: {len(set(canonicals))} distinct results"
    )
```

**Step 2 — Security fuzz (`test_mask_fuzz.py`):**

```python
"""Nyquist dim 7: mask_from_bytes must only raise typed GeometryError subclasses."""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st

from aerocloud.geometry.errors import GeometryError
from aerocloud.geometry.mask import mask_from_bytes


@given(st.binary(min_size=0, max_size=4096))
@settings(
    max_examples=200,
    deadline=2000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_random_bytes_only_raise_geometry_errors(raw: bytes) -> None:
    try:
        mask_from_bytes(raw)
    except GeometryError:
        # OK — typed error
        pass
    except Exception as exc:  # pragma: no cover - this would be a bug
        raise AssertionError(
            f"mask_from_bytes leaked untyped {type(exc).__name__}: {exc}"
        ) from exc
```

**Step 3 — Performance benchmark (`test_sdf_benchmark.py`):**

```python
"""Nyquist dim 8: 2048² SDF < 1.0 s, 100-word placement < 5 s."""
from __future__ import annotations

import io
import numpy as np
import pytest
from PIL import Image

from aerocloud.geometry.mask import mask_from_bytes
from aerocloud.geometry.sdf import compute_sdf
from aerocloud.geometry.sdf_cache import clear_cache
from aerocloud.geometry.placement import place_words
from aerocloud.models.geometry import PlacementRequest


def _big_circle_png(size: int = 2048) -> bytes:
    y, x = np.ogrid[:size, :size]
    mask = (y - size // 2) ** 2 + (x - size // 2) ** 2 <= (size // 3) ** 2
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.benchmark(group="geometry")
def test_sdf_2048_under_one_second(benchmark) -> None:
    png = _big_circle_png(2048)
    mask = mask_from_bytes(png)

    def run():
        return compute_sdf(mask)

    sdf = benchmark(run)
    assert sdf.shape == (2048, 2048)
    # Raw-run walltime gate (in addition to benchmark stats)
    assert benchmark.stats["mean"] < 1.0, (
        f"compute_sdf 2048² mean {benchmark.stats['mean']:.3f}s exceeds 1.0 s budget"
    )


@pytest.mark.benchmark(group="geometry")
def test_placement_100_words_under_five_seconds(benchmark) -> None:
    png = _big_circle_png(1024)  # 1024² to keep benchmark time bounded
    req = PlacementRequest(
        raw_png_bytes=png,
        words=[(f"w{i}", 12, 24) for i in range(100)],
        seed=7,
    )

    def run():
        clear_cache()
        return place_words(req)

    result = benchmark(run)
    assert result.stats.placed + result.stats.dropped == 100
    assert benchmark.stats["mean"] < 5.0, (
        f"place_words 100-word 1024² mean {benchmark.stats['mean']:.3f}s exceeds 5.0 s budget"
    )
```

**Step 4 — Run all three test families:**
```bash
cd packages/engine && uv run pytest tests/geometry/determinism tests/geometry/security tests/geometry/performance -x -q --benchmark-warmup=off
```

Note: if the 2048² SDF benchmark exceeds 1 s on CI hardware, Open Question 6 from RESEARCH.md applies — profile + decide whether to accept higher budget or downsample. Document the observed time in SUMMARY.md either way.
  </action>
  <verify>
    <automated>cd packages/engine && uv run pytest tests/geometry/determinism tests/geometry/security tests/geometry/performance -x -q --benchmark-disable && uv run ruff check tests/geometry/determinism tests/geometry/security tests/geometry/performance</automated>
  </verify>
  <acceptance_criteria>
    - `test_byte_identical.py` passes (10-run identity)
    - `test_mask_fuzz.py` passes with 200 hypothesis examples, no untyped exception leaks
    - `test_sdf_benchmark.py` passes (pytest-benchmark runs, budget assertion holds OR SUMMARY notes deviation)
    - `test_placement_100_words_under_five_seconds` passes with 1024² canvas
    - ruff clean on all three test files
  </acceptance_criteria>
  <done>Nyquist dims 6, 7, 8 green</done>
</task>

<task type="auto" id="04-06-T3">
  <name>Task 3: Wiki population — 7 code pages + 3 decision mirrors + tests summary + log/index</name>
  <files>
    wiki/code/geometry-mask.md
    wiki/code/geometry-sdf.md
    wiki/code/geometry-sdf-cache.md
    wiki/code/geometry-collision.md
    wiki/code/geometry-glyph.md
    wiki/code/geometry-placement.md
    wiki/code/geometry-errors.md
    wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md
    wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md
    wiki/decisions/2026-04-09-phase-4-freetype-pinning.md
    wiki/tests/geometry.md
    wiki/log.md
    wiki/index.md
  </files>
  <read_first>
    - CLAUDE.md (Regel 11 — wiki schema)
    - packages/engine/src/aerocloud/CLAUDE.md
    - wiki/index.md (existing structure — read first, append don't replace)
    - wiki/log.md (existing format)
    - .planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md
    - .planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md
    - .planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md
    - packages/engine/src/aerocloud/geometry/*.py (all 7 production files)
  </read_first>
  <action>
**Create 7 code docs** under `wiki/code/`. Each follows the Karpathy pattern:

```markdown
# geometry/{module}.py

**Module:** `aerocloud.geometry.{module}`
**Phase:** 04-geometry-v1
**Decisions:** D-XX, D-YY, D-ZZ
**ADRs:** ADR-0004, ADR-0005, ADR-0006

## Purpose
<one paragraph>

## Public API
<function signatures from source>

## Key invariants
- <invariant 1>
- <invariant 2>

## Dependencies
- <import list>

## Tests
- tests/geometry/unit/test_{module}.py
- tests/geometry/property/test_{module}_properties.py (if applicable)

## Related
- `wiki/code/geometry-{related}.md`
- `.planning/phases/04-geometry-v1/04-CONTEXT.md`
```

Produce one such doc for EACH of: `mask`, `sdf`, `sdf-cache`, `collision`, `glyph`, `placement`, `errors`.

**Create 3 decision mirrors** under `wiki/decisions/` (dated `2026-04-09-phase-4-*.md`). Each is a 1:1 mirror of the corresponding ADR file in `.planning/phases/04-geometry-v1/`, with a header linking back to the ADR. This keeps the wiki self-contained per Regel 11 while preserving the ADR as canonical source.

**Create `wiki/tests/geometry.md`** summarizing the Phase 4 test coverage:

```markdown
# Phase 4 Geometry-v1 Test Coverage

## Dimensions (Nyquist 8)
1. Unit — tests/geometry/unit/ (7 modules)
2. Integration — tests/geometry/integration/test_pipeline.py (5 fixtures)
3. Contract — tests/geometry/unit/test_contracts.py (Pydantic round-trip)
4. State — tests/geometry/state/test_cache.py (eviction + getsizeof)
5. Concurrency — tests/geometry/state/test_cache_threadsafe.py (16 × 1000)
6. Determinism — tests/geometry/determinism/test_byte_identical.py (10 runs)
7. Security — tests/geometry/security/test_mask_fuzz.py (hypothesis fuzz)
8. Performance — tests/geometry/performance/test_sdf_benchmark.py (2048² SDF < 1 s)

## Golden regression
- tests/regression/test_glyph_golden.py (~450 .npy fixtures)

## Total
~50+ new tests beyond prior phases. Run via `cd packages/engine && uv run pytest tests/geometry tests/regression/test_glyph_golden.py`.
```

**Update `wiki/log.md`** by APPENDING (never overwrite) a dated entry:

```markdown
## 2026-04-09 — Phase 4 Geometry-v1 Wave 4 shipped

- Observability (D-47/D-48/D-49) wired into sdf_cache + placement
- Nyquist dims 6 (determinism) + 7 (fuzz) + 8 (2048² SDF benchmark) green
- Wiki populated: 7 code/, 3 decisions/, 1 tests/geometry.md
- Next: Wave 5 3-KI code review per Regel 6
```

**Update `wiki/index.md`** by APPENDING (preserve existing structure) new rows for all 11 new wiki files in the appropriate sections (code/, decisions/, tests/).
  </action>
  <verify>
    <automated>test -f wiki/code/geometry-mask.md && test -f wiki/code/geometry-sdf.md && test -f wiki/code/geometry-sdf-cache.md && test -f wiki/code/geometry-collision.md && test -f wiki/code/geometry-glyph.md && test -f wiki/code/geometry-placement.md && test -f wiki/code/geometry-errors.md && test -f wiki/decisions/2026-04-09-phase-4-sdf-sign-convention.md && test -f wiki/decisions/2026-04-09-phase-4-coordinate-system-yx.md && test -f wiki/decisions/2026-04-09-phase-4-freetype-pinning.md && test -f wiki/tests/geometry.md && grep -q "Phase 4" wiki/log.md && grep -q "geometry-mask" wiki/index.md</automated>
  </verify>
  <acceptance_criteria>
    - 7 `wiki/code/geometry-*.md` files exist
    - 3 `wiki/decisions/2026-04-09-phase-4-*.md` files exist
    - `wiki/tests/geometry.md` exists with 8 dimensions listed
    - `wiki/log.md` has a new dated entry for Phase 4 Wave 4
    - `wiki/index.md` references all new pages
    - Each code doc mentions at least one D-XX decision ID
  </acceptance_criteria>
  <done>Regel 11 wiki obligations satisfied</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| AEROCLOUD_DEBUG_GEO env var → filesystem write | Operator-controlled flag creates files |
| Random bytes (hypothesis fuzz) → mask_from_bytes | Untrusted bytes reach Pillow decoder |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-06 | Tampering (path traversal) | dump_geometry_debug filesystem write | mitigate | Debug path is hardcoded `./debug/geometry/<timestamp>-<tag>/` — never user-supplied; `tag` is sanitized by placement code to alphanumerics only |
| T-4-07 | Tampering (interpreter crash) | mask_from_bytes under fuzz | mitigate | Task 2 hypothesis fuzz test asserts ONLY `GeometryError` subclasses escape; any untyped exception fails the test |
| T-4-06b | Info disclosure | Debug dump may contain user mask data | accept | Debug dump is opt-in via env var; operators are responsible for managing `./debug/geometry/` retention and access |
</threat_model>

<verification>
- `cd packages/engine && uv run pytest tests/geometry tests/regression/test_glyph_golden.py -x -q --benchmark-disable` exits 0
- `uv run mypy --strict src/aerocloud/geometry/` exits 0 (all 9 geometry files)
- `uv run ruff check src/aerocloud/geometry/ tests/geometry/` exits 0
- Wiki files exist: 7 code + 3 decisions + 1 tests summary + log + index updated
- Performance benchmark recorded in SUMMARY.md (even if budget exceeded, documented)
</verification>

<success_criteria>
1. Debug dump module functional and gated on env var
2. structlog + OTel metrics wired into sdf_cache + placement
3. 10-run byte-identity test green (Nyquist 6)
4. hypothesis fuzz test green (Nyquist 7)
5. pytest-benchmark test runs and records walltime (Nyquist 8) — budget either met or documented deviation
6. All 11 wiki files committed
7. No regression in any earlier wave's tests
</success_criteria>

<output>
Create `.planning/phases/04-geometry-v1/04-06-SUMMARY.md` with:
- Observability wiring summary
- Benchmark walltimes observed (compute_sdf 2048² + place_words 100-word 1024²)
- Whether budgets were met
- Wiki files committed
- Total Phase 4 test count so far (should be > 50 new)
- Phase 4 ready for Wave 5 3-KI code review
</output>
