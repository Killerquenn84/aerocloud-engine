# Stack Research — AeroCloud Engine

**Researched by:** Gemini CLI (initial proposal) + Codex CLI (version verification via PyPI/upstream)
**Date:** 2026-04-07
**Stack focus:** Python polyglot for full Blueprint v1 vision

> ⚠️ Codex validated all versions against live PyPI / upstream. Versions in this document are the verified ones. Gemini's initial picks were partly hallucinated and have been corrected.

## 1. Differentiable Rendering — `nvdiffrast` 0.3.3.1

**Recommendation:** nvdiffrast (with caveats).

- Latest verified PyPI: **0.3.3.1** (2024-12-06) — Gemini's "0.4.0" does not exist
- Highest performance through CUDA-fused kernels
- **Risk (Codex):** Build/runtime fragility — CUDA, PyTorch ABI, driver versions, CI reproducibility are real concerns
- **Risk (Codex):** NVIDIA Source Code License, low upstream openness
- **Mitigation:** Pin `numpy`, `torch`, CUDA toolchain exactly; CI matrix tests on every Torch update; consider PyTorch3D as fallback

**Alternative:** PyTorch3D 0.8.x (more flexible for 3D, slower for 2D)

## 2. Quality-Diversity — `pyribs` (latest)

**Recommendation:** pyribs.

- Industry standard 2026 for QD optimization
- **BOP-Elites caveat (Codex):** pyribs has `BayesianOptimizationEmitter` based on EJIE (Expected Joint Improvement of Elites). This is NOT the same as "BOP-Elites as a finished recipe". Requires extra `pymoo` dependency, only supports certain archive types.
- **Implementation note:** May need a thin wrapper to implement BOP-Elites semantics on top of `BayesianOptimizationEmitter`
- Excellent scaling through NumPy 2.x vectorization
- `qdpy` rejected: slower maintenance, less PyTorch-optimized

## 3. Optimal Transport — `POT` 0.9.6.post1

**Recommendation:** POT (Python Optimal Transport).

- Latest verified PyPI: **0.9.6.post1** (2025-09-22) — Gemini's "1.0.2" does not exist
- Highly optimized Sinkhorn-Knopp with CUDA support
- Stable numerical regularization (log-space)
- For AeroCloud (up to 5000 words) POT is the clear choice over hand-rolled

## 4. NLP for German + English — `spaCy` 3.x + `transformers`

**Recommendation:** spaCy 3.x (current stable), NOT 4.x.

- Codex verification: official spaCy site shows v3.x; "v4.1" was Gemini hallucination
- Models: `de_dep_news_trf` and `en_core_web_trf` (trf = transformer-based)
- **Codex caveat:** spaCy trf-models are heavyweight. For retrieval / entity extraction a lighter setup with targeted transformer calls may be cheaper and more stable. Reassess after Phase 3.
- `spacy-transformers` integrates natively into PyTorch pipeline

## 5. SDF (Signed Distance Field) — `scipy.ndimage.distance_transform_edt`

**Recommendation:** scipy distance_transform_edt (from `scipy>=1.17`)

- Implements exact Meijster algorithm in O(n)
- `cv2.distanceTransform` is faster but deviates on serif glyph contours
- Sub-millimeter export precision requires SciPy

## 6. MAT (Medial Axis Transform) — `scikit-fmm` 2025.6.23

**Recommendation:** scikit-fmm.

- Latest verified PyPI: **2025.6.23** (2025-06-23) — Gemini's "2025.12" does not exist
- Uses Fast Marching Method (FMM)
- Ideal for Multi-Centric Wordles
- More robust than Voronoi-based approaches on noisy glyph edges

## 7. SVG / PDF Export — `svgelements` + `ReportLab`

**Recommendation:** svgelements + ReportLab. **NOT svgwrite.**

- Codex verification: `svgwrite` latest is 1.4.3 (2022-07-14) and PyPI marks it **inactive**
- **Replacement:** `svgelements` (active, well-maintained), or direct XML generation via `lxml.etree`
- **PDF:** ReportLab (current) is the standard for sub-millimeter print precision
- `cairosvg` only for conversion, not generative path creation

## 8. Rust + WASM (Browser Preview)

**Versions (current April 2026):**
- `wasm-bindgen` (latest)
- `wasm-pack` (latest)
- `web-sys` (latest)

**Next.js integration:**
- Build with `wasm-pack --target web`
- Load in Next.js via `dynamic(() => import(...), { ssr: false })`
- `experiments.asyncWebAssembly = true` in `next.config.mjs`

## 9. PostgreSQL pgvector — HNSW Index

**Recommendation:** HNSW (NOT IVFFlat).

- BERT 384-dim embeddings: HNSW achieves recall >98% at low latency
- Moderate RAM overhead acceptable
- For <1M entries per tenant, HNSW outperforms IVFFlat clearly

## 10. Observability — `structlog` only (NOT hybrid)

**Recommendation:** structlog + stdlib logging. **NOT structlog + loguru hybrid.**

- Codex critique: Two logging abstractions create double handlers, inconsistent context propagation, operational noise
- `structlog` for structured JSON logs (OpenTelemetry compatible) — production
- `prometheus_client` + NVIDIA DCGM Exporter for GPU metrics
- **Required addition (Codex):** OpenTelemetry tracing — metrics alone are not enough

## 11. Frontend — `Next.js` 16

**Recommendation:** Next.js 16.

- Codex verification: Next.js 16 released 2025-10-21 — Gemini's "v14" is outdated
- App Router default
- WASM module loading via `experimental.asyncWebAssembly`

## 12. Task Queue — Decision Pending (Celery vs Dramatiq vs RQ)

**Codex critique:** Celery may be overkill for v1. Celery Beat + Self-Play sounds like "early orchestration bloat".

**Options:**
- **Celery 5.6.2** + Redis — most powerful, complex routing/retry/ETA patterns, big ecosystem
- **Dramatiq** — simpler, fewer features, less surface area
- **RQ** — simplest, plain Python

**Decision criterion:** Required only if v1 needs nightly Self-Play scheduling (Blueprint Teil VIII). Self-Play implies recurring jobs → Celery Beat or systemd timer is needed. Recommendation: **Celery 5.6.2** to keep optionality, but configure minimally.

## 13. Type Checking & Linting (Codex addition)

- **`mypy --strict`** for type checking (or `pyright` as faster alternative)
- **`ruff`** for both lint AND format (no Black double-format)
- `pytest` + `hypothesis` for property tests
- `mutmut` targeted at critical modules only (Loss, SDF, Collision, Pareto-Ranking, Export)

## 14. Migrations (Codex addition)

- **Alembic** for SQL schema
- Migrations must explicitly `CREATE EXTENSION IF NOT EXISTS vector`
- Version archive tables (`archive_v1`, `archive_v2`)

## 15. Container Strategy (Codex addition)

- Pinned NVIDIA CUDA base images (e.g. `nvidia/cuda:12.x-base-ubuntu22.04`)
- Multi-stage builds: build stage compiles, runtime stage minimal
- CI matrix tests on Python + CUDA + Torch combinations
- SHA-pinned base image references

## Final Pin List (Codex-verified, April 2026)

| Package | Version | Notes |
|---------|---------|-------|
| `python` | 3.11 | CPython |
| `torch` | 2.7.1 | NOT latest (CUDA-drift mitigation) |
| `transformers` | 5.5.0 | matrix-test against torch updates |
| `sentence-transformers` | 5.3.0 | for `all-MiniLM-L6-v2` |
| `nvdiffrast` | 0.3.3.1 | risky, monitor upstream |
| `pyribs` | latest stable | + `pymoo` for BOP-Elites emitter |
| `POT` | 0.9.6.post1 | Sinkhorn-Knopp |
| `spacy` | 3.x current | NOT 4.x (does not exist) |
| `scipy` | 1.17.x | for Meijster EDT |
| `scikit-fmm` | 2025.6.23 | NOT 2025.12 |
| `numpy` | 2.4.x | strict pin for nvdiffrast |
| `scikit-learn` | 1.8.x | |
| `opencv-python-headless` | 4.12.x | |
| `Pillow` | 12.1.1 | |
| `svgelements` | latest | replaces svgwrite |
| `reportlab` | 4.3.x | PDF |
| `lxml` | latest | direct XML control if needed |
| `fastapi` | 0.115.x | |
| `uvicorn[standard]` | 0.43.0 | |
| `pydantic` | 2.12.5 | |
| `pydantic-settings` | latest | config |
| `celery[redis]` | 5.6.2 | minimal config |
| `redis[hiredis]` | 7.3.0 | |
| `asyncpg` | 0.31.0 | |
| `pgvector` | 0.4.2 | HNSW index |
| `alembic` | latest | migrations + CREATE EXTENSION vector |
| `structlog` | latest | NO loguru hybrid |
| `opentelemetry-sdk` | latest | tracing required (Codex) |
| `prometheus_client` | latest | metrics |
| `orjson` | 3.11.x | fast JSON |
| `tenacity` | 9.x | retry |
| `nh3` | 0.3.3 | sanitizer |
| `safetensors` | latest | NOT pickle for model checkpoints |
| `mypy` | latest | strict mode |
| `ruff` | latest | lint + format (no Black) |
| `pytest` | latest | unit |
| `hypothesis` | latest | property tests |
| `mutmut` | 3.5.0 | targeted mutation |
| `testcontainers` | latest | integration with real Postgres+Redis |

## Frontend / Build

| Package | Version |
|---------|---------|
| `Next.js` | 16 (NOT 14) |
| `pnpm` | latest |
| `wasm-bindgen` | latest |
| `wasm-pack` | latest |
| `Cargo` (Rust) | Edition 2021 |

## Architecture Recommendation Summary

**Engine core:** nvdiffrast (with version pinning) + pyribs (with custom BOP-Elites wrapper) + POT for OT.

**Queue:** Celery 5.6.2 minimal — only because Self-Play scheduling is non-negotiable per Blueprint Teil VIII.

**Logging:** structlog only — Codex blocked the loguru hybrid.

**Frontend:** Next.js 16 (Codex caught the outdated v14).

**Build orchestration:** uv workspace + Cargo + pnpm. Turborepo deferred until JS task orchestration genuinely hurts (Codex).

---
*Initial research by Gemini CLI 2026-04-07. Versions verified by Codex CLI same day.*
