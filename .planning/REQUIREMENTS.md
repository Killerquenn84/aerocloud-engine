# Requirements: AeroCloud Engine

**Defined:** 2026-04-07
**Core Value:** Mathematically optimal word placement in arbitrary silhouettes through GPU-accelerated differentiable optimization, exploring the entire continuous solution space (Quality-Diversity).

## v1 Requirements — Full Blueprint Vision

The Blueprint is the source of truth. Every requirement maps directly to a Blueprint section. NO scope reduction.

### Foundation (Phase 1)

- [ ] **FOUND-01**: `uv` workspace at repo root with shared `uv.lock` for entire monorepo
- [ ] **FOUND-02**: Cargo workspace for Rust crates (initially `packages/preview-wasm`)
- [ ] **FOUND-03**: ~~pnpm workspace for TypeScript apps~~ **SUPERSEDED by Phase 1 CONTEXT.md D-01 (2026-04-07):** hybrid layout keeps existing `npm` package.json at root for wiki tools; pnpm migration is an explicit non-goal for v1. The workspace-level requirement is met under `npm`, not `pnpm`.
- [ ] **FOUND-04**: Multi-stage Dockerfile based on `nvidia/cuda:12.x-base-ubuntu22.04` with pinned SHA digests
- [ ] **FOUND-05**: CI pipeline runs `mypy --strict`, `ruff check`, `ruff format --check`, `pytest`, `pytest --hypothesis-profile=ci`
- [ ] **FOUND-06**: Global `set_seed(seed)` function setting numpy, torch, random, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `torch.use_deterministic_algorithms(True)`
- [ ] **FOUND-07**: PostgreSQL 16 + pgvector available via `docker compose` and Alembic migration creates `vector` extension
- [ ] **FOUND-08**: Redis 7 available via `docker compose` for Celery broker + result backend
- [ ] **FOUND-09**: structlog configured for JSON output, OpenTelemetry SDK initialized at process start
- [ ] **FOUND-10**: Pydantic-Settings v2 loads `.env` for `DATABASE_URL`, `REDIS_URL`, `GPU_DEVICE`, `MODEL_CACHE_DIR`, `LOG_LEVEL`, `SEED`
- [ ] **FOUND-11**: GPU smoke test script verifies `torch.cuda.is_available()` and CUDA capability ≥ 6.0
- [ ] **FOUND-12**: Container has bundled fonts in `assets/fonts/` (no external font URLs at runtime)

### Datenmodell + Wiki (Phase 2)

- [ ] **DATA-01**: Pydantic models for `Token`, `Shape`, `WordCandidate`, `PlacedWord`, `LayoutScore`, `MapElitesEntry`, `RenderRequest`, `RenderResult`
- [ ] **DATA-02**: Reproducibility ID schema: `(input_hash, seed, version) → output_hash`
- [ ] **DATA-03**: Alembic baseline migration with `archive_v1` table (id, descriptor vector, fitness float, metadata jsonb, created_at)
- [ ] **DATA-04**: HNSW index on `archive_v1.descriptor` with tuned `m` and `ef_construction` for 384-dim vectors
- [ ] **DATA-05**: Wiki tooling (`wiki:ingest`, `wiki:query`, `wiki:lint`) integrated into CI to validate Blueprint as living reference
- [ ] **DATA-06**: `safetensors` used exclusively for model checkpoints — `pickle` is forbidden in CI lint rule

### NLP-v1 (Phase 3)

- [ ] **NLP-01**: Tokenization via spaCy 3.x with `de_dep_news_trf` and `en_core_web_trf` models
- [ ] **NLP-02**: Language auto-detection via `franc` or spaCy language detector
- [ ] **NLP-03**: Stopword removal per detected language
- [ ] **NLP-04**: TF-IDF-AP with positional weighting (`w(t,d) = TF * IDF * P_weight`)
- [ ] **NLP-05**: Zipf-law logarithmic font-size normalization (NOT linear, NOT sqrt) with frozen `reference_weights` tensor
- [ ] **NLP-06**: Stem-for-counting / surface-form-for-display data structure
- [ ] **NLP-07**: Corpus-size guard with linear fallback below 20 unique tokens
- [ ] **NLP-08**: Lemmatization quality validated against fixture sentences (DE + EN)

### Geometry-v1 (Phase 4)

- [ ] **GEO-01**: Decode silhouette mask via `Pillow` → numpy binary array
- [ ] **GEO-02**: Generate exact SDF via `scipy.ndimage.distance_transform_edt` (Meijster algorithm)
- [ ] **GEO-03**: Validate SDF correctness against reference fixtures (circle: SDF center = radius ± 1px)
- [ ] **GEO-04**: Module-level LRU cache for SDF (50 entries, key = sha256(maskBuffer))
- [ ] **GEO-05**: AABB collision primitives (Stage 1 of 5-stage hierarchy)
- [ ] **GEO-06**: Simple spiral placement on convex shapes (centroid origin)
- [ ] **GEO-07**: Bounding-box helpers built from pixel-scanned glyph rasters (NOT `measureText` or font metrics)

### Renderer-v1 (Phase 5)

- [ ] **REND-01**: PyTorch tensor representation: position (x, y), scale (s), rotation (θ) with `requires_grad=True`
- [ ] **REND-02**: Soft-Rasterization forward pass via `nvdiffrast` (or PyTorch3D fallback)
- [ ] **REND-03**: Glyph rasterization to scratch canvas with integer-snapped positions for sprite generation
- [ ] **REND-04**: Fonts registered ONCE at process start (module-level Set), never per request
- [ ] **REND-05**: Coarse-resolution forward pass (8px) verified to produce non-NaN output
- [ ] **REND-06**: Gradient flow test: `backward()` on simple input does not raise

### Inner Loop-v1 (Phase 6)

- [ ] **INNER-01**: Four-part Loss function: `L_total = α·L_wmse + β·L_overlap + γ·L_fidelity + λ·L_temporal`
- [ ] **INNER-02**: `L_wmse` (Boundary Fitness): SDF-driven shape attraction
- [ ] **INNER-03**: `L_overlap` (Primitive Overlap): `ReLU(density - 1.0)²`
- [ ] **INNER-04**: `L_fidelity` (Data Fidelity): `1 - cos_sim(S_ref, S_upd)` against frozen reference weights
- [ ] **INNER-05**: `L_temporal` (Temporal Coherence): position-change penalty for live feeds
- [ ] **INNER-06**: Adam optimizer with α=0.001, β1=0.9, β2=0.999, ε=10⁻⁸
- [ ] **INNER-07**: Gradient clipping (`torch.nn.utils.clip_grad_norm_`) enabled for stability
- [ ] **INNER-08**: Coarse-to-Fine pipeline: 8px → 32px → 128px → target resolution
- [ ] **INNER-09**: Convergence detection with early termination on Loss plateau
- [ ] **INNER-10**: Memory hygiene: `.detach()` for metrics, `torch.cuda.empty_cache()` after each resolution stage

### Geometry-v2 (Phase 7)

- [x] **GEO2-01**: Medial Axis Transform via `scikit-fmm` Fast Marching Method
- [x] **GEO2-02**: MAT pruning (Chordal Axis Transform style) for clean topology on noisy edges
- [x] **GEO2-03**: Multi-Centric Wordle: separate spiral origin per MAT branch
- [x] **GEO2-04**: Stage 2 collision: Two-Level Box (EdWordle BVH)
- [x] **GEO2-05**: Stage 3 collision: Quadtree spatial index
- [x] **GEO2-06**: Stage 4 collision: SAT (Separating Axis Theorem) for rotated rectangles
- [x] **GEO2-07**: Stage 5 collision: Bitmap + 32-bit INT pixel-exact
- [x] **GEO2-08**: BVH tree with LRU cache for collision queries
- [x] **GEO2-09**: Bezier path representation for word boundaries

### Semantic Vector Space (Phase 8)

- [ ] **SEM-01**: BERT inference via `sentence-transformers` `all-MiniLM-L6-v2`
- [ ] **SEM-02**: Model warm-up at process startup (cold-start latency mitigation)
- [ ] **SEM-03**: Cosine similarity matrix for word pairs
- [ ] **SEM-04**: t-SNE or UMAP projection to 2D for warm-start initialization
- [ ] **SEM-05**: Sinkhorn-Knopp Optimal Transport via POT 0.9.6.post1, computed in log-space
- [ ] **SEM-06**: Adaptive ε regularization for Sinkhorn-Knopp (avoid degenerate distributions)
- [ ] **SEM-07**: BERT embeddings persisted in pgvector with HNSW index
- [ ] **SEM-08**: Sinkhorn output replaces Force-Directed initialization in the Inner Loop

### Outer Loop-v1 (Phase 9)

- [ ] **OUTER-01**: pyribs MAP-Elites archive integration
- [ ] **OUTER-02**: Behavioral descriptors: shape fidelity, rotation, symmetry, semantics
- [ ] **OUTER-03**: Quality metrics: Layout Coverage (LC), Layout Uniformity (LU), Space-Saving (SS), Compactness, Aspect Ratio (target φ ≈ 1.618)
- [ ] **OUTER-04**: Semantic metrics: Realized Adjacencies (Cycle Cover), Distortion
- [ ] **OUTER-05**: Archive persistence in PostgreSQL via `INSERT ... ON CONFLICT (bin_id) DO UPDATE WHERE EXCLUDED.fitness > archive.fitness`
- [ ] **OUTER-06**: Archive saturation monitoring + novelty search component
- [ ] **OUTER-07**: Periodic re-evaluation of elites to prevent the elite-of-the-elite problem

### Self-Play (Phase 10)

- [ ] **SP-01**: Celery Beat scheduled nightly job in `queue='background'`
- [ ] **SP-02**: Monte-Carlo sampling from current archive
- [ ] **SP-03**: Mutation operators (parameter perturbation, crossover)
- [ ] **SP-04**: Evaluation against frozen baseline metrics
- [ ] **SP-05**: Archive update with stricter dominance check
- [ ] **SP-06**: Adversarial reviewer model penalizing reward hacking
- [ ] **SP-07**: Distribution-shift monitoring across consecutive nights
- [ ] **SP-08**: Replay log for every Self-Play run (for debugging and offline policy updates)

### Outer Loop-v2 (Phase 11)

- [ ] **OUTER2-01**: BOP-Elites via custom wrapper around pyribs `BayesianOptimizationEmitter` (EJIE)
- [ ] **OUTER2-02**: Sparse GP for scaling beyond 100 evaluations
- [ ] **OUTER2-03**: CQD score equation: `ω(x, G, θ) = f(x)/|f_max - f_min| - θ · δ(g(x), G)/δ_max`
- [ ] **OUTER2-04**: Monte-Carlo CQD computation: `CQD = (1/NM) · Σ_n Σ_m ω(x^r, G_n, θ_m)`
- [ ] **OUTER2-05**: Fixed seeds for CQD Monte-Carlo sampling (reproducibility)
- [ ] **OUTER2-06**: Theta-sweep smoothing
- [ ] **OUTER2-07**: Pareto-Front computation with hypervolume approximation
- [ ] **OUTER2-08**: `CQD_HV = Σ_G HV(S_HV(G))` aggregate metric
- [ ] **OUTER2-09**: Pareto-Slider API endpoint exposing design fidelity ↔ packing density tradeoff

### Production v1 (Phase 12)

- [ ] **PROD-01**: Seam Carving energy function: `E(x,y) = Σ wᵢ · Gauss(distance)`
- [ ] **PROD-02**: Optimal seam computation via Dynamic Programming O(w·h)
- [ ] **PROD-03**: Bezier export via `svgelements` (or direct `lxml.etree`) for SVG
- [ ] **PROD-04**: PDF export via `ReportLab` for sub-millimeter print precision
- [ ] **PROD-05**: PNG export via `Pillow` from rendered tensors
- [ ] **PROD-06**: Boolean union operation on Bezier paths to prevent double cuts in print
- [ ] **PROD-07**: FastAPI `POST /render` endpoint with Pydantic schema validation
- [ ] **PROD-08**: FastAPI returns `task_id`; SSE endpoint streams progress
- [ ] **PROD-09**: Celery worker (`--pool=prefork`, `--concurrency=1`, `--max-tasks-per-child=50`)
- [ ] **PROD-10**: Two queues: `realtime` (live API) and `background` (Self-Play)
- [ ] **PROD-11**: GPU resource isolation: dedicated worker pool per GPU
- [ ] **PROD-12**: Hard task timeout (per-render budget) to prevent cost runaway
- [ ] **PROD-13**: SVG color allow-list regex `^#[0-9a-fA-F]{3,8}$`
- [ ] **PROD-14**: Font name allow-list against registered fonts
- [ ] **PROD-15**: Path traversal prevention on mask uploads (Pydantic validation, no file-path inputs)
- [ ] **PROD-16**: Rate limiting on public API endpoints
- [ ] **PROD-17**: `/health` (public) and `/health/internal` (auth) endpoints
- [ ] **PROD-18**: OpenTelemetry tracing across FastAPI → Celery → GPU worker
- [ ] **PROD-19**: Prometheus metrics + NVIDIA DCGM Exporter for GPU
- [ ] **PROD-20**: Graceful shutdown on SIGTERM (drain in-flight tasks, exit clean)
- [ ] **PROD-21**: Golden-image regression tests for renderer output
- [ ] **PROD-22**: Load test: 100 concurrent renders, P99 measurement
- [ ] **PROD-23**: Release gate: all tests green, all metrics within budget, 3-AI peer review approved

## Out of Scope

| Feature | Reason |
|---------|--------|
| Force-Directed layouts | Blueprint Teil 2.2 explicitly replaces these with Sinkhorn-Knopp |
| Linear / sqrt frequency normalization | Mathematically wrong for Zipf-distributed data (Blueprint Teil 1.2) |
| Single-optimum solvers | Project's core thesis is Quality-Diversity, not single-optimum |
| `pickle` for model checkpoints | `safetensors` mandated for security |
| `loguru` + `structlog` hybrid | Codex-blocked: dual logging abstractions create operational noise |
| `svgwrite` library | Inactive since 2022, replaced by `svgelements` |
| Next.js 14 | Outdated — Next.js 16 is current April 2026 |
| Turborepo at v1 | Premature platform tooling — uv workspace + Cargo + pnpm sufficient |
| Cookie-based authentication | Not applicable to standalone engine API |
| External font URLs at runtime | Security and reproducibility risk — bundled fonts only |
| File-path mask input | Path traversal attack surface — Pydantic-validated base64 only |
| `ctx.measureText` for collision rectangles | Unreliable across canvas implementations |
| CJK tokenization | Deferred — separate font stack and segmentation strategy required |
| Rust in Inner Loop hot path | PyO3 ABI risk too high (Codex) — Rust restricted to WASM preview |

## Traceability

| Requirement Range | Phase |
|-------------------|-------|
| FOUND-01..12 | Phase 1 — Foundation |
| DATA-01..06 | Phase 2 — Datenmodell + Wiki |
| NLP-01..08 | Phase 3 — NLP-v1 |
| GEO-01..07 | Phase 4 — Geometry-v1 |
| REND-01..06 | Phase 5 — Renderer-v1 |
| INNER-01..10 | Phase 6 — Inner Loop-v1 |
| GEO2-01..09 | Phase 7 — Geometry-v2 |
| SEM-01..08 | Phase 8 — Semantic Vector Space |
| OUTER-01..07 | Phase 9 — Outer Loop-v1 |
| SP-01..08 | Phase 10 — Self-Play |
| OUTER2-01..09 | Phase 11 — Outer Loop-v2 |
| PROD-01..23 | Phase 12 — Production v1 |

**Coverage:**
- v1 requirements: 109 total
- Mapped to phases: 109
- Unmapped: 0

---
*Requirements defined: 2026-04-07 after research synthesis (Gemini + Codex consensus)*
