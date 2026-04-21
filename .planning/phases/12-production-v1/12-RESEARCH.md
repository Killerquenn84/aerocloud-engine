# Phase 12: Production v1 - Research

**Researched:** 2026-04-16
**Domain:** FastAPI + Celery + Export Pipeline (Seam Carving, SVG, PDF, PNG, Boolean Union) + Security Hardening + Observability + Golden-Image Testing
**Confidence:** HIGH (codebase verified) / MEDIUM (PyPI versions) / LOW (DCGM sidecar without live GPU)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Export Pipeline (Seam Carving + SVG/PDF/PNG)
- **D-01:** New `export/` subpackage in `packages/engine/src/aerocloud/export/`. Modules: `seam_carving.py`, `svg_export.py`, `pdf_export.py`, `png_export.py`, `boolean_union.py`.
- **D-02:** Seam Carving energy function: custom `E(x,y) = sum(w_i * Gauss(distance))` with word-weight-aware energy map. DP optimal seam O(w*h). Pure Python + numpy.
- **D-03:** SVG export via `svgelements` (already in deps). BezierGlyph → SVG `<path>` elements. Coordinate flip (y,x) → (x,y) at export boundary.
- **D-04:** PDF export via `reportlab` (already in deps). Sub-millimeter precision. BezierGlyph → ReportLab path operations.
- **D-05:** PNG export via `Pillow` from rendered tensors. `(tensor * 255).byte().numpy()` → `Image.fromarray()`.
- **D-06:** Boolean union on Bezier paths via `shapely` (add to deps) for polygon union. Prevents double cuts in print. Convert BezierGlyph → Shapely polygon, union, convert back.

#### FastAPI HTTP Surface
- **D-07:** FastAPI app in `apps/api/` (already scaffolded). `POST /render` with Pydantic `RenderRequest` schema.
- **D-08:** Returns `task_id` immediately. SSE endpoint `GET /render/{task_id}/progress` via `StreamingResponse` with Redis pub/sub for Celery task progress relay.
- **D-09:** Health endpoints: `GET /health` (public, no auth) and `GET /health/internal` (authenticated, detailed).
- **D-10:** Rate limiting via `slowapi` (Redis-backed token bucket). Per-shop rate limits from Shopify session token.

#### Celery Worker Configuration
- **D-11:** `--pool=prefork`, `--concurrency=1`, `--max-tasks-per-child=50`. Prefork for GPU memory isolation.
- **D-12:** Two queues: `realtime` (live API renders, priority) and `background` (Self-Play nightly, low priority). Route via `task_routes` in celery_app.py.
- **D-13:** Hard task timeout: `time_limit=300` (5 min) for realtime renders. `soft_time_limit=28800` for background (8h).
- **D-14:** GPU resource isolation: one worker per GPU. `CUDA_VISIBLE_DEVICES` env var per worker instance.

#### Security Hardening
- **D-15:** SVG color allow-list: `^#[0-9a-fA-F]{3,8}$` regex validation in Pydantic model.
- **D-16:** Font name allow-list: validate against registered fonts in `assets/fonts/`.
- **D-17:** Path traversal prevention: Pydantic validators on all file-like inputs. No raw file paths in API — binary upload only.
- **D-18:** CORS disabled (server-to-server only per CLAUDE.md §12).

#### Observability
- **D-19:** Upgrade observability.py NoOp → OTLP exporter for distributed tracing (FastAPI → Celery → GPU worker).
- **D-20:** Prometheus metrics via `prometheus-client` + `prometheus-fastapi-instrumentator`. Separate from OTel.
- **D-21:** NVIDIA DCGM Exporter as Docker sidecar container in docker-compose.yml.

#### Graceful Shutdown + Hardening
- **D-22:** SIGTERM handler in worker: drain in-flight tasks, flush archive, exit 0. `worker_shutting_down` Celery signal.
- **D-23:** Dockerfile: `STOPSIGNAL SIGTERM`, health check on worker.
- **D-24:** `ulimit -c 0` in worker entrypoint (core dumps disabled per CLAUDE.md §12).

#### Testing & Release Gate
- **D-25:** Golden-image regression tests: circle, square, star, crescent fixtures. Compare rendered output against golden .png files with SSIM threshold.
- **D-26:** Load test: 100 concurrent renders via `locust` or `httpx` async. Measure P99 latency.
- **D-27:** Release gate: all tests green, P99 within budget, SSIM > 0.95, 3-KI review approved.

### Claude's Discretion
- Seam carving Gaussian sigma parameter
- SSE heartbeat interval
- Prometheus metric names and labels
- Load test ramp-up pattern
- Golden image SSIM threshold exact value

### Deferred Ideas (OUT OF SCOPE)
- WebSocket progress streaming — SSE is sufficient for v1
- Multi-GPU auto-scaling — single GPU per worker for v1
- CDN for rendered assets — direct serve for v1
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-01 | Seam Carving energy function: `E(x,y) = Σ wᵢ · Gauss(distance)` | numpy-based DP seam algorithm documented in wiki/seam-carving.md |
| PROD-02 | Optimal seam computation via DP O(w·h) | DP algorithm from wiki + Avidan & Shamir 2007 pattern |
| PROD-03 | Bezier export via `svgelements` for SVG | svgelements 1.9.6 in geometry deps; BezierGlyph (y,x) → SVG (x,y) flip pattern |
| PROD-04 | PDF export via `ReportLab` for sub-millimeter precision | reportlab 4.4.10 on PyPI; already in geometry deps |
| PROD-05 | PNG export via `Pillow` from rendered tensors | Pillow 12.2.0 installed; tensor→numpy→PIL pattern standard |
| PROD-06 | Boolean union on Bezier paths via shapely | shapely 2.1.2 on PyPI; NOT yet installed; needs adding to production deps |
| PROD-07 | FastAPI `POST /render` with Pydantic validation | FastAPI 0.135.3 installed; RenderRequest model exists in models/api.py |
| PROD-08 | FastAPI returns task_id; SSE endpoint streams progress | sse-starlette 3.3.4 on PyPI; StreamingResponse + Redis pub/sub pattern |
| PROD-09 | Celery worker prefork, concurrency=1, max-tasks-per-child=50 | Celery 5.6.3 installed; prefork pool for GPU isolation confirmed best practice |
| PROD-10 | Two queues: realtime + background | celery_app.py already has background queue; realtime queue to be added |
| PROD-11 | GPU resource isolation: dedicated worker pool per GPU | CUDA_VISIBLE_DEVICES env var per worker instance |
| PROD-12 | Hard task timeout per-render budget | time_limit=300, soft_time_limit=28800 Celery params |
| PROD-13 | SVG color allow-list regex `^#[0-9a-fA-F]{3,8}$` | Pydantic field_validator with re.fullmatch() |
| PROD-14 | Font name allow-list against registered fonts | Validate against assets/fonts/ directory listing at startup |
| PROD-15 | Path traversal prevention on mask uploads | Pydantic base64 validator; shape_b64 field already defined in RenderRequest |
| PROD-16 | Rate limiting on public API endpoints | slowapi 0.1.9 on PyPI; Redis-backed token bucket |
| PROD-17 | /health (public) and /health/internal (auth) endpoints | CLAUDE.md §12 hardcoded requirement |
| PROD-18 | OpenTelemetry tracing FastAPI → Celery → GPU worker | observability.py upgraded from NoOp → OTLPSpanExporter; otel-exporter-otlp 1.41.0 |
| PROD-19 | Prometheus metrics + NVIDIA DCGM Exporter | prometheus-client 0.25.0 + prometheus-fastapi-instrumentator 7.1.0 on PyPI |
| PROD-20 | Graceful shutdown on SIGTERM | worker_shutting_down Celery signal + STOPSIGNAL in Dockerfile |
| PROD-21 | Golden-image regression tests for renderer output | scikit-image 0.26.0 (ssim); fixtures: circle, square, star, crescent |
| PROD-22 | Load test: 100 concurrent renders, P99 measurement | locust 2.43.4 on PyPI (NOT installed); httpx 0.28.1 already installed as alternative |
| PROD-23 | Release gate: tests green, metrics in budget, 3-AI review approved | Combines all above |
</phase_requirements>

---

## Summary

Phase 12 is the final integration phase — 23 requirements spanning five distinct technical domains: (1) export pipeline (seam carving, SVG/PDF/PNG, boolean union), (2) FastAPI HTTP surface with SSE progress streaming, (3) Celery worker hardening for GPU isolation, (4) security hardening and observability, and (5) golden-image regression + load testing as the release gate.

The existing codebase is well-prepared. FastAPI 0.135.3 and Celery 5.6.3 are installed. The `export/` directory scaffold exists under `packages/engine/src/aerocloud/export/`. The `RenderRequest`/`RenderResult` Pydantic models are already defined in `models/api.py`. The Celery app already has the `background` queue wired; the `realtime` queue is new. The `observability.py` module is Phase 12-ready (explicitly flagged for OTLP upgrade). The docker-compose.yml has no GPU service entries yet — those must be added.

The primary new dependencies that are NOT yet installed are: `shapely` (boolean union), `slowapi` (rate limiting), `prometheus-client` + `prometheus-fastapi-instrumentator` (metrics), `opentelemetry-exporter-otlp` (OTLP tracing), `sse-starlette` (SSE streaming), `scikit-image` (SSIM golden-image comparison), and optionally `locust` (load test). The `geometry` optional-dependency group already declares `svgelements>=1.9.6` and `reportlab>=4.2.0`.

**Primary recommendation:** Install the six missing deps into the appropriate pyproject.toml files, implement the five export modules in `export/`, wire the FastAPI endpoints, extend Celery config, upgrade observability, add DCGM sidecar to docker-compose, write golden-image tests with scikit-image SSIM, run load test via httpx (already installed) rather than locust.

---

## Standard Stack

### Core (already installed)

| Library | Version (verified) | Purpose | Source |
|---------|--------------------|---------|--------|
| FastAPI | 0.135.3 | HTTP surface, POST /render, SSE, /health | [VERIFIED: uv pip list] |
| uvicorn | 0.44.0 | ASGI server for FastAPI | [VERIFIED: uv pip list] |
| Celery | 5.6.3 | Task queue, GPU job dispatch | [VERIFIED: uv pip list] |
| Pillow | 12.2.0 | PNG export from tensors | [VERIFIED: uv pip list] |
| scipy | 1.17.1 | Used in seam carving energy vectorization | [VERIFIED: uv pip list] |
| httpx | 0.28.1 | Async HTTP client for load test | [VERIFIED: uv pip list] |
| opentelemetry-api | 1.40.0 | Tracing API (NoOp currently) | [VERIFIED: uv pip list] |
| opentelemetry-sdk | 1.40.0 | Tracing SDK | [VERIFIED: uv pip list] |

### New Dependencies (PyPI verified, not yet installed)

| Library | Version | Purpose | Group |
|---------|---------|---------|-------|
| shapely | 2.1.2 | Boolean union on Bezier polygons | production |
| slowapi | 0.1.9 | Redis-backed rate limiting for FastAPI | api |
| prometheus-client | 0.25.0 | Prometheus metrics exposition | api + worker |
| prometheus-fastapi-instrumentator | 7.1.0 | Auto-instrument FastAPI routes | api |
| opentelemetry-exporter-otlp | 1.41.0 | OTLP span export (upgrade from NoOp) | api + worker |
| sse-starlette | 3.3.4 | SSE streaming via StreamingResponse | api |
| scikit-image | 0.26.0 | SSIM comparison for golden-image tests | dev |

[VERIFIED: PyPI JSON API, 2026-04-16]

### Already in Geometry Optional Group (declared, install with `[geometry]` extras)

| Library | Declared Version | Purpose |
|---------|-----------------|---------|
| svgelements | >=1.9.6 (latest: 1.9.6) | BezierGlyph → SVG path elements |
| reportlab | >=4.2.0 (latest: 4.4.10) | BezierGlyph → PDF path ops |

[VERIFIED: packages/engine/pyproject.toml geometry group + PyPI]

### Alternatives Considered (already decided — not alternatives)

| Locked Choice | Alternative | Why Locked Won |
|---------------|-------------|----------------|
| prefork pool | gevent/eventlet | CUDA fork-safety — gevent triggers CUDA context corruption |
| SSE via StreamingResponse | WebSocket | Simpler, unidirectional, no upgrade needed; WS deferred per CONTEXT.md |
| httpx async load test | locust | locust not installed; httpx 0.28.1 already available; asyncio.gather covers 100 concurrent |
| shapely for boolean union | clipper2py | shapely 2.x uses GEOS 3.12 — mature, well-typed, Pydantic-compatible |

### Installation Commands

```bash
# Production deps — add to apps/api/pyproject.toml
uv add --package aerocloud-api \
  "slowapi>=0.1.9" \
  "prometheus-client>=0.25.0" \
  "prometheus-fastapi-instrumentator>=7.1.0" \
  "opentelemetry-exporter-otlp>=1.41.0" \
  "sse-starlette>=3.3.4"

# Engine production optional group — add shapely
uv add --package aerocloud-engine \
  --optional production \
  "shapely>=2.1.2"

# Dev deps (test only)
uv add --dev "scikit-image>=0.26.0"
```

---

## Architecture Patterns

### Recommended File Layout for Phase 12

```
packages/engine/src/aerocloud/export/
├── __init__.py              # exports: SeamCarver, export_svg, export_pdf, export_png, boolean_union
├── seam_carving.py          # SeamCarver class: energy_map(), find_seam(), remove_seam()
├── svg_export.py            # export_svg(glyphs: list[BezierGlyph], layout, ...) -> str
├── pdf_export.py            # export_pdf(glyphs: list[BezierGlyph], layout, ...) -> bytes
├── png_export.py            # export_png(tensor: torch.Tensor) -> bytes
└── boolean_union.py         # union_glyphs(glyphs: list[BezierGlyph]) -> list[BezierGlyph]

apps/api/src/aerocloud_api/
├── __init__.py              # version
├── app.py                   # FastAPI() instance, lifespan, router includes
├── routes/
│   ├── render.py            # POST /render, GET /render/{task_id}/progress (SSE)
│   └── health.py            # GET /health, GET /health/internal
├── middleware/
│   └── rate_limit.py        # slowapi Limiter wiring
└── metrics.py               # prometheus-fastapi-instrumentator setup

apps/worker/src/aerocloud_worker/
├── celery_app.py            # extend: add realtime queue + task_routes + time_limit
└── tasks/
    ├── self_play.py         # existing
    └── render.py            # NEW: render_task() — full pipeline dispatch
```

### Pattern 1: Seam Carving — Energy Map + DP Seam

**What:** Pure numpy implementation. Build a word-weighted Gaussian energy map over the layout canvas, find the minimum-energy vertical seam via DP, remove it to compact whitespace.

**When to use:** After Inner/Outer Loop places words — pre-export compaction step.

**Implementation pattern (from wiki/seam-carving.md):**
```python
# Source: wiki/seam-carving.md + Avidan & Shamir 2007 pattern
import numpy as np
from scipy.ndimage import gaussian_filter

def build_energy_map(
    canvas_h: int,
    canvas_w: int,
    word_positions: list[tuple[float, float]],
    word_weights: list[float],
    sigma: float = 15.0,  # Claude's discretion — tunable
) -> np.ndarray:
    """E(x,y) = Σ wᵢ · Gauss(distance(x,y, μᵢ), σᵢ)"""
    energy = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    ys, xs = np.mgrid[0:canvas_h, 0:canvas_w]
    for (cy, cx), w in zip(word_positions, word_weights):
        dist_sq = (ys - cy) ** 2 + (xs - cx) ** 2
        energy += w * np.exp(-dist_sq / (2 * sigma ** 2))
    return energy

def find_vertical_seam(energy: np.ndarray) -> np.ndarray:
    """DP optimal seam O(w*h). Returns column indices per row."""
    h, w = energy.shape
    M = energy.copy()
    for row in range(1, h):
        for col in range(w):
            lo = max(0, col - 1)
            hi = min(w - 1, col + 1)
            M[row, col] += M[row - 1, lo : hi + 1].min()
    # backtrack
    seam = np.empty(h, dtype=np.int32)
    seam[-1] = int(np.argmin(M[-1]))
    for row in range(h - 2, -1, -1):
        col = seam[row + 1]
        lo, hi = max(0, col - 1), min(w - 1, col + 1)
        seam[row] = lo + int(np.argmin(M[row, lo : hi + 1]))
    return seam
```

**Note:** Vectorize the inner loop with `np.minimum.reduce` on shifted rows for O(w*h) without Python for-loop over rows.

### Pattern 2: SVG Export from BezierGlyph

**What:** Convert BezierGlyph cubic Bezier segments (y,x internal) to SVG `<path>` `C` commands (x,y external). The coordinate flip happens ONLY at export boundary (D-03, documented in bezier.py).

```python
# Source: packages/engine/src/aerocloud/geometry/bezier.py coordinate convention
# [VERIFIED: bezier.py docstring — (y,x) internal, flip at export]

def bezier_curve_to_svg_cmd(curve: BezierCurve) -> str:
    """Cubic Bezier segment to SVG 'C' command. Flip (y,x) → (x,y)."""
    def fmt(p: tuple[float, float]) -> str:
        y, x = p
        return f"{x:.6f},{y:.6f}"  # SVG uses (x,y)
    return (
        f"C {fmt(curve.p1)} {fmt(curve.p2)} {fmt(curve.p3)}"
    )

def glyph_to_svg_path(glyph: BezierGlyph) -> str:
    paths = []
    for contour in glyph.contours:
        if not contour:
            continue
        y0, x0 = contour[0].p0
        cmds = [f"M {x0:.6f},{y0:.6f}"]
        cmds += [bezier_curve_to_svg_cmd(c) for c in contour]
        cmds.append("Z")
        paths.append(" ".join(cmds))
    return " ".join(paths)
```

**svgelements usage for full SVG document:**
```python
# Source: [ASSUMED] — svgelements 1.9.6 API based on library docs
from svgelements import SVGElement, Path, SVG

def export_svg(placed_glyphs: list[BezierGlyph], width: int, height: int) -> str:
    svg = SVG(width=width, height=height)
    for glyph in placed_glyphs:
        path_d = glyph_to_svg_path(glyph)
        svg.append(Path(path_d))
    return svg.write_xml()
```

**Critical:** The `svgelements` library uses `write_xml()` or string serialization. For simple path-only SVG, direct `lxml.etree` assembly is a viable fallback if the svgelements API differs.
[ASSUMED — verify svgelements exact API at implementation time. Library is in geometry deps at 1.9.6 but not currently installed in venv.]

### Pattern 3: PDF Export via ReportLab

**What:** BezierGlyph cubic segments → ReportLab `canvas.bezierCurveTo()`. ReportLab uses 72 DPI user-space by default; convert pixel coordinates to points (pt = px * 72/dpi).

```python
# Source: [ASSUMED] — ReportLab 4.x API (bezierCurveTo signature stable since v3)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import mm

DPI = 300  # print resolution
PX_TO_PT = 72.0 / DPI  # sub-millimeter: 300 DPI → 0.24pt per pixel

def export_pdf(placed_glyphs: list[BezierGlyph], width_px: int, height_px: int) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_px * PX_TO_PT, height_px * PX_TO_PT))
    for glyph in placed_glyphs:
        for contour in glyph.contours:
            if not contour:
                continue
            c.beginPath()
            y0, x0 = contour[0].p0
            c.moveTo(x0 * PX_TO_PT, y0 * PX_TO_PT)
            for curve in contour:
                # flip (y,x) → (x,y) and scale to pt
                _, x1 = curve.p1; _, y1 = curve.p1  # wrong — destructure properly
                c.bezierCurveTo(
                    curve.p1[1] * PX_TO_PT, curve.p1[0] * PX_TO_PT,
                    curve.p2[1] * PX_TO_PT, curve.p2[0] * PX_TO_PT,
                    curve.p3[1] * PX_TO_PT, curve.p3[0] * PX_TO_PT,
                )
            c.closePath()
            c.drawPath(c._currentPath, fill=1, stroke=0)
    c.save()
    return buf.getvalue()
```

**Sub-millimeter guarantee:** At 300 DPI, 1px = 0.0846mm. `float64` control points (already guaranteed by BezierCurve type) provide <0.001mm precision.

### Pattern 4: Boolean Union via Shapely

**What:** Convert BezierGlyph contours → Shapely Polygon (via `shapely.geometry.Polygon`), compute `unary_union`, convert back.

**Key constraint:** Shapely operates on polygonal approximations of curves. For word outlines, the Bezier curves must be densely sampled (tessellated) before `Polygon()` construction.

```python
# Source: [ASSUMED] — shapely 2.x API (shapely.ops.unary_union stable since 1.8)
from shapely.geometry import Polygon
from shapely.ops import unary_union
import numpy as np

def bezier_curve_to_points(curve: BezierCurve, n: int = 20) -> list[tuple[float, float]]:
    """Tessellate one cubic segment into n+1 (x,y) points."""
    t = np.linspace(0, 1, n + 1)
    p0, p1, p2, p3 = (np.array([c[1], c[0]]) for c in [curve.p0, curve.p1, curve.p2, curve.p3])
    # De Casteljau / cubic Bezier formula
    pts = (
        (1-t)**3 * p0[:, None] +
        3*(1-t)**2*t * p1[:, None] +
        3*(1-t)*t**2 * p2[:, None] +
        t**3 * p3[:, None]
    )  # shape (2, n+1): [x_coords, y_coords]
    return list(zip(pts[0], pts[1]))

def glyph_to_polygon(glyph: BezierGlyph) -> Polygon | None:
    if not glyph.contours:
        return None
    outer = []
    for c in glyph.contours[0]:
        outer.extend(bezier_curve_to_points(c))
    holes = []
    for contour in glyph.contours[1:]:
        hole = []
        for c in contour:
            hole.extend(bezier_curve_to_points(c))
        holes.append(hole)
    return Polygon(outer, holes)

def union_glyphs(glyphs: list[BezierGlyph]) -> Polygon:
    polygons = [p for g in glyphs if (p := glyph_to_polygon(g)) is not None]
    return unary_union(polygons)
```

**Anti-pattern:** Do NOT try to reconstruct BezierGlyph from the shapely union polygon — the result is a simplified polygon, not a Bezier representation. Use the shapely polygon directly for printing mask generation (SVG polygon element) rather than converting back to cubic Bezier.

### Pattern 5: FastAPI POST /render + SSE Progress

**What:** `POST /render` dispatches Celery task, returns `task_id`. `GET /render/{task_id}/progress` streams Celery progress updates via Redis pub/sub using `StreamingResponse` + `sse-starlette`.

```python
# Source: [ASSUMED] — FastAPI + sse-starlette 3.x pattern (stable SSE API)
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis
import json

async def render_progress_stream(task_id: str, redis_url: str):
    """Async generator — yields SSE events from Redis pub/sub."""
    redis = aioredis.from_url(redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"render:progress:{task_id}")
    heartbeat_interval = 15  # seconds — Claude's discretion
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield {"data": json.dumps(data), "event": "progress"}
                if data.get("status") in ("SUCCESS", "FAILURE"):
                    break
    finally:
        await pubsub.unsubscribe(f"render:progress:{task_id}")
        await redis.aclose()

@app.get("/render/{task_id}/progress")
async def render_progress(task_id: str):
    return EventSourceResponse(
        render_progress_stream(task_id, settings.redis_url),
        ping=15,  # heartbeat in seconds — Claude's discretion
    )
```

**Celery task publishes progress:**
```python
# In render task — publish to Redis channel
import redis as sync_redis
import json

def publish_progress(task_id: str, payload: dict, redis_url: str) -> None:
    r = sync_redis.from_url(redis_url)
    r.publish(f"render:progress:{task_id}", json.dumps(payload))
```

### Pattern 6: slowapi Rate Limiting

```python
# Source: [ASSUMED] — slowapi 0.1.9 standard usage pattern
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,  # Redis-backed
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/render")
@limiter.limit("10/minute")  # per-IP; override with per-shop key_func
async def post_render(request: Request, body: RenderRequest):
    ...
```

**Per-shop rate limiting:** Override `key_func` to extract shop identifier from request headers (passed by Shopify session token context) rather than IP.

### Pattern 7: Prometheus Instrumentation

```python
# Source: [ASSUMED] — prometheus-fastapi-instrumentator 7.x standard setup
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, make_asgi_app

# Auto-instrument all routes
Instrumentator().instrument(app).expose(app)

# Custom metrics (Claude's discretion for names)
render_duration = Histogram(
    "aerocloud_render_duration_seconds",
    "End-to-end render latency",
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
)
render_total = Counter(
    "aerocloud_renders_total",
    "Total renders by status",
    labelnames=["status"],  # success, failure, timeout
)
```

### Pattern 8: OTel OTLP Upgrade

The existing `observability.py` initializes a `TracerProvider` with no exporter (NoOp). Upgrade adds `OTLPSpanExporter`:

```python
# Source: packages/engine/src/aerocloud/observability.py (verified — explicit Phase 12 TODO)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def init_tracing(
    service_name: str = "aerocloud-engine",
    otlp_endpoint: str | None = None,
) -> None:
    ...
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
```

`otlp_endpoint` comes from `Settings` (new field: `otlp_endpoint: str | None = None`).

### Pattern 9: Celery Graceful Shutdown

```python
# Source: [ASSUMED] — Celery 5.x worker signals (stable API since 4.x)
# [CITED: https://docs.celeryq.dev/en/stable/userguide/signals.html#worker-shutting-down]
from celery.signals import worker_shutting_down
import structlog

log = structlog.get_logger()

@worker_shutting_down.connect
def on_worker_shutting_down(sig: str, how: str, exitcode: int, **kwargs: object) -> None:
    log.info("worker.shutting_down", sig=sig, how=how, exitcode=exitcode)
    # Flush any in-flight archive writes here
    # ulimit -c 0 is set in entrypoint, not here
```

**Dockerfile pattern:**
```dockerfile
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD celery -A aerocloud_worker.celery_app inspect ping -t 5 || exit 1
```

**Entrypoint:**
```bash
#!/bin/sh
ulimit -c 0  # D-24: core dumps disabled per CLAUDE.md §12
exec celery -A aerocloud_worker.celery_app worker \
    --pool=prefork \
    --concurrency=1 \
    --max-tasks-per-child=50 \
    --queues=realtime,background \
    --loglevel=info
```

### Pattern 10: Golden-Image SSIM Test

```python
# Source: [ASSUMED] — scikit-image 0.26 skimage.metrics.structural_similarity
from skimage.metrics import structural_similarity as ssim
import numpy as np
from PIL import Image
import pytest

SSIM_THRESHOLD = 0.95  # D-27 locked floor; exact value Claude's discretion

FIXTURES = ["circle", "square", "star", "crescent"]

@pytest.mark.parametrize("fixture_name", FIXTURES)
def test_golden_image_ssim(fixture_name: str, tmp_path):
    golden_path = Path(__file__).parent / "golden" / f"{fixture_name}.png"
    golden = np.array(Image.open(golden_path).convert("L"))

    # Run renderer with known seed
    rendered = run_renderer(fixture_name, seed=42)  # returns np.ndarray (H, W)

    score = ssim(golden, rendered, data_range=255)
    assert score >= SSIM_THRESHOLD, (
        f"{fixture_name}: SSIM {score:.4f} < threshold {SSIM_THRESHOLD}"
    )
```

**Golden image generation:** Run once with `--generate-goldens` flag, commit to `tests/regression/golden/`.

### Pattern 11: Realtime Queue Wiring in celery_app.py

The existing `celery_app.py` only routes `self_play.*` to `background`. Phase 12 adds the `realtime` queue and the render task route:

```python
# Extension of existing apps/worker/src/aerocloud_worker/celery_app.py
app.conf.task_routes = {
    "aerocloud_worker.tasks.self_play.*": {"queue": "background"},
    "aerocloud_worker.tasks.render.*": {"queue": "realtime"},  # NEW
}

# Task time limits (D-13)
app.conf.task_time_limit = 300         # realtime hard limit: 5 min
app.conf.task_soft_time_limit = 28800  # background soft limit: 8h
```

### Pattern 12: DCGM Exporter Docker Sidecar

```yaml
# Addition to infra/docker/docker-compose.yml
services:
  dcgm-exporter:
    image: nvcr.io/nvidia/k8s/dcgm-exporter:3.6.2-3.4.2-ubuntu22.04
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    ports:
      - "9400:9400"
    cap_add:
      - SYS_ADMIN
    depends_on:
      - worker
```

**Note:** DCGM Exporter 3.6.2 introduced a label rename: `container_name` → `k8s_container_name` [CITED: wiki/research/nightly/2026-04-11-nvidia-dcgm-exporter-gpu-metrics.md]. This affects Prometheus scrape config label selectors if written before upgrading. Use the current 3.6.2 image tag and the new label names from the start.

**Security note:** CVE-2026-2184 affects DCGM Runtime < 3.3.6. The 3.6.2 image includes a patched DCGM daemon. [CITED: wiki/research/nightly/2026-04-11-nvidia-dcgm-exporter-gpu-metrics.md — LOW confidence: nightly research, not official advisory confirmed].

### Anti-Patterns to Avoid

- **CUDA forking with non-prefork pools:** `--pool=gevent` or `--pool=eventlet` will corrupt CUDA context after fork. `--pool=prefork` with `--concurrency=1` is mandatory. [CITED: wiki/research/nightly/2026-04-11-celery-gpu-worker-pool-management.md]
- **Blocking `asyncio.gather` in FastAPI route:** The `/render` endpoint must dispatch to Celery and return immediately. Never `await` the render task inline.
- **CORS enabled:** CLAUDE.md §12 explicitly forbids CORS — this is a server-to-server API.
- **Raw file paths in API:** `shape_b64` field already enforces base64 binary. Never add a `mask_path: str` field.
- **BezierGlyph back-conversion after shapely union:** The union result is a Polygon, not Bezier. Expose it as SVG `<polygon>` or as a tessellated path.
- **Per-request font registration:** `fonts.py` already registers fonts once at module level. Do not re-register per render task.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting state | Custom Redis counter in middleware | `slowapi` 0.1.9 | Handles token bucket, sliding window, error responses correctly |
| SSE heartbeat + keep-alive | Manual `asyncio.sleep` loop | `sse-starlette` 3.3.4 | Handles client disconnect, ping frames, content-type negotiation |
| Prometheus metric scrape endpoint | Manual `/metrics` route | `prometheus-fastapi-instrumentator` | Auto-instruments latency/status histograms; thread-safe registry |
| SSIM image comparison | Pixel MSE diff | `skimage.metrics.structural_similarity` | Perceptual similarity, handles luminance/contrast/structure separately |
| Celery task pub/sub | Custom polling loop | Redis pub/sub via `redis.asyncio` | Zero-latency push vs polling; Celery tasks publish on state change |
| Boolean polygon union | Custom Sutherland-Hodgman | `shapely.ops.unary_union` | GEOS 3.12 handles degenerate cases, self-intersections, holes correctly |

**Key insight:** Phase 12 is an integration phase. Every non-domain problem (rate limiting, SSE, metrics, SSIM) has a mature library. Hand-rolling any of these introduces security edge cases and delays the release gate.

---

## Common Pitfalls

### Pitfall 1: CUDA Fork Safety with Celery Prefork
**What goes wrong:** If PyTorch CUDA tensors are initialized in the Celery main process before forking workers, child processes inherit a corrupt CUDA context.
**Why it happens:** CUDA drivers are not fork-safe. The parent process's CUDA handles are invalid in child processes.
**How to avoid:** Import `torch` and call `torch.cuda.is_available()` only inside the Celery task function, never at module top-level in the worker process. The `--max-tasks-per-child=50` setting ensures the forked worker process exits after 50 tasks, freeing GPU memory via OS process exit.
**Warning signs:** `RuntimeError: Cannot re-initialize CUDA in forked subprocess`, GPU memory not released after task completion.

### Pitfall 2: BezierGlyph Coordinate Flip
**What goes wrong:** SVG and PDF use (x, y) coordinate order; BezierGlyph stores (y, x) per D-14. Forgetting to flip produces mirrored/transposed output.
**Why it happens:** cv2 returns (x, y) and bezier.py flips to (y, x) for internal row-major consistency (documented in bezier.py docstring).
**How to avoid:** The flip must happen exactly once, at the export boundary — in `svg_export.py` and `pdf_export.py`. A test with an asymmetric fixture (e.g., letter "F") will catch this immediately.
**Warning signs:** Exported glyphs appear mirrored or rotated 90 degrees.

### Pitfall 3: Seam Carving Removes Words
**What goes wrong:** A seam passes through a word's bounding box, visually cutting off a character.
**Why it happens:** The energy map has insufficient weight around word centers, or sigma is too small for the word size.
**How to avoid:** Word energy sigma should scale with word bounding box size: `sigma_i = max(bbox_w, bbox_h) * 0.5`. Words must be protected — the seam algorithm should treat word bounding boxes as infinite-energy walls. Add a test asserting that no seam pixel falls within any word's AABB.
**Warning signs:** Exported SVG shows partial characters; SSIM test fails on regression.

### Pitfall 4: SSE Connection Leak
**What goes wrong:** Redis pub/sub subscriptions accumulate if SSE clients disconnect without proper cleanup.
**Why it happens:** `asyncio` cancellation during `async for` leaves the Redis connection open.
**How to avoid:** Wrap the generator in `try/finally` and call `await pubsub.unsubscribe()` + `await redis.aclose()` in the `finally` block. `sse-starlette` handles the client disconnect signal via `asyncio.CancelledError`.
**Warning signs:** Redis connection count grows monotonically under load; `INFO clients connected=N` in Redis logs grows unbounded.

### Pitfall 5: Prometheus Registry Double-Registration
**What goes wrong:** `Counter("aerocloud_renders_total", ...)` raises `ValueError: Duplicated timeseries` when the FastAPI app is imported twice (e.g., during pytest collection).
**Why it happens:** `prometheus-client` has a global default registry. Re-importing the metrics module creates duplicate registrations.
**How to avoid:** Wrap metric creation with a try/except or use `prometheus_client.REGISTRY.get_sample_value()` to check before creating. Alternatively, use a module-level singleton pattern with `_metrics: dict[str, Any] = {}`.
**Warning signs:** `ValueError: Duplicated timeseries` in test logs; tests pass individually but fail when run as a suite.

### Pitfall 6: ReportLab Y-Axis Inversion
**What goes wrong:** ReportLab's coordinate system has Y=0 at the bottom-left (PDF convention), while pixel coordinates have Y=0 at the top-left.
**Why it happens:** PDF/PostScript heritage — Y increases upward.
**How to avoid:** Transform: `pdf_y = page_height_pt - pixel_y * PX_TO_PT`. Add to every Y coordinate before passing to ReportLab. A test rendering a single glyph with known position and checking visual placement catches this.
**Warning signs:** Glyphs appear vertically flipped in PDF output.

### Pitfall 7: slowapi and FastAPI lifespan
**What goes wrong:** `slowapi` limiter must be attached to `app.state` before routes are included, or rate limiting silently does nothing.
**Why it happens:** `slowapi` uses `request.app.state.limiter` at request time.
**How to avoid:** Attach `limiter` to `app.state` in the lifespan context (or before router includes), not inside a route handler.

---

## Code Examples

### Verified Patterns from Codebase

#### RenderRequest model (models/api.py — VERIFIED)
```python
class RenderRequest(AeroCloudBase):
    text: str = Field(..., min_length=1, max_length=50_000)
    shape_b64: str = Field(..., description="Base64-encoded silhouette mask PNG")
    width: int = Field(default=1024, gt=0, le=4096)
    height: int = Field(default=1024, gt=0, le=4096)
    seed: int = Field(default=42, ge=0)
    max_words: int = Field(default=200, gt=0, le=2000)
    font_family: str = Field(default="Inter")
```

#### Pydantic validators for security (D-15, D-16)
```python
import re
from pathlib import Path
from pydantic import field_validator

FONT_ALLOW_LIST: frozenset[str] = frozenset()  # populated at startup from assets/fonts/

class RenderRequest(AeroCloudBase):
    ...
    color: str = Field(default="#000000")
    font_family: str = Field(default="Inter")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.fullmatch(r"^#[0-9a-fA-F]{3,8}$", v):
            raise ValueError(f"Invalid color: {v!r}")
        return v

    @field_validator("font_family")
    @classmethod
    def validate_font_family(cls, v: str) -> str:
        if FONT_ALLOW_LIST and v not in FONT_ALLOW_LIST:
            raise ValueError(f"Font not registered: {v!r}")
        return v
```

#### Celery task with time_limit (D-12, D-13)
```python
# Source: celery_app.py pattern (VERIFIED existing) + Phase 12 additions
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

@shared_task(
    bind=True,
    name="aerocloud_worker.tasks.render.render_task",
    time_limit=300,        # D-13: hard kill after 5 min
    soft_time_limit=270,   # warn at 4.5 min
    max_retries=0,         # no retry for GPU tasks
    queue="realtime",
)
def render_task(self, request_dict: dict) -> dict:
    task_id = self.request.id
    try:
        # ... full pipeline call
        publish_progress(task_id, {"status": "SUCCESS", "result": result}, REDIS_URL)
        return result
    except SoftTimeLimitExceeded:
        publish_progress(task_id, {"status": "TIMEOUT"}, REDIS_URL)
        raise
    except Exception as exc:
        publish_progress(task_id, {"status": "FAILURE", "error": str(exc)}, REDIS_URL)
        raise
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery `--pool=solo` for GPU | `--pool=prefork --concurrency=1` | April 2026 best practice | Prefork gives true process isolation; solo pool runs in main process (no isolation) |
| OTel synchronous exporter | `BatchSpanProcessor` + OTLP | OTel SDK stable | Async batching prevents latency spikes on export |
| svgwrite (inactive) | svgelements 1.9.6 | 2022 (svgwrite abandoned) | Already in deps — confirmed choice |
| Manual SSIM comparison | `skimage.metrics.structural_similarity` | scikit-image 0.19+ | Standard perceptual metric, handles structural/luminance/contrast |
| DCGM Exporter label `container_name` | `k8s_container_name` | DCGM 3.6.2 (April 10, 2026) | Breaking label change — use new label in Prometheus selectors |

**Deprecated/outdated:**
- `--pool=solo`: Runs task in worker main process, no fork. No GPU isolation. Replaced by `--pool=prefork --concurrency=1`.
- Synchronous OTel exporter (`SimpleSpanProcessor`): Adds latency to every span. Use `BatchSpanProcessor` always.
- `prometheus_client.start_http_server()`: Manual pattern. Use `prometheus-fastapi-instrumentator` instead for FastAPI integration.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `svgelements` API uses `SVG()`, `Path()`, `.write_xml()` for SVG document construction | Architecture Patterns §SVG Export | Implementation needs library docs check; lxml.etree fallback always available |
| A2 | `reportlab` `canvas.bezierCurveTo()` is the correct method name for cubic Bezier | Architecture Patterns §PDF Export | Actual method may be `curveTo()`; verify in reportlab 4.4.10 docs |
| A3 | `sse-starlette 3.3.4` `EventSourceResponse` accepts an async generator directly | Architecture Patterns §SSE | Older versions used different interface; verify at install |
| A4 | `shapely.ops.unary_union` handles self-intersecting input gracefully | Architecture Patterns §Boolean Union | May raise TopologicalError on degenerate glyphs; need `.buffer(0)` cleanup |
| A5 | DCGM CVE-2026-2184 is fixed in 3.6.2 image | Architecture Patterns §DCGM | Nightly research claim — not independently verified against NVIDIA advisory |
| A6 | `skimage.metrics.structural_similarity` default `win_size` works for 64px test fixtures | Golden Image Tests | May need `win_size=7` parameter for small images; verify empirically |

---

## Open Questions

1. **P99 latency budget**
   - What we know: Phase 12 success criteria says "P99 within agreed budget for 200 words"
   - What's unclear: The specific latency budget number is not defined in CONTEXT.md or REQUIREMENTS.md
   - Recommendation: Establish budget during Wave 0 based on initial load test baseline. Suggest: < 30s P99 for 200 words at 1024x1024 on available GPU. Capture as a constant in test config.

2. **svgelements exact document construction API**
   - What we know: svgelements 1.9.6 is declared in geometry deps but not installed in current venv
   - What's unclear: Exact method for creating SVG root element and appending Path objects
   - Recommendation: Install and test locally at Wave 0. Fallback: direct `lxml.etree` SVG assembly requires no API lookup.

3. **Font allow-list initialization timing**
   - What we know: `FONT_ALLOW_LIST` must be populated from `assets/fonts/` directory
   - What's unclear: Should this happen in FastAPI lifespan, at module import, or in the Pydantic model class body?
   - Recommendation: Use FastAPI `lifespan` context manager to scan fonts directory and populate a module-level `frozenset`. Avoid class-body evaluation (runs at import time, before assets are available in Docker).

4. **Load test tool**
   - What we know: `locust` is not installed; `httpx` 0.28.1 is installed
   - What's unclear: Whether a locust-based test is required for PROD-22 or whether an httpx/asyncio script suffices
   - Recommendation: Implement PROD-22 as a pytest-marked `@pytest.mark.slow` test using `asyncio.gather` with 100 concurrent `httpx.AsyncClient.post()` calls. This requires no additional dependency and is reproducible in CI. Locust can be added later if interactive load testing is needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | DCGM sidecar, container build | ✓ | 29.3.0 | — |
| CUDA GPU | GPU isolation (D-11, D-14) | ✗ (VPS: CPU only) | — | Tests marked `@pytest.mark.gpu`, skipped on CPU host |
| nvidia-smi | GPU monitoring | ✗ | — | DCGM tests skipped on non-GPU host |
| FastAPI | POST /render | ✓ | 0.135.3 | — |
| Celery | Task queue | ✓ | 5.6.3 | — |
| Redis | Broker + pub/sub | ✓ (via docker-compose) | 7-alpine | — |
| Pillow | PNG export | ✓ | 12.2.0 | — |
| scipy | Seam carving vectorization | ✓ | 1.17.1 | — |
| httpx | Load test | ✓ | 0.28.1 | — |
| shapely | Boolean union | ✗ | 2.1.2 on PyPI | — (must install) |
| slowapi | Rate limiting | ✗ | 0.1.9 on PyPI | — (must install) |
| prometheus-client | Metrics | ✗ | 0.25.0 on PyPI | — (must install) |
| prometheus-fastapi-instrumentator | Auto metrics | ✗ | 7.1.0 on PyPI | — (must install) |
| opentelemetry-exporter-otlp | OTLP tracing | ✗ | 1.41.0 on PyPI | Stays NoOp (degraded observability) |
| sse-starlette | SSE streaming | ✗ | 3.3.4 on PyPI | — (must install) |
| scikit-image | SSIM golden tests | ✗ | 0.26.0 on PyPI | Manual pixel diff (less reliable) |
| locust | Load test (optional) | ✗ | 2.43.4 on PyPI | httpx (already installed — use this) |

**Missing dependencies blocking implementation (must install):**
- `shapely>=2.1.2` — PROD-06 boolean union is a hard requirement
- `slowapi>=0.1.9` — PROD-16 rate limiting
- `prometheus-client>=0.25.0` + `prometheus-fastapi-instrumentator>=7.1.0` — PROD-19
- `sse-starlette>=3.3.4` — PROD-08 SSE endpoint

**Missing dependencies with fallback:**
- `opentelemetry-exporter-otlp` — system degrades to NoOp tracing if not installed; install anyway per D-19
- `scikit-image` — SSIM fallback is pixel MSE; scikit-image is strongly preferred for PROD-21
- `locust` — httpx async is the preferred fallback for PROD-22

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + hypothesis 6.120.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest packages/engine/tests/ apps/api/tests/ apps/worker/tests/ -x -q` |
| Full suite command | `pytest packages/engine/tests/ apps/api/tests/ apps/worker/tests/ -v --hypothesis-profile=ci` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-01 | Energy map produces positive values at word positions | unit | `pytest packages/engine/tests/export/test_seam_carving.py::test_energy_map_peak_at_word -x` | ❌ Wave 0 |
| PROD-02 | DP seam avoids word positions | unit | `pytest packages/engine/tests/export/test_seam_carving.py::test_seam_avoids_words -x` | ❌ Wave 0 |
| PROD-03 | SVG output contains valid `<path>` elements | unit | `pytest packages/engine/tests/export/test_svg_export.py -x` | ❌ Wave 0 |
| PROD-04 | PDF output is parseable PDF with path ops | unit | `pytest packages/engine/tests/export/test_pdf_export.py -x` | ❌ Wave 0 |
| PROD-05 | PNG output has correct shape and dtype | unit | `pytest packages/engine/tests/export/test_png_export.py -x` | ❌ Wave 0 |
| PROD-06 | Boolean union reduces path count for overlapping glyphs | unit | `pytest packages/engine/tests/export/test_boolean_union.py -x` | ❌ Wave 0 |
| PROD-07 | POST /render returns 202 with task_id | integration | `pytest apps/api/tests/test_render_route.py::test_post_render_202 -x` | ❌ Wave 0 |
| PROD-08 | SSE endpoint streams progress events | integration | `pytest apps/api/tests/test_sse.py -x` | ❌ Wave 0 |
| PROD-09 | Worker starts with prefork pool, concurrency=1 | smoke | `pytest apps/worker/tests/test_worker_config.py -x` | ❌ Wave 0 |
| PROD-10 | render.* routes to realtime queue | unit | `pytest apps/worker/tests/test_celery_app.py::test_task_routes -x` | ❌ Wave 0 |
| PROD-11 | CUDA_VISIBLE_DEVICES is set before torch import | unit | `pytest apps/worker/tests/test_gpu_isolation.py -x` | ❌ Wave 0 |
| PROD-12 | Task exceeding time_limit is killed | integration `@pytest.mark.slow` | `pytest apps/worker/tests/test_timeout.py -x -m slow` | ❌ Wave 0 |
| PROD-13 | Invalid SVG color returns HTTP 400 | unit | `pytest apps/api/tests/test_render_route.py::test_invalid_color_400 -x` | ❌ Wave 0 |
| PROD-14 | Unknown font returns HTTP 400 | unit | `pytest apps/api/tests/test_render_route.py::test_unknown_font_400 -x` | ❌ Wave 0 |
| PROD-15 | shape_b64 accepts base64 PNG, rejects raw path | unit | `pytest apps/api/tests/test_render_route.py::test_path_traversal_rejected -x` | ❌ Wave 0 |
| PROD-16 | 11th request in 1 minute returns 429 | integration | `pytest apps/api/tests/test_rate_limit.py -x` | ❌ Wave 0 |
| PROD-17 | GET /health returns 200 JSON; /health/internal returns 200 with auth | unit | `pytest apps/api/tests/test_health.py -x` | ❌ Wave 0 |
| PROD-18 | OTel spans are exported (OTLP endpoint mock) | integration | `pytest apps/api/tests/test_tracing.py -x` | ❌ Wave 0 |
| PROD-19 | /metrics endpoint returns Prometheus text | unit | `pytest apps/api/tests/test_metrics.py -x` | ❌ Wave 0 |
| PROD-20 | SIGTERM drains in-flight task before exit | integration `@pytest.mark.slow` | `pytest apps/worker/tests/test_graceful_shutdown.py -x -m slow` | ❌ Wave 0 |
| PROD-21 | SSIM >= 0.95 for circle, square, star, crescent | regression | `pytest packages/engine/tests/regression/test_golden_images.py -x` | ❌ Wave 0 |
| PROD-22 | P99 < budget under 100 concurrent renders | load `@pytest.mark.slow` | `pytest tests/load/test_load.py -x -m slow` | ❌ Wave 0 |
| PROD-23 | All above green | release gate | `pytest -x -q` (full suite) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest packages/engine/tests/export/ apps/api/tests/ -x -q`
- **Per wave merge:** `pytest packages/engine/tests/ apps/api/tests/ apps/worker/tests/ -q`
- **Phase gate:** Full suite green + `mypy --strict` clean + `ruff check` clean

### Wave 0 Gaps
- [ ] `packages/engine/tests/export/__init__.py` + `test_seam_carving.py` — covers PROD-01, PROD-02
- [ ] `packages/engine/tests/export/test_svg_export.py` — covers PROD-03
- [ ] `packages/engine/tests/export/test_pdf_export.py` — covers PROD-04
- [ ] `packages/engine/tests/export/test_png_export.py` — covers PROD-05
- [ ] `packages/engine/tests/export/test_boolean_union.py` — covers PROD-06
- [ ] `apps/api/tests/__init__.py` + `test_render_route.py` — covers PROD-07, PROD-13, PROD-14, PROD-15
- [ ] `apps/api/tests/test_sse.py` — covers PROD-08
- [ ] `apps/api/tests/test_health.py` — covers PROD-17
- [ ] `apps/api/tests/test_rate_limit.py` — covers PROD-16
- [ ] `apps/api/tests/test_metrics.py` — covers PROD-19
- [ ] `apps/api/tests/test_tracing.py` — covers PROD-18
- [ ] `apps/worker/tests/test_celery_app.py` — covers PROD-09, PROD-10
- [ ] `apps/worker/tests/test_gpu_isolation.py` — covers PROD-11
- [ ] `packages/engine/tests/regression/test_golden_images.py` + `tests/regression/golden/*.png` — covers PROD-21
- [ ] `tests/load/test_load.py` — covers PROD-22
- [ ] Install deps: `uv add shapely slowapi prometheus-client prometheus-fastapi-instrumentator sse-starlette opentelemetry-exporter-otlp` + `uv add --dev scikit-image`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (/health/internal) | Bearer token from Shopify session; `authenticate.admin(request)` equivalent |
| V3 Session Management | no | Server-to-server, no sessions |
| V4 Access Control | yes | Per-shop rate limits; /health/internal auth |
| V5 Input Validation | yes | Pydantic field_validators: color regex, font allow-list, base64 mask |
| V6 Cryptography | no | No encryption in phase scope (OTel uses OTLP/gRPC with optional TLS) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SVG color injection (CSS property smuggling) | Tampering | Pydantic regex `^#[0-9a-fA-F]{3,8}$` — D-15 |
| Font path traversal | Tampering | Allow-list against `assets/fonts/` directory contents — D-16 |
| Mask upload path traversal | Tampering | base64-only input in `shape_b64` field, never a file path — D-17 |
| Rate limit bypass (IP spoofing) | DoS | Per-shop key_func (not IP-only) for production; Redis-backed — D-10 |
| SSRF via mask URL | Tampering | No URL input — binary upload only. No `requests.get()` in processing path |
| Task time runaway (cost) | DoS | Celery `time_limit=300` hard kill — D-12/D-13 |
| CUDA memory exhaustion between tasks | DoS | `--max-tasks-per-child=50` forces worker restart; `torch.cuda.empty_cache()` in task cleanup |
| Unsafe tensor deserialization | Tampering | `safetensors` only (CI lint rule from FOUND-06 / Phase 1); never `pickle.load()` |
| CORS bypass | Elevation | CORS disabled entirely per CLAUDE.md §12 — D-18 |

**SVG export output safety:** The SVG produced by `svg_export.py` is NOT user-uploaded SVG — it is generated from validated BezierGlyph data. However, if this SVG is ever served back to a browser, it must be sanitized (nh3 is already in deps). For v1 (server-to-server), raw SVG output is acceptable.

---

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md §12 (MVP Production-Hardening) apply directly to Phase 12 implementation. The planner MUST verify each task complies:

| Directive | CLAUDE.md §12 Ref | Phase 12 Manifestation |
|-----------|-------------------|----------------------|
| Health endpoints: `/health` (public) + `/health/internal` (authenticated) | §12 explicit | D-09 — both endpoints required |
| CORS disabled (server-to-server only) | §12 explicit | D-18 — no CORS middleware |
| Graceful shutdown (SIGTERM → drain → exit) | §12 explicit | D-22, D-23 — worker_shutting_down signal |
| PM2 as sole process manager | §12 implicit | Docker Compose for dev; PM2 for VPS production |
| Core dumps disabled (`ulimit -c 0`) | §12 explicit | D-24 — worker entrypoint |
| JSON-Depth-Limit, bodyLimit | §12 explicit | Uvicorn `--limit-max-requests` + FastAPI body size limit |
| `additionalProperties: false` | §12 explicit | Pydantic v2 `model_config = ConfigDict(extra="forbid")` on RenderRequest |
| Node.js CVE tracking | §12 (Node specific) | Not applicable to Python engine |
| Fastify v5 | §12 (Node specific) | Not applicable — this is Python FastAPI |
| Pre-MVP Checklist: 85 Items in 5 Gates | §12 explicit | Release gate PROD-23 covers: Security, Runtime, Load, Webhook (N/A), DSGVO |
| TDD/BDD mandatory before implementation | CLAUDE.md §3 | Every PROD requirement has a test in the test map above (Wave 0 creates them before code) |
| Tests are laws — never adapted to code | CLAUDE.md §8 | Tests must fail first; only implementation changes to make them green |
| 3-KI review (Claude + Gemini + ChatGPT) | CLAUDE.md §6 | D-27 release gate explicitly requires 3-AI review approved |
| Conventional Commits | CLAUDE.md §9 | All commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` |
| All code/comments in English | CLAUDE.md §10 | Enforce across all new Phase 12 files |

**Specific to CLAUDE.md §8 (Test Strategies):**
- Mutation tests (StrykerJS) — not applicable to Python; Mutmut or Cosmic-Ray equivalent for Python is OUT OF SCOPE for v1
- Property-based tests (hypothesis) — required for seam carving energy function and shapely union edge cases
- Security tests — Pydantic validator tests cover OWASP input validation

---

## Sources

### Primary (HIGH confidence)
- `packages/engine/src/aerocloud/geometry/bezier.py` — BezierGlyph (y,x) coordinate convention, D-14 documented
- `packages/engine/src/aerocloud/models/api.py` — RenderRequest/RenderResult verified in codebase
- `apps/worker/src/aerocloud_worker/celery_app.py` — existing queue + Beat schedule verified
- `packages/engine/pyproject.toml` — geometry optional deps (svgelements, reportlab) verified
- `apps/api/pyproject.toml` — FastAPI deps verified
- `infra/docker/docker-compose.yml` — service topology verified
- `packages/engine/src/aerocloud/observability.py` — NoOp Phase 12 TODO confirmed
- `pyproject.toml` (root) — pytest config, ruff config, mypy config verified

### Secondary (MEDIUM confidence)
- PyPI JSON API (2026-04-16): shapely 2.1.2, slowapi 0.1.9, prometheus-client 0.25.0, prometheus-fastapi-instrumentator 7.1.0, opentelemetry-exporter-otlp 1.41.0, scikit-image 0.26.0, sse-starlette 3.3.4, locust 2.43.4, svgelements 1.9.6, reportlab 4.4.10 — [VERIFIED: live PyPI]
- `wiki/seam-carving.md` — DP seam algorithm and energy function specification
- `wiki/bezier-export.md` — coordinate flip pipeline documentation
- `wiki/research/nightly/2026-04-11-celery-gpu-worker-pool-management.md` — Celery 5.6.3 prefork best practice
- `wiki/research/nightly/2026-04-11-nvidia-dcgm-exporter-gpu-metrics.md` — DCGM 3.6.2 label change

### Tertiary (LOW confidence — nightly research, not independently verified)
- DCGM CVE-2026-2184 fix in v3.6.2 — [CITED: nightly wiki] — planner should verify against official NVIDIA advisory before deploying
- Celery 5.6.3 "Silent Heartbeat Loss" fix for warm-shutdown — [CITED: nightly wiki] — matches installed version, verify against Celery changelog

---

## Metadata

**Confidence breakdown:**
- Standard stack (installed libs): HIGH — verified via `uv pip list` against live venv
- New dependencies (not installed): HIGH — verified via PyPI JSON API, 2026-04-16
- Architecture patterns: MEDIUM — Celery/FastAPI patterns standard; svgelements/reportlab API [ASSUMED] pending install
- Pitfalls: HIGH — CUDA fork safety and ReportLab Y-flip are well-known, verified by codebase comments
- Security domain: HIGH — CLAUDE.md directives are authoritative; Pydantic validator patterns are standard

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable stack — PyPI versions may drift but patterns remain valid)
