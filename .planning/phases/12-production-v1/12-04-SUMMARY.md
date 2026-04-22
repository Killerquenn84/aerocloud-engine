---
phase: 12-production-v1
plan: "04"
subsystem: infra
tags: [opentelemetry, otlp, prometheus, observability, tracing, metrics]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "NoOp init_tracing() and get_tracer() foundation"
provides:
  - "Production-ready observability.py with OTLP gRPC export when endpoint configured"
  - "Prometheus metric singletons: render_duration (Histogram), render_total (Counter), gpu_memory_used (Gauge)"
  - "AeroCloudSettings.otlp_endpoint field (default None, backward compat)"
  - "_reset_tracing() test helper for OTel provider isolation between tests"
affects:
  - "12-05 (FastAPI instrumentator wiring uses render_duration, render_total)"
  - "worker render task (uses render_duration.observe, render_total.labels)"

# Tech tracking
tech-stack:
  added:
    - "opentelemetry-exporter-otlp-proto-grpc (already installed, now activated)"
    - "prometheus-client (already installed, now activated)"
  patterns:
    - "OTel conditional exporter: NoOp when endpoint=None, OTLP BatchSpanProcessor when endpoint provided"
    - "Prometheus module-level singletons — created once at import time per prometheus_client convention"
    - "_reset_tracing() pattern: resets both _INITIALIZED flag and OTel _TRACER_PROVIDER + _TRACER_PROVIDER_SET_ONCE._done for true test isolation"

key-files:
  created:
    - "packages/engine/tests/unit/test_observability.py"
  modified:
    - "packages/engine/src/aerocloud/observability.py"
    - "packages/engine/src/aerocloud/config.py"

key-decisions:
  - "NoOp backward compatibility preserved: callers without otlp_endpoint arg see identical behavior to Phase 1"
  - "Prometheus Counter name: prometheus_client strips _total suffix from internal _name (exposed as aerocloud_renders_total in scrape output)"
  - "OTel reset uses setattr/getattr + Once._done=False to avoid mypy attr-defined errors on private internals"
  - "Security T-12-04-01 enforced in docstring: span attributes must not contain PII or API keys"

patterns-established:
  - "Conditional exporter pattern: import OTLPSpanExporter inside the if-branch to avoid module-level grpc dependency when NoOp"
  - "Test isolation for OTel: reset _TRACER_PROVIDER and Once._done to allow fresh provider per test"

requirements-completed:
  - PROD-18
  - PROD-19

# Metrics
duration: 3min
completed: 2026-04-22
---

# Phase 12 Plan 04: Observability Upgrade Summary

**OTLP gRPC trace export activated on endpoint config + three Prometheus metric singletons (Histogram/Counter/Gauge) defined for render pipeline monitoring**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-22T00:02:17Z
- **Completed:** 2026-04-22T00:05:31Z
- **Tasks:** 1 (TDD — 2 commits: test RED + feat GREEN)
- **Files modified:** 3

## Accomplishments

- `init_tracing(otlp_endpoint=...)` now wires `BatchSpanProcessor + OTLPSpanExporter` when endpoint provided; NoOp when None (backward compatible with all prior phases)
- Three Prometheus module-level metric singletons ready for worker and FastAPI use: `render_duration`, `render_total`, `gpu_memory_used`
- `AeroCloudSettings.otlp_endpoint: str | None = None` added so endpoint can be injected via environment variable
- `_reset_tracing()` test helper correctly resets both the module flag and OTel's internal `Once` sentinel for per-test provider isolation
- 26 tests green, `mypy --strict` clean

## Task Commits

1. **Task 1 RED — failing tests** - `60e203c` (test)
2. **Task 1 GREEN — implementation** - `b83e59c` (feat)

## Files Created/Modified

- `packages/engine/tests/unit/test_observability.py` — 26 tests covering OTLP mode, NoOp mode, idempotency, Prometheus metrics, config field, _reset_tracing helper
- `packages/engine/src/aerocloud/observability.py` — upgraded with OTLP conditional exporter, Prometheus singletons, _reset_tracing()
- `packages/engine/src/aerocloud/config.py` — added `otlp_endpoint: str | None = None` field to Settings

## Decisions Made

- **Conditional OTLP import inside if-branch:** `OTLPSpanExporter` is imported inside the `if otlp_endpoint is not None` block to avoid loading the grpc dependency at module import time when running in NoOp mode.
- **prometheus_client Counter _name convention:** Counter `aerocloud_renders_total` has internal `_name = "aerocloud_renders"` — prometheus_client automatically appends `_total` in the exposition format. Test updated to reflect actual library behavior.
- **OTel reset via setattr + Once._done:** Reaching into OTel private internals is unavoidable for test isolation; used `setattr`/`getattr` + direct `_done = False` assignment to keep mypy clean while being explicit about intent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed OTel test isolation — _reset_tracing() must also reset Once sentinel**
- **Found during:** Task 1 GREEN phase (test run after initial implementation)
- **Issue:** `_reset_tracing()` only reset `_INITIALIZED` flag; OTel's `_TRACER_PROVIDER_SET_ONCE` (a `Once` sentinel) blocked `set_tracer_provider()` from re-setting the global provider in subsequent tests, causing 11 test failures with "Overriding of current TracerProvider is not allowed"
- **Fix:** Extended `_reset_tracing()` to also clear `opentelemetry.trace._TRACER_PROVIDER = None` and `_TRACER_PROVIDER_SET_ONCE._done = False`
- **Files modified:** `packages/engine/src/aerocloud/observability.py`
- **Verification:** All 26 tests pass; provider correctly re-created per test
- **Committed in:** `b83e59c` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed Counter name assertion — prometheus_client strips _total suffix**
- **Found during:** Task 1 GREEN phase (test_render_total_name failure)
- **Issue:** Test asserted `render_total._name == "aerocloud_renders_total"` but prometheus_client stores `_name = "aerocloud_renders"` and appends `_total` only in scrape exposition
- **Fix:** Updated test assertion to check `_name == "aerocloud_renders"` and `_type == "counter"` with explanatory comment
- **Files modified:** `packages/engine/tests/unit/test_observability.py`
- **Verification:** 26/26 tests pass
- **Committed in:** `b83e59c` (Task 1 GREEN commit — test fix folded into same commit as implementation)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — library behavior bugs discovered during TDD GREEN phase)
**Impact on plan:** Both fixes necessary for correct test behavior. No scope creep. Implementation matches plan spec exactly.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None — no external service configuration required. The `otlp_endpoint` setting is opt-in via environment variable `OTLP_ENDPOINT`; without it the engine runs in NoOp mode as before.

## Known Stubs

None — all metrics are real prometheus_client singletons. The OTLP exporter is conditionally activated, not stubbed. FastAPI instrumentation wiring is intentionally deferred to Plan 05 per plan spec.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model (T-12-04-01: span attributes must not contain PII; T-12-04-02: BatchSpanProcessor queue DoS — accepted).

## Next Phase Readiness

- Plan 05 can import `render_duration`, `render_total`, `gpu_memory_used` directly from `aerocloud.observability`
- Plan 05 FastAPI instrumentator should call `init_tracing(otlp_endpoint=settings.otlp_endpoint)` at app startup
- Worker render task should call `render_duration.observe(elapsed)` and `render_total.labels(status=...).inc()` after each render

---
*Phase: 12-production-v1*
*Completed: 2026-04-22*
