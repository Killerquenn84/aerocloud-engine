# Roadmap: AeroCloud Engine v1

**Created:** 2026-04-07
**Granularity:** Fine (12 phases)
**Strategy:** Bottom-up build order (Geometry → NLP → Inner Loop → Outer Loop → Export). Iterative reification per domain (v1 → v2) within v1 milestone. 3-AI consensus (Claude + Gemini + Codex).

## Milestone

**v1: Full Blueprint Realization** — All 11 Blueprint sections implemented and integrated. Production-deployable on Hostinger Cloud with NVIDIA-Docker GPU instances.

## Phase Exit Gate (applies to all 12 phases)

Each phase ends ONLY when ALL of:

1. ✅ All `pytest` + `hypothesis` tests green
2. ✅ `mypy --strict` clean
3. ✅ `ruff check` and `ruff format --check` clean
4. ✅ Wiki updated with phase findings (`wiki/` reflects new modules)
5. ✅ Stable interfaces (no breaking changes downstream)
6. ✅ Benchmark vs prior phase (no regression in determinism or quality)
7. ✅ 3-AI peer review approved (Claude implements, Codex reviews, Gemini checks against research)

## Phase 1: Foundation

**Goal:** Reproducible runtime, monorepo skeleton, CI green, GPU smoke test passing.

**Requirements covered:** FOUND-01 to FOUND-12 (12)

**Plans:**
- Setup uv workspace + Cargo workspace + pnpm workspace
- Multi-stage Dockerfile with `nvidia/cuda:12.x-base-ubuntu22.04` (SHA-pinned)
- CI pipeline (mypy, ruff, pytest, hypothesis)
- Global `set_seed()` function with cuBLAS deterministic config
- PostgreSQL 16 + pgvector + Redis 7 via `docker compose`
- structlog + OpenTelemetry initialization
- Pydantic-Settings v2 config loader
- GPU smoke test script
- Bundled fonts in `assets/fonts/`

**Success criteria:**
1. `docker compose up` brings up Postgres+pgvector+Redis without errors
2. `pytest` runs green on a fresh container
3. `set_seed(42)` produces identical numpy + torch outputs across runs
4. CI green for `mypy --strict` + `ruff` + `pytest` on PR
5. GPU smoke test reports CUDA capability ≥ 6.0 (or skips gracefully on CPU-only host)

**Risk addressed:** Determinism (#11), VPS/NVIDIA-Docker (#10), reproducibility (#18)

## Phase 2: Datenmodell + Wiki

**Goal:** Pydantic data model for the entire pipeline + wiki tooling integrated as living reference.

**Requirements covered:** DATA-01 to DATA-06 (6)

**Plans:**
- Pydantic v2 models: Token, Shape, WordCandidate, PlacedWord, LayoutScore, MapElitesEntry, RenderRequest, RenderResult
- Reproducibility ID schema `(input_hash, seed, version) → output_hash`
- Alembic baseline migration: `archive_v1` table with HNSW index on descriptor vector
- Wiki tooling integration: `wiki:ingest`, `wiki:query`, `wiki:lint` callable from CI
- `safetensors` enforcement (CI lint rule blocks `pickle.dump/load`)

**Success criteria:**
1. Round-trip serialization tests pass for all Pydantic models
2. Alembic upgrade + downgrade works on fresh Postgres
3. HNSW index exists with tuned `m` and `ef_construction`
4. `wiki:lint` reports zero broken refs in `wiki/`
5. CI lint rule rejects any `pickle` import in source files

**Risk addressed:** Schema validation foundation, security baseline (safetensors)

## Phase 3: NLP-v1

**Goal:** Raw text input → scored, Zipf-normalized, multilingual word list.

**Requirements covered:** NLP-01 to NLP-08 (8)

**Plans:**
- spaCy 3.x model loading (`de_dep_news_trf`, `en_core_web_trf`)
- Language auto-detection
- Stopword removal per language
- TF-IDF-AP scoring with positional weighting
- Zipf log-normalization with frozen `reference_weights` tensor
- Stem-for-counting / surface-form-for-display data structure
- Corpus-size guard with linear fallback
- Lemmatization fixture validation (DE + EN)

**Success criteria:**
1. English fixture text yields correct stopword removal
2. German "Jahresurlaub" stays unsplit (compound limitation documented)
3. Zipf font sizes are log-distributed (NOT linear, NOT sqrt — verified mathematically)
4. Display surface forms preserved while stems used for counting
5. Corpus < 20 unique tokens triggers linear fallback (no NaN/division-by-zero)

**Risk addressed:** TF-IDF-AP correctness, Zipf math, multilingual handling

## Phase 4: Geometry-v1

**Goal:** Silhouette mask → exact signed float32 SDF (positive=inside) + bytes-bounded cache with blake3 composite key + vectorized integer AABB collision + per-word adaptive POI spiral placement with structured DropReason contract + pixel-scanned glyph AABBs with cross-platform golden-corpus firewall.

**Requirements covered:** GEO-01 to GEO-07 (7)

**Plans:** 7 plans in 6 waves ✅ ALL COMPLETE 2026-04-09
- [x] 04-01-scaffolding-PLAN.md — ADRs (0004/0005/0006), errors.py, deps, config, test subtree [Wave 0]
- [x] 04-02-mask-sdf-PLAN.md — mask.py + sdf.py + _assert_freetype + property tests [Wave 1]
- [x] 04-03-sdf-cache-PLAN.md — bytes-bounded LRU + blake3 composite key + RLock + 16-thread test [Wave 2 parallel]
- [x] 04-04-glyph-golden-PLAN.md — font.getmask + Pydantic AABB/GlyphBBox + 480 golden .npy fixtures [Wave 2 parallel]
- [x] 04-05-collision-placement-PLAN.md — vectorized int AABB + per-word adaptive POI + integer Archimedean (MAX_STEP=16) + DropReason enum [Wave 3]
- [x] 04-06-observability-gates-PLAN.md — debug dump + structlog+OTel + Nyquist dims 6/7/8 + 11 wiki files [Wave 4]
- [x] 04-07-3ki-review-PLAN.md — Claude self + Codex + Gemini review, Jens-ratified consensus, 2 Gemini bonus fixes applied [Wave 5]

**Phase 4 Status:** ✅ COMPLETE 2026-04-09
- 595/595 tests green (mypy strict clean, ruff clean)
- 3-KI review: Claude APPROVED-WITH-NOTES, Codex BLOCKED + Gemini BLOCKED (both overridden by Jens with documented rationale)
- 2 accepted deviations: (A) place_words perf 24.85s vs retired 5.0s gate → 60s VPS ceiling + Phase 12 re-validate, (B) FreeType 2.13.2 → 2.14.3 ADR-0006 update + bypass removed
- 2 Gemini bonus fixes applied inline: del edt_in before gc.collect (sdf.py), float32 promotion audit (placement.py)
- Known limits carried forward: `wiki/knowledge/phase-4-known-limits.md`

**Success criteria:**
1. Circle mask: SDF center value equals radius ± 1px
2. SDF cache hit observable in metrics
3. AABB collision detects pixel-perfect overlaps on test fixtures
4. Centroid spiral places 100 words on circle without collision
5. Pixel-scan AABB matches actual ink bounds (not font metric estimate)

**Risk addressed:** Meijster EDT correctness, measureText avoidance

## Phase 5: Renderer-v1

**Goal:** Pure PyTorch differentiable 2D sprite compositor with learnable tensors, grid_sample forward pass, and alpha-over compositing (D-01 supersedes nvdiffrast).

**Requirements covered:** REND-01 to REND-06 (6)

**Plans:** 4 plans in 4 waves ✅ ALL COMPLETE 2026-04-14

Plans:
- [x] 05-01-PLAN.md — Scaffolding: psutil dep, renderer package, sprite cache + font registry + unit tests [Wave 1]
- [x] 05-02-PLAN.md — DifferentiableRenderer nn.Module: affine_grid + grid_sample forward pass + alpha-over + unit tests [Wave 2]
- [x] 05-03-PLAN.md — Test pyramid: hypothesis property, Phase 4 integration, determinism, RSS stability, font leak [Wave 3]
- [x] 05-04-3ki-review-PLAN.md — 3-KI Review (Claude + Codex + Gemini) + Wiki Update + 6 post-review fixes [Wave 4]

**Phase 5 Status:** ✅ COMPLETE 2026-04-14
- 48/48 tests green (mypy strict clean, ruff clean)
- 3-KI review: Claude APPROVED, Codex APPROVED (after 6 fixes), Gemini APPROVED (after affine inversion fix)
- D-01 supersession: nvdiffrast replaced by pure PyTorch grid_sample (zero external deps, CPU fallback)
- Post-review fixes: affine target-to-source, NDC (2p+1)/size-1, softplus scale clamp, TOCTOU, device cache key, accessor functions

**Success criteria:**
1. Forward pass on 8px canvas produces non-NaN tensor
2. `backward()` on toy loss does not raise
3. Font Set has exactly N entries after first render and stays at N after 100 renders
4. RSS stable across 100 consecutive renders (no font leak)
5. Gradient flows from output back to position tensor

**Risk addressed:** Vanishing gradients (#1), CUDA OOM (#2), font memory leaks

## Phase 6: Inner Loop-v1

**Goal:** Differentiable optimization with 4-part Loss + Adam + Coarse-to-Fine.

**Requirements covered:** INNER-01 to INNER-10 (10)

**Plans:** 4 plans in 4 waves

Plans:
- [x] 06-01-PLAN.md — Scaffolding + Pydantic models + 4 loss functions + convergence detection + unit tests [Wave 1]
- [x] 06-02-PLAN.md — InnerLoop class + Coarse-to-Fine pipeline + Adam optimizer + integration tests [Wave 2]
- [x] 06-03-PLAN.md — Test pyramid: hypothesis property + determinism + RSS memory stability [Wave 3]
- [x] 06-04-PLAN.md — 3-KI Review (Claude + Codex + Gemini) + Wiki Update + phase exit gates [Wave 4]

**Success criteria:**
1. Loss converges from random init within 100 epochs at 8px
2. Coarse-to-Fine produces ≥ 10x speedup vs single-resolution baseline
3. No NaN losses across 1000 random seeds (hypothesis property test)
4. RSS does not grow across 100 inner-loop runs
5. Loss curves identical for same seed (determinism verified)

**Risk addressed:** Loss instability (#1), CUDA OOM (#2)

## Phase 7: Geometry-v2

**Goal:** Full geometric machinery: MAT, Multi-Centric, full 5-stage collision, Bezier paths.

**Requirements covered:** GEO2-01 to GEO2-09 (9)

**Plans:** 7/7 plans complete

Plans:
- [x] 07-01-PLAN.md — MAT skeleton extraction + pruning + mat_cache (TDD) [Wave 1] — GEO2-01, GEO2-02
- [x] 07-02-PLAN.md — BVH + Quadtree + BVH LRU cache (TDD) [Wave 2 parallel] — GEO2-04, GEO2-05, GEO2-08
- [x] 07-03-PLAN.md — SAT + Bitmap collision stages (TDD) [Wave 3] — GEO2-06, GEO2-07
- [x] 07-04-PLAN.md — Multi-Centric placement pre-pass (TDD) [Wave 4] — GEO2-03
- [x] 07-05-PLAN.md — BezierGlyph + glyph_to_bezier via cv2 (TDD) [Wave 2 parallel] — GEO2-09
- [x] 07-06-PLAN.md — Renderer dual-mode + delete compute_additive_density (TDD) [Wave 5] — D-20/D-21
- [x] 07-07-PLAN.md — 3-KI Review + Wiki Update + Phase Exit Gate [Wave 6]

**Success criteria:**
1. Star mask produces > 1 MAT branch (multi-centric verified)
2. Crescent mask produces > 1 MAT branch
3. Rotated text on convex shape: SAT detects collision that AABB misses
4. Bitmap collision is pixel-exact on adversarial fixtures
5. Multi-centric placement fills concave shapes that single-centric leaves empty

**Risk addressed:** MAT pruning instability (#5), spiral deadlock on concave shapes

## Phase 8: Semantic Vector Space

**Goal:** BERT embeddings + Sinkhorn-Knopp Optimal Transport warm-start.

**Requirements covered:** SEM-01 to SEM-08 (8)

**Plans:** 6 plans in 5 waves

Plans:
- [x] 08-01-PLAN.md — Scaffolding + BERT embeddings + Pydantic models + config + test infra (TDD) [Wave 1] — SEM-01, SEM-02
- [x] 08-02-PLAN.md — Cosine similarity matrix + UMAP/t-SNE 2D projection (TDD) [Wave 2] — SEM-03, SEM-04
- [x] 08-03-PLAN.md — Sinkhorn-Knopp transport + adaptive epsilon + hypothesis tests (TDD) [Wave 3] — SEM-05, SEM-06
- [x] 08-04-PLAN.md — semantic_warm_start glue function + integration/determinism tests (TDD) [Wave 4] — SEM-08
- [x] 08-05-PLAN.md — Alembic migration word_embeddings + pgvector persistence (TDD) [Wave 2 parallel] — SEM-07
- [x] 08-06-PLAN.md — 3-KI Review + Wiki Update + Phase Exit Gate [Wave 5]

**Success criteria:**
1. BERT model loads in < 10s on first call (warmed cache thereafter)
2. Sinkhorn-Knopp converges on degenerate distributions without NaN
3. t-SNE/UMAP produces deterministic 2D coordinates with fixed seed
4. pgvector HNSW recall ≥ 98% on test query set
5. Inner Loop with Sinkhorn warm-start converges faster than random init

**Risk addressed:** BERT inference drift (#3), Sinkhorn underflow (#4)

## Phase 9: Outer Loop-v1

**Goal:** MAP-Elites archive with quality metrics, novelty search, archive persistence.

**Requirements covered:** OUTER-01 to OUTER-07 (7)

**Plans:** 6 plans in 5 waves

Plans:
- [x] 09-01-PLAN.md — Scaffolding + pyribs GridArchive wrapper + GaussianEmitter + behavioral descriptors (TDD) [Wave 1] — OUTER-01, OUTER-02
- [x] 09-02-PLAN.md — Quality metrics: LC, LU, SS, Compactness, Aspect Ratio + semantic metrics (TDD) [Wave 2] — OUTER-03, OUTER-04
- [x] 09-03-PLAN.md — Alembic migration 0003 + asyncpg archive persistence with upsert (TDD) [Wave 2 parallel] — OUTER-05
- [x] 09-04-PLAN.md — Novelty search emitter + saturation monitor + elite re-evaluation (TDD) [Wave 3] — OUTER-06, OUTER-07
- [x] 09-05-PLAN.md — OuterLoop orchestrator: full MAP-Elites evaluation loop + determinism + hypothesis tests [Wave 4] — OUTER-01..07
- [x] 09-06-PLAN.md — 3-KI Review + Wiki Update + Phase Exit Gate [Wave 5]

**Success criteria:**
1. After 1000 evaluations, archive coverage > 30% of behavior grid
2. Race condition test: concurrent inserts to same bin keep best fitness
3. Novelty search prevents premature single-corner saturation
4. Re-evaluation detects elite drift > threshold
5. Archive can be exported and re-imported deterministically

**Risk addressed:** Archive saturation (#5)

## Phase 10: Self-Play

**Goal:** Nightly Self-Play training with adversarial reviewer and replay logging.

**Requirements covered:** SP-01 to SP-08 (8)

**Plans:** 5 plans in 5 waves

Plans:
- [ ] 10-01-PLAN.md — Scaffolding: Celery app + Beat schedule + SelfPlayConfig + models + Alembic migration 0004 + ReplayLogger (TDD) [Wave 1] — SP-01, SP-08
- [ ] 10-02-PLAN.md — Mutation operators (Gaussian + crossover) + Adversarial reviewer (TDD) [Wave 2] — SP-02, SP-03, SP-06
- [ ] 10-03-PLAN.md — SelfPlayLoop orchestrator + KL monitoring + Celery task wiring (TDD) [Wave 3] — SP-04, SP-05, SP-07
- [ ] 10-04-PLAN.md — Integration tests + determinism tests + hypothesis property tests [Wave 4] — SP-01..08
- [ ] 10-05-PLAN.md — 3-KI Review + Wiki Update + Phase Exit Gate [Wave 5]

**Success criteria:**
1. Nightly job runs for 8 hours then exits cleanly
2. Adversarial reviewer rejects > 5% of mutations as reward-hacking
3. Diversity metric does not collapse over 7 consecutive nights
4. Replay log fully reconstructs each Self-Play run
5. Distribution shift alert fires if descriptor distribution drifts > threshold

**Risk addressed:** Self-Play feedback collapse (#12)

## Phase 11: Outer Loop-v2

**Goal:** BOP-Elites + CQD metric + Pareto-Front + Pareto-Slider.

**Requirements covered:** OUTER2-01 to OUTER2-09 (9)

**Plans:**
- Custom BOP-Elites wrapper around pyribs `BayesianOptimizationEmitter` (EJIE)
- Sparse GP for scaling
- CQD score equation implementation
- Monte-Carlo CQD computation with fixed seeds
- Theta-sweep smoothing
- Pareto-Front computation with hypervolume approximation
- `CQD_HV = Σ_G HV(S_HV(G))`
- Pareto-Slider API endpoint

**Success criteria:**
1. BOP-Elites at 700 evaluations matches MAP-Elites at 90 000 evaluations on test problem (Blueprint claim verified)
2. CQD scores reproducible across runs with fixed seed
3. Pareto-Front smooth (no dominance ties)
4. Pareto-Slider returns layouts at slider positions 0.0, 0.25, 0.5, 0.75, 1.0
5. Hypervolume metric monotonically non-decreasing across nights

**Risk addressed:** CQD normalization (#6), Pareto scaling (#13)

## Phase 12: Production v1

**Goal:** Full FastAPI + Celery + Redis + pgvector deployment with Seam Carving + Bezier export, security hardening, performance budget validated.

**Requirements covered:** PROD-01 to PROD-23 (23)

**Plans:**
- Seam Carving energy function + DP optimal seam
- `svgelements` SVG export
- ReportLab PDF export with sub-millimeter precision
- `Pillow` PNG export from rendered tensors
- Boolean union on Bezier paths
- FastAPI `POST /render` with Pydantic validation
- SSE progress endpoint
- Celery worker config (`prefork`, `concurrency=1`, `max-tasks-per-child=50`)
- Two queues: `realtime` + `background`
- GPU resource isolation
- Hard task timeouts
- SVG color + font allow-lists
- Path traversal prevention
- Rate limiting
- `/health` + `/health/internal`
- OpenTelemetry tracing
- Prometheus + DCGM Exporter
- Graceful shutdown
- Golden-image regression tests
- Load test (100 concurrent renders)
- Release gate

**Success criteria:**
1. P99 render latency within agreed budget for 200 words
2. SVG XSS injection attempt returns HTTP 400
3. 100 concurrent renders complete without GPU OOM
4. SIGTERM drains in-flight tasks before exit
5. Golden-image tests pass for circle, square, star, crescent fixtures
6. Memory stable under load test (no leaks)
7. Cost monitor alerts within budget
8. All other phase exit gates passed

**Risk addressed:** Celery+GPU zombies (#7), async/sync mixing (#8), Bezier precision (#15), security (#16), cost runaway (#17)

## Coverage Summary

| Phase | Requirements | Domain |
|-------|--------------|--------|
| 1 | 12 | Foundation |
| 2 | 6 | Data + Wiki |
| 3 | 8 | NLP-v1 |
| 4 | 7 | Geometry-v1 |
| 5 | 6 | Renderer-v1 |
| 6 | 10 | Inner Loop-v1 |
| 7 | 9 | Geometry-v2 |
| 8 | 8 | Semantic Vector |
| 9 | 7 | Outer Loop-v1 |
| 10 | 8 | Self-Play |
| 11 | 9 | Outer Loop-v2 |
| 12 | 23 | Production v1 |
| **Total** | **109** | **All Blueprint sections** |

**Coverage:** 109/109 v1 requirements mapped. 0 unmapped. ✓

## Parallelization Hints

Phases that can run in parallel (independent data dependencies):
- **Phase 3 (NLP-v1) ∥ Phase 4 (Geometry-v1)** — both depend only on Phase 2 data model
- **Phase 7 (Geometry-v2) ∥ Phase 8 (Semantic Vector Space)** — independent extensions of v1 modules

All other phases are strictly sequential due to hard data dependencies.

## Critical Path

```
1 → 2 → (3 ∥ 4) → 5 → 6 → (7 ∥ 8) → 9 → 10 → 11 → 12
```

---
*Roadmap created: 2026-04-07 after research synthesis (Gemini + Codex consensus)*
*Granularity: Fine (12 phases as decided by Jens)*
*Strategy: Bottom-up build order + iterative reification*
*Phase 7 plans added: 2026-04-15*
*Phase 8 plans added: 2026-04-16*
*Phase 9 plans added: 2026-04-18*
*Phase 10 plans added: 2026-04-21*
