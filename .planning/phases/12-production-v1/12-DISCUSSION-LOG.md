# Phase 12: Production v1 - Discussion Log (Assumptions Mode)

> Audit trail only.

**Date:** 2026-04-21
**Phase:** 12-production-v1
**Mode:** assumptions (--auto)

## Auto-Resolved
- Export pipeline (Confident → export/ subpackage, svgelements + reportlab + shapely)
- FastAPI surface (Confident → apps/api/, SSE via StreamingResponse + Redis pub/sub)
- Celery worker (Confident → prefork pool, 2 queues, GPU isolation)
- Observability (Likely → OTLP exporter + prometheus-client separate)
- Security (Confident → allow-lists, path traversal prevention, CORS disabled)
