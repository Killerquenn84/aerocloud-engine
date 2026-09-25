# API Surface

**Phase:** 12-production-v1
**Plans:** 12-05
**Requirements:** PROD-07, PROD-08, PROD-16, PROD-17
**Source package:** `apps/api/src/aerocloud_api/`

---

## Overview

The AeroCloud Engine HTTP API is a FastAPI application that acts as the gateway
between external callers and the Celery/GPU render pipeline.

**Key properties:**
- No CORS middleware (server-to-server only per CLAUDE.md §12, D-18)
- All endpoints are JSON (except SSE progress stream)
- Rate limiting via slowapi on POST /render (10/minute per IP)
- Prometheus metrics auto-instrumented on all routes

---

## Endpoints

### POST /render

**Purpose:** Dispatch a render job to the Celery `realtime` queue.
**Auth:** None (rate limited instead — see T-12-05-05)
**Rate limit:** 10 requests/minute per IP (Redis-backed in production)

**Request schema:** `RenderRequest` (Pydantic model)

```json
{
  "text": "Hello World",
  "seed": 42,
  "shape_b64": "<base64-encoded PNG mask>",
  "font_family": "Inter",
  "colors": ["#000000", "#1a1a1a"],
  "width": 512,
  "height": 512
}
```

**Field validators (security):**
- `font_family`: must be in `assets/fonts/` allow-list (D-16, PROD-14)
- `shape_b64`: no path traversal characters (D-17, PROD-13)
- `colors`: each must match `^#[0-9a-fA-F]{3,8}$` (D-15, PROD-15)

**Response:** `202 Accepted`

```json
{
  "task_id": "celery-task-uuid-here"
}
```

**Error responses:**
- `422 Unprocessable Entity` — invalid RenderRequest (field validation failed)
- `429 Too Many Requests` — rate limit exceeded

```json
{
  "error": "rate_limit_exceeded",
  "detail": "10 per 1 minute"
}
```

---

### GET /render/{task_id}/progress

**Purpose:** Stream Server-Sent Events (SSE) for render job progress.
**Auth:** None
**Rate limit:** Not rate limited (read-only stream)

**Protocol:** SSE (`Content-Type: text/event-stream`)

Each event is a JSON payload:

```json
{"stage": "nlp", "pct": 10}
{"stage": "rendering", "pct": 50}
{"stage": "optimization", "pct": 70}
{"stage": "export", "pct": 90}
{"stage": "done", "pct": 100}
```

On failure:
```json
{"stage": "failed", "pct": 0, "error": "soft_time_limit_exceeded"}
```

**Termination:** Stream closes when `stage` is `done`, `failed`, or `success`.
**Ping:** 15-second SSE ping to prevent proxy timeouts (T-12-05-04).

**Backed by:** Redis pub/sub channel `render:progress:{task_id}`

---

### GET /health

**Purpose:** Public liveness probe for load balancers.
**Auth:** None
**Rate limit:** None (infrastructure probe — must always succeed)

**Response:** `200 OK`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### GET /health/internal

**Purpose:** Authenticated readiness probe — checks Postgres, Redis, GPU.
**Auth:** `X-Internal-Token` header required
**Rate limit:** None

**Auth error:** `401 Unauthorized` on missing or incorrect token.

Configure the token via `INTERNAL_HEALTH_TOKEN` environment variable.
Default `"changeme"` must be overridden in production.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "postgres": "ok",
  "redis": "ok",
  "gpu": "available"
}
```

Status values:
- `status`: `"ok"` (all checks pass) or `"degraded"` (Postgres or Redis down)
- `postgres`: `"ok"` or `"unavailable"`
- `redis`: `"ok"` or `"unavailable"`
- `gpu`: `"available"` or `"unavailable"`

**Security note (T-12-05-03):** Returns only status strings — never connection
strings, error messages, or credentials.

---

### GET /metrics

**Purpose:** Prometheus metrics scrape endpoint.
**Auth:** None (Prometheus scrapes from internal network; CORS disabled)
**Rate limit:** None

Exposed by `prometheus-fastapi-instrumentator`. Includes:
- HTTP request latency histogram per route
- HTTP request count per route + status code
- Custom AeroCloud metrics (defined in `aerocloud.observability`):

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `aerocloud_render_duration_seconds` | Histogram | — | End-to-end render latency |
| `aerocloud_renders_total` | Counter | `status` | Total renders (success/failed) |
| `aerocloud_gpu_memory_used_bytes` | Gauge | — | GPU memory in use |

---

## Rate Limiting

**Implementation:** `slowapi` with Redis-backed token bucket.

```
POST /render: 10/minute per IP
All other endpoints: unlimited
```

**Storage:** Redis URL from `settings.redis_url`. Falls back to in-memory for
tests (swap `limiter._storage` and `limiter.limiter.storage` in conftest).

**Error format:** JSON 429 with `error` and `detail` fields.

**Known limitation (T-12-05-05):** Rate limiting is IP-based. Per-shop rate
limiting (via Shopify session token) is deferred to a future plan.

---

## Authentication

| Endpoint | Auth |
|----------|------|
| POST /render | None (rate limited) |
| GET /render/{task_id}/progress | None |
| GET /health | None |
| GET /health/internal | X-Internal-Token header |
| GET /metrics | None (internal network access assumed) |

---

## Request/Response Models

### RenderRequest

```python
class RenderRequest(BaseModel):
    text: str
    seed: int = 42
    shape_b64: str | None = None      # base64 PNG mask
    font_family: str = "Inter"        # validated: assets/fonts/ allow-list
    colors: list[str] | None = None   # validated: ^#[0-9a-fA-F]{3,8}$
    width: int = 512
    height: int = 512
```

### RenderResult (from Celery task)

```python
class RenderResult(BaseModel):
    reproducibility_id: str    # "{seed}:{task_id}"
    placed_words: list[...]    # PlacedWord list
    score: LayoutScore         # quality metrics
    png_b64: str               # base64 PNG output
    svg: str | None            # SVG string (optional)
    elapsed_ms: int            # render duration in milliseconds
```

---

## Celery Task Dispatch

`POST /render` dispatches via:

```python
celery_app.send_task(
    "aerocloud_worker.tasks.render.render_task",
    args=[body.model_dump()],
    queue="realtime",
)
```

Two queues:
- `realtime` — live API renders (priority)
- `background` — Self-Play nightly training (low priority)

---

## CORS Policy

No `CORSMiddleware` installed. This is intentional per D-18 and CLAUDE.md §12
(server-to-server only — Shopify session token auth, no cross-origin browser calls).

---

## Application Factory

```python
from aerocloud_api.app import create_app
app = create_app()
```

Startup lifecycle (via FastAPI `lifespan`):
1. `init_tracing(otlp_endpoint=settings.otlp_endpoint)` — initialize OTel tracing

Shutdown: no cleanup required at API layer (Redis connections are per-request).

---

*Last updated: Phase 12 Plan 09 release gate*
*Owner: AeroCloud Engine Phase 12 — Production v1*
