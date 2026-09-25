---
phase: 12-production-v1
plan: "05"
subsystem: api
tags: [fastapi, celery, sse, redis, slowapi, prometheus, rate-limiting, health, tdd]

requires:
  - phase: 12-production-v1
    plan: "03"
    provides: "render_task on realtime queue, Redis pub/sub channel render:progress:{task_id}"
  - phase: 12-production-v1
    plan: "04"
    provides: "init_tracing(), render_duration Histogram, render_total Counter from observability.py"
  - phase: 12-production-v1
    plan: "02"
    provides: "RenderRequest with field validators (font_family, shape_b64, colors)"

provides:
  - "FastAPI app instance with lifespan (init_tracing on startup)"
  - "POST /render: validates RenderRequest, dispatches to Celery realtime queue, returns 202 + task_id"
  - "GET /render/{task_id}/progress: SSE stream from Redis pub/sub render:progress:{task_id}, terminates on done/failed"
  - "GET /health: public liveness probe, returns {status: ok, version}"
  - "GET /health/internal: authenticated readiness probe (X-Internal-Token), checks Postgres + Redis + GPU"
  - "SlowAPI rate limiter at 10/minute per IP on POST /render (Redis-backed in production)"
  - "Prometheus /metrics via prometheus-fastapi-instrumentator"
  - "No CORSMiddleware (D-18 enforced)"

affects:
  - "12-06 (integration tests — tests POST /render + SSE against running API)"
  - "12-09 (load tests — rate limiter and SSE under concurrent load)"

tech-stack:
  added:
    - "httpx>=0.27.0 (FastAPI TestClient dependency)"
    - "asyncpg>=0.29.0 (health/internal Postgres check)"
  patterns:
    - "TDD Red-Green per task: failing tests committed before implementation"
    - "conftest.py swaps limiter.limiter.storage to MemoryStorage per test — @limiter.limit() decorator captures limiter instance at decoration time, so patching app.state.limiter alone is insufficient; the strategy's .storage reference must also be swapped"
    - "asyncio.gather() for concurrent Postgres + Redis health checks in /health/internal"
    - "torch imported inline in _check_gpu() — CUDA fork-safety pattern consistent with render_task"
    - "SSE generator uses try/finally with pubsub.unsubscribe + client.aclose for guaranteed cleanup"
    - "rate_limit_exceeded_handler returns JSON 429 with {error: rate_limit_exceeded, detail: ...}"

key-files:
  created:
    - "apps/api/src/aerocloud_api/app.py"
    - "apps/api/src/aerocloud_api/routes/render.py"
    - "apps/api/src/aerocloud_api/routes/health.py"
    - "apps/api/src/aerocloud_api/routes/__init__.py"
    - "apps/api/src/aerocloud_api/middleware/rate_limit.py"
    - "apps/api/src/aerocloud_api/middleware/__init__.py"
    - "apps/api/src/aerocloud_api/metrics.py"
    - "apps/api/tests/__init__.py"
    - "apps/api/tests/test_render_endpoint.py"
    - "apps/api/tests/test_health_endpoint.py"
    - "apps/api/tests/test_rate_limit.py"
    - "apps/api/tests/conftest.py"
  modified:
    - "apps/api/pyproject.toml (added httpx, asyncpg dependencies)"
    - "packages/engine/src/aerocloud/config.py (added internal_health_token field)"

key-decisions:
  - "@limiter.limit() decorator captures the limiter instance at decoration time — replacing app.state.limiter with a new Limiter in tests does nothing; only swapping ._storage AND .limiter.storage on the original singleton works"
  - "internal_health_token added to AeroCloudSettings (default 'changeme') rather than a separate config class — consistent with existing settings pattern; override via INTERNAL_HEALTH_TOKEN env var in production"
  - "torch imported inline in _check_gpu() not at module level — maintains CUDA fork-safety pattern established in render_task (Plan 03)"
  - "MemoryStorage per test via conftest autouse fixture — rate-limit counters bleed between tests if storage is shared; fresh MemoryStorage per test is the only correct isolation approach"
  - "Prometheus /metrics exposed without auth — acceptable because CORS is disabled and Prometheus scrapes from internal network only (D-18 enforces no cross-origin access)"
  - "setup_metrics(app) called after include_router() calls — ensures all routes are instrumented by prometheus-fastapi-instrumentator"

patterns-established:
  - "SlowAPI test isolation: swap limiter._storage AND limiter.limiter.storage (not app.state.limiter) in conftest autouse fixture"
  - "SSE generator pattern: subscribe → listen → yield events → break on terminal stage → finally unsubscribe+aclose"
  - "Health endpoint auth: X-Internal-Token header checked before any DB/Redis calls; 401 on missing or wrong token"

requirements-completed:
  - PROD-07
  - PROD-08
  - PROD-16
  - PROD-17

duration: 10min
completed: 2026-04-22
---

# Phase 12 Plan 05: FastAPI HTTP Surface Summary

**FastAPI app with POST /render Celery dispatch + SSE progress streaming, health probes (public + authenticated), slowapi rate limiting at 10/minute per IP, and Prometheus /metrics — 20 TDD tests green, mypy --strict clean**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-22T00:07:29Z
- **Completed:** 2026-04-22T00:17:52Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Created `app.py`: FastAPI instance with lifespan (init_tracing on startup), SlowAPIMiddleware, health + render routers, Prometheus auto-instrumentation — NO CORSMiddleware (D-18)
- Created `routes/render.py`: POST /render dispatches to Celery `realtime` queue via `send_task("aerocloud_worker.tasks.render.render_task")`, returns 202 + task_id; GET /render/{task_id}/progress streams SSE from Redis pub/sub channel `render:progress:{task_id}`, terminates on done/failed/success stage, ping=15s
- Created `routes/health.py`: GET /health (public, 200 + version); GET /health/internal (X-Internal-Token auth, concurrent Postgres SELECT 1 + Redis PING + torch.cuda.is_available(), returns status strings not booleans — T-12-05-03)
- Created `middleware/rate_limit.py`: slowapi Limiter with Redis-backed storage at 10/minute per IP on POST /render; JSON 429 handler
- Created `metrics.py`: Instrumentator().instrument(app).expose(app) wired after all routers
- Added `internal_health_token` to AeroCloudSettings in config.py (T-12-05-01)
- Added `httpx` and `asyncpg` to api pyproject.toml dependencies
- 20 unit tests across 3 test files, all green: 8 render endpoint tests, 9 health endpoint tests, 3 rate limit tests

## Task Commits

1. **Task 1 RED — failing tests for POST /render + SSE + no-CORS** — `c1cc79c` (test)
2. **Task 1 GREEN — FastAPI app + render route + SSE** — `c580827` (feat)
3. **Task 2 RED — failing tests for health + rate limit** — `1dc2105` (test)
4. **Task 2 GREEN — health endpoints + rate limiting + metrics** — `ca5e57f` (feat)

## Files Created/Modified

- `apps/api/src/aerocloud_api/app.py` — FastAPI factory, lifespan, middleware, router includes, metrics wiring
- `apps/api/src/aerocloud_api/routes/render.py` — POST /render + GET /{task_id}/progress SSE
- `apps/api/src/aerocloud_api/routes/health.py` — GET /health + GET /health/internal
- `apps/api/src/aerocloud_api/routes/__init__.py` — package marker
- `apps/api/src/aerocloud_api/middleware/rate_limit.py` — slowapi Limiter + 429 handler
- `apps/api/src/aerocloud_api/middleware/__init__.py` — package marker
- `apps/api/src/aerocloud_api/metrics.py` — Prometheus instrumentator setup
- `apps/api/tests/__init__.py` — test package marker
- `apps/api/tests/conftest.py` — autouse fixture swapping limiter storage to MemoryStorage per test
- `apps/api/tests/test_render_endpoint.py` — 8 tests (202, dispatch, args, 422, SSE content-type, no CORS)
- `apps/api/tests/test_health_endpoint.py` — 9 tests (200, status, version, 401 no-token, 401 wrong-token, 200 valid, string values, PG failure, Redis failure)
- `apps/api/tests/test_rate_limit.py` — 3 tests (429 after 10 requests, error body, health not rate-limited)
- `apps/api/pyproject.toml` — added httpx, asyncpg
- `packages/engine/src/aerocloud/config.py` — added internal_health_token field

## Decisions Made

- `@limiter.limit("10/minute")` decorator captures the limiter **instance** at decoration time via `async_wrapper` closure. When tests replace `app.state.limiter` with a new Limiter, the decorator's closure still references the original. The only correct fix is to swap `_storage` AND `limiter.limiter.storage` (the FixedWindowRateLimiter's reference) on the original singleton in the test fixture.
- `internal_health_token` added to `AeroCloudSettings` rather than a separate security config — keeps the single-settings-class pattern established in Phase 1. Production deployments override via `INTERNAL_HEALTH_TOKEN` env var.
- `torch` imported inline in `_check_gpu()` (not at module level) — preserves CUDA fork-safety pattern from Plan 03: no CUDA context before prefork.
- `setup_metrics(app)` called **after** `include_router()` calls so all routes are visible to the instrumentator before it instruments them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added httpx and asyncpg to pyproject.toml**
- **Found during:** Task 1 RED phase (test collection failed — `ModuleNotFoundError: No module named 'httpx'`)
- **Issue:** FastAPI TestClient requires httpx at runtime; asyncpg needed for health/internal Postgres check. Neither was in api/pyproject.toml.
- **Fix:** Added `httpx>=0.27.0` and `asyncpg>=0.29.0` to api project dependencies; ran `uv sync`
- **Files modified:** `apps/api/pyproject.toml`
- **Verification:** Test collection succeeds; asyncpg import works in health.py
- **Committed in:** `c1cc79c` (Task 1 RED commit)

**2. [Rule 1 - Bug] Fixed AsyncMock for pubsub coroutines in SSE test**
- **Found during:** Task 1 GREEN phase (SSE test failing with `TypeError: object MagicMock can't be used in 'await' expression`)
- **Issue:** `pubsub.subscribe`, `pubsub.unsubscribe`, and `client.aclose` are coroutines (awaited); test used plain `MagicMock` which cannot be awaited
- **Fix:** Changed to `AsyncMock` for all awaited methods in the SSE test mock
- **Files modified:** `apps/api/tests/test_render_endpoint.py`
- **Verification:** SSE content-type test passes
- **Committed in:** `c580827` (Task 1 GREEN commit)

**3. [Rule 1 - Bug] Fixed SlowAPI test isolation — limiter._storage swap alone insufficient**
- **Found during:** Task 2 GREEN phase (all POST /render tests returning 500 due to AuthenticationError from Redis)
- **Issue:** `@limiter.limit("10/minute")` captures the limiter **instance** at decoration time. `app.state.limiter` replacement and `limiter._storage` swap did not update `limiter.limiter.storage` (the `FixedWindowRateLimiter`'s storage reference used by `__evaluate_limits`). The strategy's `.storage` attribute is a separate reference that must also be patched.
- **Fix:** conftest autouse fixture now swaps both `limiter._storage` AND `limiter.limiter.storage` to a fresh `MemoryStorage()` per test, restoring originals after yield.
- **Files modified:** `apps/api/tests/conftest.py`
- **Verification:** All 20 tests pass including rate_limit tests (429 after 10 requests) and render tests (202 on first request)
- **Committed in:** `ca5e57f` (Task 2 GREEN commit)

**4. [Rule 1 - Bug] Fixed mypy strict errors — redis.asyncio.from_url untyped**
- **Found during:** Post-implementation mypy check
- **Issue:** `redis.asyncio.from_url` has no type stubs; mypy --strict emits `no-untyped-call` for both health.py and render.py
- **Fix:** Added `# type: ignore[no-untyped-call]` comments on both `from_url` calls
- **Files modified:** `apps/api/src/aerocloud_api/routes/health.py`, `apps/api/src/aerocloud_api/routes/render.py`
- **Verification:** `mypy --strict` reports 0 errors
- **Committed in:** `ca5e57f` (Task 2 GREEN commit)

---

**Total deviations:** 4 auto-fixed (1 blocking, 3 bugs)
**Impact on plan:** All fixes necessary for correct test operation and type safety. No scope creep. All STRIDE mitigations applied (T-12-05-01 through T-12-05-05).

## Known Stubs

None — all endpoints are fully wired to real dependencies (Celery, Redis pub/sub, asyncpg, prometheus-fastapi-instrumentator). The plan goal is achieved without stubs.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model:
- T-12-05-01 (Spoofing): X-Internal-Token on /health/internal — implemented
- T-12-05-02 (DoS): slowapi 10/minute per IP on POST /render — implemented
- T-12-05-03 (Info Disclosure): /health/internal returns only status strings — implemented
- T-12-05-04 (DoS): SSE terminates on terminal stage, ping=15s — implemented
- T-12-05-05 (Spoofing): IP-based rate limiting accepted per threat register

## Self-Check

- [x] `apps/api/src/aerocloud_api/app.py` — exists
- [x] `apps/api/src/aerocloud_api/routes/render.py` — exists
- [x] `apps/api/src/aerocloud_api/routes/health.py` — exists
- [x] `apps/api/src/aerocloud_api/middleware/rate_limit.py` — exists
- [x] `apps/api/src/aerocloud_api/metrics.py` — exists
- [x] Task commits: c1cc79c, c580827, 1dc2105, ca5e57f — all present in git log
- [x] 20/20 tests pass
- [x] mypy --strict: 0 errors

## Self-Check: PASSED

## Next Phase Readiness

- POST /render + SSE progress stream ready for integration test consumption (Plan 06)
- /health + /health/internal ready for load balancer and monitoring configuration
- /metrics ready for Prometheus scrape configuration
- Rate limiter wired; production Redis URL must be set via REDIS_URL env var (tested with in-memory fallback)
- `internal_health_token` must be overridden in production via INTERNAL_HEALTH_TOKEN env var (default "changeme" is insecure)

---
*Phase: 12-production-v1*
*Completed: 2026-04-22*
