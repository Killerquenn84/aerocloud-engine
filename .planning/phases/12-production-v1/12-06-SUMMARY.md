---
phase: 12-production-v1
plan: "06"
subsystem: infra
tags: [docker, nvidia, dcgm, gpu-metrics, prometheus, celery, fastapi, healthcheck]

# Dependency graph
requires:
  - phase: 12-production-v1/12-03
    provides: worker-entrypoint.sh (Celery entrypoint script COPYed into worker image)

provides:
  - DCGM Exporter sidecar service (nvcr.io/nvidia/k8s/dcgm-exporter:3.6.2) in docker-compose
  - STOPSIGNAL SIGTERM on worker.Dockerfile (Celery warm shutdown)
  - HEALTHCHECK on worker.Dockerfile (celery inspect ping)
  - STOPSIGNAL SIGTERM on api.Dockerfile (uvicorn graceful shutdown)
  - HEALTHCHECK on api.Dockerfile (curl /health)
  - runtime: nvidia + CUDA_VISIBLE_DEVICES=0 on worker service
  - stop_grace_period: 30s on worker service for clean drain

affects:
  - 12-production-v1 (monitoring, deployment, smoke-tests)
  - Prometheus scrape config (port 9400 dcgm-exporter endpoint)

# Tech tracking
tech-stack:
  added:
    - nvcr.io/nvidia/k8s/dcgm-exporter:3.6.2-3.4.2-ubuntu22.04
    - curl (installed in api.Dockerfile runtime for HEALTHCHECK)
  patterns:
    - Sidecar pattern: DCGM Exporter runs alongside worker, scrapes GPU metrics via port 9400
    - Docker STOPSIGNAL + stop_grace_period for graceful Celery/uvicorn drain
    - HEALTHCHECK in Dockerfile for container-level liveness detection

key-files:
  created: []
  modified:
    - infra/docker/docker-compose.yml
    - infra/docker/worker.Dockerfile
    - infra/docker/api.Dockerfile

key-decisions:
  - "DCGM Exporter 3.6.2 chosen over older tags — includes k8s_container_name label rename and CVE-2026-2184 patch"
  - "SYS_ADMIN cap on dcgm-exporter accepted: required by DCGM to read GPU hardware counters; container on trusted internal network (T-12-06-01)"
  - "GPU metrics (utilization/memory/temperature) treated as operational data, not secrets (T-12-06-02)"
  - "curl installed in api runtime stage to provide HEALTHCHECK dependency without shell trickery"
  - "HEALTHCHECK celery inspect ping with -t 5 (probe timeout) < Docker timeout 10s to avoid false negatives"

patterns-established:
  - "STOPSIGNAL SIGTERM: both Dockerfiles declare explicit SIGTERM to ensure signal routing to PID 1 process"
  - "HEALTHCHECK internal timeout < Docker timeout: prevents Docker marking healthy-but-slow containers as dead"

requirements-completed:
  - PROD-19

# Metrics
duration: 12min
completed: 2026-04-22
---

# Phase 12 Plan 06: DCGM Exporter Sidecar + Dockerfile Hardening Summary

**DCGM Exporter 3.6.2 sidecar wired into docker-compose alongside GPU worker; both Dockerfiles hardened with STOPSIGNAL SIGTERM and HEALTHCHECK directives**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-22T00:09:00Z
- **Completed:** 2026-04-22T00:21:30Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Added `dcgm-exporter` sidecar service to docker-compose.yml using NVIDIA-official 3.6.2 image (k8s_container_name label fix + CVE-2026-2184 patch) with SYS_ADMIN cap and depends_on worker
- Hardened worker service with `runtime: nvidia`, `CUDA_VISIBLE_DEVICES: "0"`, `entrypoint`, `stop_signal: SIGTERM`, and `stop_grace_period: 30s`
- Added `STOPSIGNAL SIGTERM` + `HEALTHCHECK` (celery inspect ping) to worker.Dockerfile; COPYed worker-entrypoint.sh with chmod +x
- Added `STOPSIGNAL SIGTERM` + `HEALTHCHECK` (curl /health) to api.Dockerfile; installed curl in runtime stage

## Task Commits

Each task was committed atomically:

1. **Task 1: DCGM Exporter sidecar + Dockerfile hardening** - `9778607` (feat)

## Files Created/Modified
- `infra/docker/docker-compose.yml` - Added dcgm-exporter sidecar service; hardened worker service with nvidia runtime, CUDA env, entrypoint, stop_signal, stop_grace_period
- `infra/docker/worker.Dockerfile` - Added STOPSIGNAL SIGTERM, HEALTHCHECK (celery inspect ping), COPY + chmod of worker-entrypoint.sh
- `infra/docker/api.Dockerfile` - Added STOPSIGNAL SIGTERM, HEALTHCHECK (curl /health), curl installed in runtime stage

## Decisions Made
- Used DCGM Exporter 3.6.2 (not 3.3.x or 3.5.x): 3.6.2 is the first tag that renames the Prometheus label from `container_name` to `k8s_container_name` AND includes CVE-2026-2184 fix
- `curl` added to api runtime stage (not builder): health check runs at runtime, builder doesn't need it; keeps image layers clean
- HEALTHCHECK internal timeout set to 5s (celery -t 5) and Docker timeout to 10s — inner timeout fires first, giving Docker a clean exit code rather than a hung probe

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DCGM Exporter sidecar is ready; Prometheus scrape config for port 9400 is owned by the monitoring plan
- Dockerfiles are production-hardened; health probes will work once the actual FastAPI /health endpoint is implemented in the API plan
- Worker graceful shutdown (30s drain window) is in place for Celery in-flight task protection

---
*Phase: 12-production-v1*
*Completed: 2026-04-22*
