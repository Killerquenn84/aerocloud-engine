---
phase: 12-production-v1
plan: "08"
subsystem: testing
tags: [load-test, httpx, asyncio, p99, concurrency, pytest, performance]

requires:
  - phase: 12-production-v1
    plan: "05"
    provides: "POST /render endpoint returning 202 + task_id"

provides:
  - "100-concurrent-render load test via httpx.AsyncClient + asyncio.gather"
  - "P50 + P99 dispatch latency measurement with printed report"
  - "pytest.mark.load marker for selective execution (excluded from default suite)"
  - "LOAD_TEST_URL env var override for targeting any server instance"

affects:
  - "12-09 (golden set / release gate — load test must pass before release)"

tech-stack:
  added: []
  patterns:
    - "asyncio.gather() for 100 concurrent HTTP requests in a single test coroutine"
    - "pytest.mark.load isolates load tests from the default CI suite"
    - "P99 via sorted list index: latencies[int(len * 0.99)]"
    - "Circle mask generated programmatically via numpy + PIL — no external fixture dependency"

key-files:
  created:
    - "packages/engine/tests/load/__init__.py"
    - "packages/engine/tests/load/test_load_concurrent.py"
  modified:
    - "pyproject.toml (added 'load' marker to [tool.pytest.ini_options])"

key-decisions:
  - "Used httpx.AsyncClient + asyncio.gather (not locust) per Phase 12 research recommendation — simpler, no daemon process, works in-process with pytest"
  - "P99 index computed as int(len * 0.99) — avoids off-by-one at 100 samples (gives index 99 = last element)"
  - "Test asserts P99 < 5.0s for dispatch latency only (not render completion) — appropriate budget for task enqueue under concurrency"
  - "LOAD_TEST_URL defaults to http://localhost:8000 — zero-config for local development, overridable for CI/staging"

patterns-established:
  - "load marker: pytest.mark.load — all load tests in packages/engine/tests/load/ are isolated from default pytest run"
  - "circle mask generation: numpy ogrid circle drawn to BytesIO PNG then base64-encoded — reusable pattern for fixture-free mask generation in tests"

requirements-completed:
  - PROD-22

duration: 5min
completed: 2026-04-16
---

# Phase 12 Plan 08: Load Test — 100 Concurrent Renders with P99 Latency Summary

**httpx + asyncio.gather load test dispatching 100 concurrent POST /render requests, measuring P50/P99 dispatch latency, asserting zero failures and P99 < 5s — marked pytest.mark.load for selective execution**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-16T00:00:00Z
- **Completed:** 2026-04-16T00:05:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Created `packages/engine/tests/load/__init__.py` (package marker)
- Created `packages/engine/tests/load/test_load_concurrent.py`: single async test function dispatching 100 concurrent POST /render requests via `httpx.AsyncClient` + `asyncio.gather`, printing P50/P99 dispatch latency, asserting 0 errors and P99 < 5.0s
- Registered `load` marker in root `pyproject.toml` — load tests do not appear in default `pytest` runs; invoke with `pytest packages/engine/tests/load/ -m load -v -s`

## Task Commits

1. **Task 1: 100-concurrent-render load test with P99 measurement (PROD-22)** — `26211f8` (feat)

## Files Created/Modified

- `packages/engine/tests/load/__init__.py` — package marker (empty)
- `packages/engine/tests/load/test_load_concurrent.py` — async load test: 100 concurrent requests, P50/P99 measurement, assertions, configurable BASE_URL
- `pyproject.toml` — added `"load: load tests (not run by default; run with -m load against a live server)"` to markers list

## Decisions Made

- httpx + asyncio.gather chosen over locust per Phase 12 research (simpler, no separate process, pytest-native)
- P99 assertion budget of 5.0s applies to dispatch latency only (time to receive 202), not render completion time
- Circle mask generated inline (`numpy ogrid` → PIL → BytesIO → base64) — no dependency on conftest fixtures, keeping load tests self-contained

## Deviations from Plan

None — plan executed exactly as written. The TDD flow was: write test (RED — test structure valid but requires live server to execute), collect-only verification passes, commit.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. To execute the load test against a live server:

```bash
# Start the API server first, then:
uv run pytest packages/engine/tests/load/ -m load -v -s

# Against a specific server:
LOAD_TEST_URL=http://my-server:8000 uv run pytest packages/engine/tests/load/ -m load -v -s
```

## Known Stubs

None — the load test is fully wired. It requires a live server to produce meaningful results; collection-only verification confirms structural correctness.

## Threat Flags

No new threat surface. T-12-08-01 (DoS — intentional self-DoS for testing) is documented in the plan's threat model and mitigated by the `pytest.mark.load` selective marker (never runs in default CI).

## Self-Check

- [x] `packages/engine/tests/load/__init__.py` — exists
- [x] `packages/engine/tests/load/test_load_concurrent.py` — exists
- [x] `pyproject.toml` — `load` marker added
- [x] Task commit: 26211f8 — present in git log
- [x] `uv run pytest packages/engine/tests/load/test_load_concurrent.py --collect-only` — 1 test collected

## Self-Check: PASSED

## Next Phase Readiness

- Load test ready to execute against any running server instance
- Plan 09 (golden set / release gate) can use this test as part of pre-release validation
- Marker isolation ensures CI default runs are unaffected

---
*Phase: 12-production-v1*
*Completed: 2026-04-16*
