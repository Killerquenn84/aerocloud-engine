# Phase 12: Production v1 - Context

**Gathered:** 2026-04-21 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Full FastAPI + Celery + Redis + pgvector deployment with Seam Carving + Bezier export, security hardening, performance budget validated. This is the final phase — everything integrates into a deployable production system.

Requirements: PROD-01 to PROD-23.

</domain>

<decisions>
## Implementation Decisions

### Export Pipeline (Seam Carving + SVG/PDF/PNG)
- **D-01:** New `export/` subpackage in `packages/engine/src/aerocloud/export/`. Modules: `seam_carving.py`, `svg_export.py`, `pdf_export.py`, `png_export.py`, `boolean_union.py`.
- **D-02:** Seam Carving energy function: custom `E(x,y) = sum(w_i * Gauss(distance))` with word-weight-aware energy map. DP optimal seam O(w*h). Pure Python + numpy.
- **D-03:** SVG export via `svgelements` (already in deps). BezierGlyph → SVG `<path>` elements. Coordinate flip (y,x) → (x,y) at export boundary.
- **D-04:** PDF export via `reportlab` (already in deps). Sub-millimeter precision. BezierGlyph → ReportLab path operations.
- **D-05:** PNG export via `Pillow` from rendered tensors. `(tensor * 255).byte().numpy()` → `Image.fromarray()`.
- **D-06:** Boolean union on Bezier paths via `shapely` (add to deps) for polygon union. Prevents double cuts in print. Convert BezierGlyph → Shapely polygon, union, convert back.

### FastAPI HTTP Surface
- **D-07:** FastAPI app in `apps/api/` (already scaffolded). `POST /render` with Pydantic `RenderRequest` schema.
- **D-08:** Returns `task_id` immediately. SSE endpoint `GET /render/{task_id}/progress` via `StreamingResponse` with Redis pub/sub for Celery task progress relay.
- **D-09:** Health endpoints: `GET /health` (public, no auth) and `GET /health/internal` (authenticated, detailed).
- **D-10:** Rate limiting via `slowapi` (Redis-backed token bucket). Per-shop rate limits from Shopify session token.

### Celery Worker Configuration
- **D-11:** `--pool=prefork`, `--concurrency=1`, `--max-tasks-per-child=50`. Prefork for GPU memory isolation.
- **D-12:** Two queues: `realtime` (live API renders, priority) and `background` (Self-Play nightly, low priority). Route via `task_routes` in celery_app.py.
- **D-13:** Hard task timeout: `time_limit=300` (5 min) for realtime renders. `soft_time_limit=28800` for background (8h).
- **D-14:** GPU resource isolation: one worker per GPU. `CUDA_VISIBLE_DEVICES` env var per worker instance.

### Security Hardening
- **D-15:** SVG color allow-list: `^#[0-9a-fA-F]{3,8}$` regex validation in Pydantic model.
- **D-16:** Font name allow-list: validate against registered fonts in `assets/fonts/`.
- **D-17:** Path traversal prevention: Pydantic validators on all file-like inputs. No raw file paths in API — binary upload only.
- **D-18:** CORS disabled (server-to-server only per CLAUDE.md §12).

### Observability
- **D-19:** Upgrade observability.py NoOp → OTLP exporter for distributed tracing (FastAPI → Celery → GPU worker).
- **D-20:** Prometheus metrics via `prometheus-client` + `prometheus-fastapi-instrumentator`. Separate from OTel.
- **D-21:** NVIDIA DCGM Exporter as Docker sidecar container in docker-compose.yml.

### Graceful Shutdown + Hardening
- **D-22:** SIGTERM handler in worker: drain in-flight tasks, flush archive, exit 0. `worker_shutting_down` Celery signal.
- **D-23:** Dockerfile: `STOPSIGNAL SIGTERM`, health check on worker.
- **D-24:** `ulimit -c 0` in worker entrypoint (core dumps disabled per CLAUDE.md §12).

### Testing & Release Gate
- **D-25:** Golden-image regression tests: circle, square, star, crescent fixtures. Compare rendered output against golden .png files with SSIM threshold.
- **D-26:** Load test: 100 concurrent renders via `locust` or `httpx` async. Measure P99 latency.
- **D-27:** Release gate: all tests green, P99 within budget, SSIM > 0.95, 3-KI review approved.

### Claude's Discretion
- Seam carving Gaussian sigma parameter
- SSE heartbeat interval
- Prometheus metric names and labels
- Load test ramp-up pattern
- Golden image SSIM threshold exact value

</decisions>

<canonical_refs>
## Canonical References

### Export
- `packages/engine/src/aerocloud/geometry/bezier.py` — BezierGlyph, glyph_to_bezier(), (y,x) coordinates
- `packages/engine/src/aerocloud/renderer/_renderer.py` — DifferentiableRenderer forward() → tensor output
- `wiki/seam-carving.md` — Seam carving algorithm description
- `wiki/bezier-export.md` — Bezier export pipeline

### API & Worker
- `apps/api/pyproject.toml` — FastAPI + uvicorn deps
- `apps/worker/src/aerocloud_worker/celery_app.py` — Celery app + Beat + queue config
- `packages/engine/src/aerocloud/models/api.py` — RenderRequest, RenderResult Pydantic models
- `infra/docker/docker-compose.yml` — Service orchestration

### Security & Observability
- `packages/engine/src/aerocloud/observability.py` — OTel NoOp (upgrade to OTLP here)
- `CLAUDE.md §12` — MVP Production-Hardening rules (85 items, 5 gates)
- `wiki/research/nightly/2026-04-18-svg-sanitization-security-cve.md` — SVG CVE context

### Existing Patterns
- `packages/engine/src/aerocloud/config.py` — AeroCloudSettings
- `packages/engine/src/aerocloud/utils/determinism.py` — set_seed()
- `packages/engine/src/aerocloud/self_play/replay.py` — asyncpg persistence pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- BezierGlyph model from Phase 7 — SVG/PDF export input ready
- DifferentiableRenderer forward() — PNG export source
- Celery app from Phase 10 — extend with realtime queue + render task
- asyncpg persistence pattern — reuse for task progress tracking
- RenderRequest/RenderResult models — already defined in models/api.py
- export/ directory — already created in Phase 1 scaffolding

### Integration Points
- NLP pipeline → Renderer → Inner Loop → Outer Loop → Export (full pipeline)
- FastAPI dispatches to Celery which calls the full engine pipeline
- SSE streams progress from Celery task back to client via Redis pub/sub
- Prometheus scrapes /metrics, DCGM Exporter scrapes GPU metrics

</code_context>

<deferred>
## Deferred Ideas

- WebSocket progress streaming — SSE is sufficient for v1
- Multi-GPU auto-scaling — single GPU per worker for v1
- CDN for rendered assets — direct serve for v1

</deferred>

---

*Phase: 12-production-v1*
*Context gathered: 2026-04-21*
