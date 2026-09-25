# AeroCloud Engine

## What This Is

AeroCloud Engine is a self-learning word cloud rendering engine that solves the 2D Irregular Bin Packing Problem (NP-hard) through a Dual-Loop architecture: a PyTorch GPU-accelerated Inner Loop with Differentiable Rendering (Exploitation), and an asynchronous Quality-Diversity Outer Loop using MAP-Elites + CQD metrics (Exploration). It is a standalone project that implements the full mathematical vision of the AeroCloud Blueprint — no scope reduction, no feature deferral.

## Core Value

Mathematically optimal word placement in arbitrary silhouettes through GPU-accelerated differentiable optimization, exploring the entire continuous solution space (not a single optimum) via Quality-Diversity algorithms — producing not one word cloud, but an archive of diverse, aesthetically and semantically distinct interpretations of any input text.

## Requirements

### Validated

(None yet — ship to validate)

### Active (v1 — the full Blueprint vision)

**Mathematical Foundations (Blueprint Teil I):**
- [ ] Zipf-law logarithmic normalization for word frequency (linear is mathematically wrong for power-law data)
- [ ] TF-IDF-AP scoring with positional weighting (`w(t,d) = TF * IDF * P_weight`, +12.9% semantic precision)
- [ ] NLP pipeline: tokenization/lemmatization (spaCy), stopword removal, frozen `reference_weights` tensor

**Semantic Vector Space (Blueprint Teil II):**
- [ ] BERT embeddings via `sentence-transformers/all-MiniLM-L6-v2`
- [ ] Cosine similarity for semantic distance
- [ ] t-SNE / UMAP projection to 2D for warm-start initialization
- [ ] Sinkhorn-Knopp Optimal Transport replacing Force-Directed Layouts (deterministic, with convergence guarantee)

**Shape Analysis — The Skeleton (Blueprint Teil III):**
- [ ] Signed Distance Field (SDF) generation with gradient pointing to nearest contour
- [ ] Medial Axis Transform (MAT) extracting topological skeleton
- [ ] Multi-Centric Wordle: separate spiral origins per non-convex sub-region
- [ ] Rust/WASM real-time engine (Archimedean spiral, 1-bit mask in 32-bit ints, quadtree, <100ms browser preview)

**Collision Detection (Blueprint Teil IV — full 5-stage hierarchy):**
- [ ] Stage 1: AABB Bounding Boxes — O(1) per pair
- [ ] Stage 2: Two-Level Box (EdWordle) — O(n) with BVH
- [ ] Stage 3: Quadtree Spatial Index — O(n log n)
- [ ] Stage 4: SAT (Separating Axis Theorem) — O(n·k)
- [ ] Stage 5: Bitmap + 32-bit INT — O(n·m/32), pixel-exact
- [ ] BVH tree + LRU cache

**Inner Loop — The Muscles (Blueprint Teil V):**
- [ ] Tensor architecture: position (x,y), scale (s), rotation (θ) as learnable tensors with `requires_grad=True`
- [ ] Soft-Rasterization: `I(x,y) = ∫∫ k(u,v) · f(x-u, y-v; Θ) du dv`
- [ ] Four-part Loss function: `L_total = α·L_wmse + β·L_overlap + γ·L_fidelity + λ·L_temporal`
  - L_wmse (Boundary Fitness): shape "sucks" words inward
  - L_overlap (Primitive Overlap): `ReLU(density - 1.0)²`
  - L_fidelity (Data Fidelity): `1 - cos_sim(S_ref, S_upd)` — prevents artificial inflation
  - L_temporal (Temporal Coherence): penalizes position changes for live feeds
- [ ] Adam Optimizer (α=0.001, β1=0.9, β2=0.999, ε=10⁻⁸)
- [ ] Coarse-to-Fine pipeline: 8px → 32px → 128px → target (~10x speedup, ~100 epochs convergence)

**Seam Carving (Blueprint Teil VI):**
- [ ] Energy function: `E(x,y) = Σ wᵢ · Gauss(distance)`
- [ ] Optimal seam via Dynamic Programming, O(w·h)

**Quality Metrics (Blueprint Teil VII):**
- [ ] Geometric: LC, LU, SS, Compactness, Aspect Ratio (target → φ ≈ 1.618)
- [ ] Semantic: Realized Adjacencies (Cycle Cover), Distortion
- [ ] Meta: CQD-Score, CQD_β, CQD_HV

**Outer Loop — The Evolution (Blueprint Teil VIII):**
- [ ] CQD equation: `ω(x, G, θ) = f(x)/|f_max - f_min| - θ · δ(g(x), G)/δ_max`
- [ ] CQD-Score via Monte-Carlo: `CQD = (1/NM) · Σ_n Σ_m ω(x^r, G_n, θ_m)`
- [ ] MAP-Elites grid axes: shape fidelity, rotation, symmetry, semantics
- [ ] BOP-Elites: 700 evaluations equivalent to MAP-Elites at 90,000
- [ ] Self-Play training (nightly): Monte-Carlo sampling → mutation → evaluation → archive update

**Pareto-Front (Blueprint Teil IX):**
- [ ] `CQD_HV = Σ_G HV(S_HV(G))`
- [ ] Pareto-Slider: design fidelity ↔ packing density

**Export (Blueprint Teil X):**
- [ ] Seam Carving + Bezier intersection optimization
- [ ] Sub-millimeter precision SVG / PDF / PNG output

**IT Infrastructure (Blueprint Teil XI):**
- [ ] Frontend: Next.js 14 / React / Tailwind
- [ ] Browser preview: Rust/WASM (compiled module)
- [ ] Animation: Three.js / WebGL
- [ ] API: FastAPI (Python)
- [ ] GPU Worker: PyTorch/CUDA + Celery + Redis
- [ ] Training datastore: PostgreSQL with pgvector + MAP-Elites archive

### Out of Scope

| Item | Why |
|------|-----|
| Alternative loss formulations | Blueprint specifies the four-part loss; no experimentation in v1 |
| Force-directed layouts | Blueprint explicitly replaces these with Sinkhorn-Knopp Optimal Transport |
| Linear or sqrt frequency normalization | Mathematically wrong for Zipf-distributed data per Blueprint Teil 1.2 |
| Unlimited word rotation | Out of scope to keep readability; rotation handled via differentiable θ tensors |
| Non-deterministic outputs | Seeded reproducibility required for Self-Play training and merchant trust |
| Cross-shop data leakage | Strict tenant isolation required |
| Single-optimum solvers | Project's core thesis is Quality-Diversity, not single-optimum |

## Context

- **Standalone project.** No parent system, no upstream caller, no inherited constraints. The engine owns its full stack from data model to frontend.
- **Blueprint location:** `raw/sources/AeroCloud-Blueprint.md` (191 lines, 11 parts) — the canonical mathematical and architectural specification
- **Existing codebase state:** Wiki-tooling (`wiki:ingest`, `wiki:query`, `wiki:lint`) is implemented in TypeScript; engine modules (`src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/export/`) are stubs. Wiki tooling stays in TypeScript; engine core is built in Python.
- **3-AI team workflow:** Claude Code (orchestrator + code writer), Gemini (researcher + knowledge support), Codex (code reviewer + critic). Every architectural decision goes through 3-AI consensus before implementation.
- **Knowledge Wiki:** Karpathy LLM Wiki pattern with nightly deep research; Blueprint is the immutable source in `raw/sources/`, wiki/ is LLM-maintained living reference.
- **Self-evolution:** Engine produces an MAP-Elites archive that improves over time via nightly Self-Play training, not a static algorithm.

## Constraints

- **Runtime — Engine Core:** Python 3.11 (CPython, no PyPy/Cinder); ESM-style strict typing (`mypy --strict`)
- **Runtime — Frontend:** Node.js 22 LTS, TypeScript 5.7+ ESM, Next.js 14 App Router
- **Runtime — Native Helpers / Browser Preview:** Rust Edition 2021 compiled to WASM (no PyO3 in Inner Loop hot path — Rust only for Preview/WASM and isolated native helpers)
- **GPU:** NVIDIA CUDA 12.1+ runtime in Docker; on-demand GPU instances on Hostinger Cloud (NVIDIA-Docker, host-driver passthrough)
- **CPU fallback:** Engine must run (slower) without GPU for development and CI
- **Database:** PostgreSQL 16 + pgvector (BERT embeddings, MAP-Elites archive)
- **Queue / Broker:** Redis 7 + Celery 5.6+ (async GPU job dispatch, nightly Self-Play)
- **API:** FastAPI 0.115+, async I/O for HTTP layer; Celery workers are sync at task boundary (asyncio + Celery anti-pattern explicitly avoided)
- **Frontend:** Next.js 14 + React 18 + Tailwind + Three.js
- **Pinned Python dependencies (Codex-validated, April 2026):**
  - `torch==2.7.1` (NOT latest — CUDA-drift mitigation)
  - `transformers==5.5.0`, `sentence-transformers==5.3.0`
  - `fastapi==0.115.*`, `uvicorn[standard]==0.43.0`, `pydantic==2.12.5`
  - `celery[redis]==5.6.2`, `redis[hiredis]==7.3.0`
  - `asyncpg==0.31.0`, `pgvector==0.4.2`
  - `numpy==2.4.3`, `scipy==1.17.1`, `scikit-learn==1.8.0`
  - `opencv-python-headless==4.12.*`, `Pillow==12.1.1`
  - `orjson==3.11.*`, `tenacity==9.*`, `nh3==0.3.3`
- **Code quality (mandatory):** `mypy --strict`, `ruff` (lint AND format — no Black double-format), `pytest`, `hypothesis` (property tests), `coverage.py` with hard gate, `mutmut==3.5.0` targeted at critical modules (Loss, SDF, Collision, Pareto-Ranking, Export geometry)
- **Process management:** PM2 not used (Python ecosystem); `systemd` units + Celery beat for production scheduling
- **Reproducibility:** Every render carries a seed; `(input, seed, version) → output` must be deterministic for Self-Play training quality
- **Workflow:** TDD/BDD strict — failing test must exist before implementation; 3-AI peer review before merge per CLAUDE.md Sections 1, 6, 7
- **Communication:** All Telegram updates to Jens go via `bash scripts/telegram-send.sh` (token in `.env.telegram`, never in commands)
- **Deployment:** Hostinger Cloud VPS, NVIDIA-Docker with host-driver passthrough, multi-stage Docker builds (build on potent machine, push slim runtime image)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Polyglot stack (Python + Rust + TypeScript) | No single language covers Differentiable Rendering (PyTorch), real-time geometry (Rust/WASM), and modern frontend (Next.js) | -- Pending |
| Python is engine core, Rust only for Preview/WASM | PyO3 ABI breakage risk too high for Inner Loop hot path; Codex review (Anti-Sycophancy) | -- Pending |
| Sinkhorn-Knopp replaces Force-Directed | Blueprint Teil 2.2 — deterministic, convergence guarantee, mathematically optimal | -- Pending |
| Logarithmic Zipf normalization (not linear/sqrt) | Blueprint Teil 1.2 — power-law data requires log normalization | -- Pending |
| 12 Phases with iterative reification per domain | 3-AI consensus: full v1 vision is non-negotiable, but `Geometry-v1 → Geometry-v2`, `Outer-Loop-v1 → Outer-Loop-v2` prevents "optimizing chaos" (Codex) while keeping all Blueprint features in v1 | -- Pending |
| `torch==2.7.1` not latest 2.10 | CUDA-drift mitigation; Codex-recommended conservative pinning | -- Pending |
| Ruff for lint AND format (no Black) | Two formatters create friction; Codex recommendation | -- Pending |
| Mutation testing targeted, not global | Mutmut on Loss/SDF/Collision/Pareto/Export only — global mutation testing is time-prohibitive | -- Pending |
| asyncio + Celery strictly separated | FastAPI async / Celery sync task boundary / GPU own worker pool — avoids classic anti-pattern | -- Pending |
| Rendering output is reproducible (seeded) | Self-Play training and merchant trust require `(input, seed, version) → output` determinism | -- Pending |
| Engine bottom-up build order | 3-AI consensus: Geometry → NLP → Inner Loop → Outer Loop → Export. Top-down would build the optimizer before the data it optimizes | -- Pending |

## Roadmap Preview (12 Phases — full detail in ROADMAP.md)

3-AI consensus, with iterative reification within v1:

| # | Phase | Domain | Notes |
|---|-------|--------|-------|
| 1 | Foundation | Tooling | Python+CUDA Docker, monorepo, pinned versions, mypy/ruff/pytest CI |
| 2 | Datenmodell + Wiki | Data | Pydantic models (Tokens, Shapes, Constraints, Scores, Seeds), wiki self-maintenance |
| 3 | NLP-v1 | NLP | TF-IDF-AP, Zipf log-normalization, stopwords, lemmatization (spaCy) |
| 4 | Geometry-v1 | Geometry | SDF (Meijster EDT), AABB collision, simple placement |
| 5 | Renderer-v1 | Renderer | PyTorch Soft-Rasterizer, learnable tensors (x/y/s/θ), forward pass |
| 6 | Inner Loop-v1 | Optimizer | 4-part Loss + Adam + Coarse-to-Fine 8→32→128→target |
| 7 | Geometry-v2 | Geometry | MAT, Multi-Centric Wordle, full 5-stage collision, Bezier paths |
| 8 | Semantic Vector | NLP | BERT all-MiniLM-L6-v2, Sinkhorn-Knopp Optimal Transport, t-SNE/UMAP warm-start |
| 9 | Outer Loop-v1 | Optimizer | MAP-Elites grid, feature descriptors, archive, LC/LU/SS/Compactness |
| 10 | Self-Play | Optimizer | Nightly Monte-Carlo sampling → mutation → evaluation → archive update |
| 11 | Outer Loop-v2 | Optimizer | BOP-Elites, CQD-Score Monte-Carlo, Pareto-Front, CQD_HV, Pareto-Slider |
| 12 | Production v1 | Export + API | Seam Carving + Bezier SVG/PDF, FastAPI + Celery + Redis + pgvector, NVIDIA-Docker, load tests, golden sets, release gate |

**Phase exit gate (Codex recommendation, applied to all 12):**
- All `pytest` + `hypothesis` tests green
- Wiki updated with phase findings
- Stable interfaces (no breaking changes downstream)
- Benchmark vs prior phase (no regression in determinism or quality)
- 3-AI peer review approved

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Mark with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-07 after 3-AI consensus (Claude + Gemini + Codex)*
