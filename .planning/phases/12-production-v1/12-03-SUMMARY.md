---
phase: 12-production-v1
plan: "03"
subsystem: worker
tags: [celery, worker, queue, gpu, redis, timeout, graceful-shutdown, docker, tdd]

requires:
  - phase: 10-self-play
    provides: self_play_nightly task and celery_app.py base config

provides:
  - celery_app.py: realtime queue route for render.*, worker_prefetch_multiplier=1, task_annotations with per-queue timeouts
  - tasks/render.py: render_task Celery task with Pydantic validation, Redis progress pub/sub, SoftTimeLimitExceeded handling
  - shutdown.py: on_worker_shutting_down signal handler registered at app load
  - infra/docker/worker-entrypoint.sh: production entrypoint with ulimit -c 0, prefork/concurrency=1/max-tasks-per-child=50

affects:
  - 12-05 (FastAPI render endpoint — dispatches render jobs to realtime queue)
  - 12-06 (Integration tests — render_task is the execution target)

tech-stack:
  added: []
  patterns:
    - TDD Red-Green per task: tests written before implementation, verified failing before GREEN
    - Module-level redis import alias (redis_lib) for test patchability via patch("aerocloud_worker.tasks.render.redis_lib")
    - torch deferred to task body only — CUDA fork safety (no CUDA context before prefork)
    - task_annotations over global task_time_limit — different limits per queue
    - exec in entrypoint — clean SIGTERM delivery to celery process (no shell wrapper)

key-files:
  created:
    - apps/worker/src/aerocloud_worker/tasks/render.py
    - apps/worker/src/aerocloud_worker/shutdown.py
    - infra/docker/worker-entrypoint.sh
    - apps/worker/tests/__init__.py
    - apps/worker/tests/test_celery_config.py
    - apps/worker/tests/test_render_task.py
  modified:
    - apps/worker/src/aerocloud_worker/celery_app.py (realtime route, prefetch=1, task_annotations, shutdown import)

key-decisions:
  - "redis imported at module level as redis_lib alias — enables patch('aerocloud_worker.tasks.render.redis_lib') in tests without inline import"
  - "torch NOT imported at module level — Celery prefork forks after app init; CUDA context before fork corrupts child GPU state"
  - "task_annotations used instead of global task_time_limit — render needs 300s hard kill, self_play needs 8h soft limit (incompatible globals)"
  - "exec in worker-entrypoint.sh — shell process replaced by celery; SIGTERM delivered directly without shell interception"
  - "shutdown.py imported from celery_app.py bottom — signal registered at app import time, not lazily at first task"

requirements-completed: [PROD-09, PROD-10, PROD-11, PROD-12, PROD-20]

duration: 8min
completed: 2026-04-22
---

# Phase 12 Plan 03: Celery Worker Hardening Summary

**Realtime queue routing, render task skeleton with Redis progress pub/sub, GPU timeout annotations, graceful shutdown handler, and production Docker entrypoint — 17 TDD tests green**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-22T00:02:27Z
- **Completed:** 2026-04-22T00:10:47Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Extended `celery_app.py`: added `realtime` queue route for `render.*` tasks, `worker_prefetch_multiplier=1` (GPU OOM prevention), and `task_annotations` with per-queue timeouts (render: 300s hard/270s soft; self_play: 28800s soft)
- Created `tasks/render.py`: bound Celery task with RenderRequest Pydantic validation at entry (T-12-03-03), Redis progress pub/sub on `render:progress:{task_id}`, 7 progress stages (started/nlp/geometry/rendering/optimization/export/done), SoftTimeLimitExceeded handler publishes `failed` stage then re-raises, torch import comment deferred to task body (CUDA fork safety)
- Created `shutdown.py`: `on_worker_shutting_down` connected to Celery `worker_shutting_down` signal at app load time via celery_app.py import, logs shutdown event via structlog
- Created `infra/docker/worker-entrypoint.sh`: `ulimit -c 0` (core dumps disabled per CLAUDE.md §12), `exec celery` with `--pool=prefork --concurrency=1 --max-tasks-per-child=50 --queues=realtime,background`
- 17 unit tests across 2 test files, all green: 9 config tests (queue routing, timeouts, prefetch, shutdown signal), 8 render task tests (registration, torch safety, Redis progress, SoftTimeLimitExceeded, result fields)

## Task Commits

1. **Task 1: Celery config + realtime queue + render task + timeouts (PROD-09, PROD-10, PROD-11, PROD-12)** — `3413c6e` (feat)
2. **Task 2: Graceful shutdown + worker entrypoint (PROD-20)** — `c5b1c45` (feat)

## Files Created/Modified

- `apps/worker/src/aerocloud_worker/celery_app.py` — realtime route, prefetch=1, task_annotations, shutdown import
- `apps/worker/src/aerocloud_worker/tasks/render.py` — render_task with Pydantic validation, Redis pub/sub, timeout handling
- `apps/worker/src/aerocloud_worker/shutdown.py` — on_worker_shutting_down signal handler
- `infra/docker/worker-entrypoint.sh` — production entrypoint (ulimit -c 0, prefork, concurrency=1)
- `apps/worker/tests/__init__.py` — new test package
- `apps/worker/tests/test_celery_config.py` — 9 tests (routes, timeouts, prefetch, shutdown)
- `apps/worker/tests/test_render_task.py` — 8 tests (registration, CUDA safety, progress, failure, result shape)

## Decisions Made

- Module-level `import redis as redis_lib` alias chosen over inline import so tests can patch `aerocloud_worker.tasks.render.redis_lib` cleanly without `import_module` hacks
- torch intentionally NOT imported at module level — Celery prefork forks after app init; any CUDA context created before fork is invalid in child processes (research Pitfall 1)
- `task_annotations` used (not `task_time_limit`) — render needs 300s hard kill while self_play needs unlimited hard kill with 8h soft; these are incompatible with a single global setting
- `exec celery` in entrypoint replaces the sh process, so SIGTERM from Docker/systemd reaches the Celery master directly without shell signal interception

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed duplicate inline redis import shadowing module-level alias**
- **Found during:** Task 1 (first GREEN test run)
- **Issue:** Tests patched `aerocloud_worker.tasks.render.redis_lib` but a duplicate `import redis as redis_lib` inside the task function body created a local binding that bypassed the patch
- **Fix:** Moved redis import to module level as `redis_lib` alias; removed inline import from task body
- **Files modified:** `apps/worker/src/aerocloud_worker/tasks/render.py`
- **Verification:** 8 render task tests pass with mock_redis intercepting all publish calls
- **Committed in:** `3413c6e`

**2. [Rule 1 - Bug] Fixed wrong calling convention for bound Celery tasks in tests**
- **Found during:** Task 1 (first test run — `TypeError: render_task() takes 2 positional arguments but 3 were given`)
- **Issue:** Initial tests called `task.run(mock_self, request_dict)` but with `bind=True`, `task.run()` already receives `self` as the Celery task instance; passing `mock_self` as first arg is wrong
- **Fix:** Rewrote tests to use `task.apply(args=[request_dict], task_id=...)` which runs the task synchronously in Celery's eager mode with correct `self` binding
- **Files modified:** `apps/worker/tests/test_render_task.py`
- **Verification:** All 8 render task tests pass
- **Committed in:** `3413c6e`

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both required for correct test operation. No scope creep.

## Known Stubs

`tasks/render.py` is a skeleton — the render pipeline stages (NLP, Geometry, Renderer, Optimizer, Export) are stubbed with `# Future:` comments. This is intentional per the plan spec: "For now, implement as a skeleton that publishes progress stages and returns a mock RenderResult. Full pipeline wiring is integration work beyond this plan." The skeleton returns an empty `RenderResult` with zero scores and empty `placed_words`. The stub is tracked and will be wired in the integration plans (12-05, 12-06).

## Threat Flags

None — all STRIDE mitigations applied:
- T-12-03-01 (DoS): `time_limit=300` in `task_annotations` for render tasks
- T-12-03-02 (DoS): `--max-tasks-per-child=50` in worker-entrypoint.sh
- T-12-03-03 (Tampering): `RenderRequest.model_validate(request_dict)` at task entry
- T-12-03-04 (DoS): `worker_prefetch_multiplier=1` in celery_app.py

## Next Phase Readiness

- `render_task` is registered on `realtime` queue and ready for dispatch from FastAPI endpoint (Plan 05)
- Progress channel `render:progress:{task_id}` is ready for SSE consumption (Plan 05)
- `worker-entrypoint.sh` is production-ready for Docker image builds

---
*Phase: 12-production-v1*
*Completed: 2026-04-22*
