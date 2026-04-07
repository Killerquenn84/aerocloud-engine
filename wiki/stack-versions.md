---
title: Stack Versions (Codex-Verified)
tags: [stack, versions, dependencies, polyglot, python, rust, typescript]
source: .planning/research/STACK.md
verified_by: Codex CLI
verified_on: 2026-04-07
---

# Stack Versions — Codex-Verified

> Jede Version hier wurde von Codex CLI gegen PyPI / offizielle Upstream-Quellen live verifiziert am 2026-04-07.
> Gemini hatte initial einige Versionen halluziniert — siehe [codex-corrections.md](codex-corrections.md).
> Vor jedem Dependency-Update: diese Seite lesen und gegen aktuelle PyPI-Stände prüfen.

## Polyglot-Uebersicht

| Schicht | Sprache | Zweck |
|---------|---------|-------|
| Engine-Kern | Python 3.11 | PyTorch Inner Loop, MAP-Elites, BERT, spaCy |
| API | FastAPI (Python) | HTTP Endpoints, Job-Management |
| Browser-Preview | Rust → WASM | <100ms Echtzeit-Spirale + Quadtree |
| Frontend | Next.js 16 / TypeScript | UI, Three.js Animation, Pareto-Slider |
| GPU-Worker | NVIDIA-Docker + Celery + Redis | Async Jobs |
| Datenhaltung | PostgreSQL 16 + pgvector | BERT-Vektoren + MAP-Elites Archiv |

## Core ML Stack (Python)

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `python` | 3.11 | CPython, mypy --strict |
| `torch` | 2.7.1 | **NICHT** latest 2.10 — CUDA-drift mitigation |
| `nvdiffrast` | 0.3.3.1 | **NICHT** 0.4.0 — existiert nicht. Build/Runtime-Fragilität, NVIDIA Source Code License |
| `transformers` | 5.5.0 | Matrix-Test gegen torch updates |
| `sentence-transformers` | 5.3.0 | für `all-MiniLM-L6-v2` |
| `pyribs` | latest stable | + `pymoo` für BOP-Elites emitter |
| `POT` | 0.9.6.post1 | **NICHT** 1.0.2 — existiert nicht. Sinkhorn-Knopp in log-space |
| `spacy` | 3.x current | **NICHT** 4.x — existiert nicht |
| `scipy` | 1.17.x | für Meijster EDT via `distance_transform_edt` |
| `scikit-fmm` | 2025.6.23 | **NICHT** 2025.12 — existiert nicht. Fast Marching Method für MAT |
| `numpy` | 2.4.x | strict pin für nvdiffrast |
| `scikit-learn` | 1.8.x | |
| `opencv-python-headless` | 4.12.x | |
| `Pillow` | 12.1.1 | |

## Export Stack

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `svgelements` | latest | **Ersetzt** `svgwrite` (inaktiv seit 2022) |
| `reportlab` | 4.3.x | PDF sub-millimeter Präzision |
| `lxml` | latest | direkte XML-Kontrolle wenn nötig |

## API / Backend Stack

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `fastapi` | 0.115.x | |
| `uvicorn[standard]` | 0.43.0 | |
| `pydantic` | 2.12.5 | |
| `pydantic-settings` | latest | Config Management |
| `celery[redis]` | 5.6.2 | minimal konfiguriert |
| `redis[hiredis]` | 7.3.0 | |
| `asyncpg` | 0.31.0 | |
| `pgvector` | 0.4.2 | HNSW Index, nicht IVFFlat |
| `alembic` | latest | Migrations mit `CREATE EXTENSION vector` |

## Observability Stack

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `structlog` | latest | **KEIN** loguru Hybrid (Codex blockiert) |
| `opentelemetry-sdk` | latest | Tracing zwingend (nicht nur Metrics) |
| `prometheus_client` | latest | Metrics |
| NVIDIA DCGM Exporter | 3.4+ | GPU Metrics |

## Utility Stack

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `orjson` | 3.11.x | schnelle JSON Serialisierung |
| `tenacity` | 9.x | Retry-Logik |
| `nh3` | 0.3.3 | HTML/SVG Sanitizer |
| `safetensors` | latest | **Ersetzt** `pickle` für Model Checkpoints |

## Code Quality

| Tool | Version | Bemerkung |
|------|---------|-----------|
| `mypy` | latest | strict mode |
| `ruff` | latest | **Lint UND Format** — kein Black doppelt |
| `pytest` | latest | Unit Tests |
| `hypothesis` | latest | Property-Based Tests |
| `mutmut` | 3.5.0 | **gezielt** auf Loss/SDF/Collision/Pareto/Export |
| `testcontainers` | latest | Integration mit realem Postgres+Redis |

## Frontend / Build Stack

| Package | Version | Bemerkung |
|---------|---------|-----------|
| `Next.js` | 16 | **NICHT** 14 — seit 2025-10-21 verfügbar |
| `pnpm` | latest | |
| `wasm-bindgen` | latest | |
| `wasm-pack` | latest | |
| `Cargo` (Rust) | Edition 2021 | WASM Preview only |

## Container Base Images

- `nvidia/cuda:12.x-base-ubuntu22.04` — SHA-pinned
- Multi-stage Builds: build stage kompiliert, runtime stage minimal
- CI Matrix-Tests auf Python + CUDA + Torch Kombinationen

## Build-Orchestrierung

- `uv` workspace für Python Monorepo
- `Cargo` workspace für Rust Crates
- `pnpm` workspace für TypeScript Apps
- **Turborepo:** Aufgeschoben bis JS-Task-Orchestrierung wirklich weh tut (Codex-Empfehlung)

## Architektur-Empfehlung

Engine-Kern: **nvdiffrast (mit strikter Versions-Pinning)** + **pyribs (custom BOP-Elites wrapper)** + **POT (Sinkhorn-Knopp)**.

Queue: **Celery 5.6.2 minimal** — erforderlich für nächtliches Self-Play Scheduling (Blueprint Teil VIII).

Logging: **nur structlog** — Codex blockierte den loguru-Hybrid.

Frontend: **Next.js 16** — Codex erkannte die veraltete v14 Gemini-Angabe.

## Siehe auch

- [codex-corrections.md](codex-corrections.md) — die 6 entlarvten Halluzinationen als Lessons Learned
- `.planning/research/STACK.md` — vollständige Research-Output mit Rationale
- `.planning/research/SUMMARY.md` — Cross-Cutting Risks
- `docs/ai-team-decisions.md` — Log der 3-KI Entscheidungen
