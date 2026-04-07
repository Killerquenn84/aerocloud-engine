---
title: Research Summary (Claude synthesis)
tags: [research, summary, synthesis, risks]
source: mirrored into wiki by reorganization
mirrored_on: 2026-04-07
slug: summary
created: 2026-04-07

---

# Research Summary — AeroCloud Engine

**Researched by:** Gemini CLI (4 dimensions) + Codex CLI (verification)
**Date:** 2026-04-07
**Confidence:** MEDIUM-HIGH (Codex caught and corrected several Gemini hallucinations)

## Executive Summary

AeroCloud Engine is a standalone, self-learning word cloud rendering engine implementing the full mathematical vision of the Blueprint: PyTorch CUDA differentiable rendering (Inner Loop), MAP-Elites + BOP-Elites + CQD Quality-Diversity (Outer Loop), BERT semantic vector space, Sinkhorn-Knopp Optimal Transport, Multi-Centric SDF/MAT geometry, Seam Carving + Bezier sub-millimeter export, and nightly Self-Play training. NO scope reduction in v1.

The polyglot stack is **Python 3.11 (engine core)** + **Rust (browser preview only)** + **TypeScript/Next.js 16 (frontend)**, deployed on Hostinger Cloud VPS with NVIDIA-Docker GPU instances on demand.

## Top 5 Stack Picks (Codex-verified)

1. **`nvdiffrast 0.3.3.1`** — differentiable rasterizer (with caveats: build/runtime fragility, NVIDIA Source Code License)
2. **`pyribs` (latest)** + custom BOP-Elites wrapper around `BayesianOptimizationEmitter` (EJIE)
3. **`POT 0.9.6.post1`** — Sinkhorn-Knopp Optimal Transport (CUDA-accelerated, log-space)
4. **`scipy 1.17.x` `distance_transform_edt`** — exact Meijster EDT for SDF
5. **`torch 2.7.1`** + CUDA 12.1 — pinned, NOT latest 2.10 (CUDA-drift mitigation)

## Top 5 Differentiating Features (per FEATURES.md)

1. **Quality-Diversity archive** — produces an archive of diverse layouts, not a single optimum (Blueprint Teil VIII)
2. **SDF + MAT skeleton-aware placement** — fills non-convex shapes correctly via Multi-Centric Wordle (Blueprint Teil III)
3. **Differentiable rendering with 4-part Loss** — gradient-driven word optimization (Blueprint Teil V)
4. **Sinkhorn-Knopp warm-start** — deterministic global initialization replacing Force-Directed (Blueprint Teil II)
5. **Sub-millimeter Bezier export** — print-quality vector output via Seam Carving + Boolean union (Blueprint Teil X)

## Critical Architecture Decisions

1. **Engine core in Python; Rust ONLY for WASM browser preview.** PyO3 ABI risk too high for hot loop (Codex).
2. **uv workspace + Cargo + pnpm** — Turborepo deferred until JS task orchestration genuinely hurts (Codex).
3. **Celery 5.6.2 minimal** — required for nightly Self-Play scheduling, but configured with strict separation: FastAPI async, Celery sync, GPU own pool.
4. **PostgreSQL 16 + pgvector HNSW** for MAP-Elites archive and BERT embeddings (HNSW recall >98% at low latency).
5. **`structlog` only — no `loguru` hybrid** (Codex blocked the dual-logger pattern).
6. **`safetensors` not `pickle`** for model checkpoints (security).
7. **Next.js 16** (not 14 — Codex caught the outdated version).

## Top 5 Pitfalls + Mitigations (per PITFALLS.md)

1. **Vanishing gradients in differentiable rendering** → nvdiffrast antialiasing + gradient clipping + heuristic init (Phases 5-6)
2. **CUDA OOM via autograd graph retention** → explicit `.detach()` for metrics, `torch.cuda.empty_cache()`, gradient checkpointing (Phases 5-6)
3. **MAP-Elites archive saturation** → well-chosen behavioral descriptors, novelty search components, periodic re-evaluation (Phase 9)
4. **Determinism loss across runs** → global `set_seed()`, `torch.use_deterministic_algorithms(True)`, `CUBLAS_WORKSPACE_CONFIG=:4096:8` (Phase 1)
5. **Self-Play feedback loops collapsing diversity** → adversarial reviewer model, out-of-bounds penalty, mix in real user data (Phase 10)

## Recommended Phase Order (12 phases, 3-AI consensus)

| # | Phase | Domain | Critical Risk Addressed |
|---|-------|--------|------------------------|
| 1 | Foundation | Tooling | Determinism (#11), VPS/NVIDIA-Docker (#10), reproducibility (#18) |
| 2 | Datenmodell + Wiki | Data | Pydantic schema validation foundation |
| 3 | NLP-v1 | NLP | TF-IDF-AP correctness, Zipf log-norm |
| 4 | Geometry-v1 | Geometry | Meijster EDT validation |
| 5 | Renderer-v1 | Renderer | nvdiffrast forward pass (#1, #2 monitoring) |
| 6 | Inner Loop-v1 | Optimizer | 4-part Loss + Adam stability (#1) |
| 7 | Geometry-v2 | Geometry | MAT pruning, Multi-Centric, 5-stage collision |
| 8 | Semantic Vector Space | NLP | BERT inference (#3), Sinkhorn underflow (#4) |
| 9 | Outer Loop-v1 | Optimizer | MAP-Elites archive saturation (#5) |
| 10 | Self-Play | Optimizer | Feedback loop collapse (#12) |
| 11 | Outer Loop-v2 | Optimizer | CQD normalization (#6), Pareto scaling (#13) |
| 12 | Production v1 | Export + API | Celery+GPU zombies (#7), async/sync (#8), Bezier precision (#15), security (#16), cost runaway (#17) |

## Cross-Cutting Risks

- **nvdiffrast version pinning** is essential — single biggest production risk
- **CUDA toolchain matrix** must be tested in CI on every torch update
- **GPU cold-start latency** on Hostinger requires warm-up routines on container start
- **Self-Play feedback loops** could collapse the archive — adversarial reviewer needed
- **Determinism flag** must be set globally from Phase 1 — retrofitting is painful

## Confidence Assessment

| Area | Confidence | Notes |
|------|-----------|-------|
| Stack picks | MEDIUM-HIGH | Codex verified versions; nvdiffrast is the residual risk |
| Architecture | HIGH | Standard patterns + Codex sanity check |
| Features (Blueprint mapping) | HIGH | Gemini's literature mapping is solid |
| Pitfalls | HIGH | Each pitfall traceable to source |
| BOP-Elites integration | MEDIUM | pyribs has the building block, but custom wrapper required |
| Self-Play implementation | LOW-MEDIUM | Bleeding-edge research, will need iterative refinement |

## Open Questions for Phase Planning

1. Does the Hostinger VPS provide a GPU type compatible with `nvdiffrast` build (Compute Capability ≥ 6.0)?
2. Is CJK (Chinese/Japanese/Korean) tokenization required for v1 or deferred?
3. What is the target P99 latency for the live API render endpoint (vs. nightly Self-Play training)?
4. Where does the BERT model load from in production (HuggingFace download vs. baked into Docker image)?

These questions will be addressed during phase planning (`/gsd-discuss-phase`).

---
*Synthesis: Claude Code (orchestrator) on 2026-04-07*
*Sources: Gemini CLI (research), Codex CLI (verification)*

## Siehe auch

- [research/stack.md](research/stack.md) — Stack Details
- [research/features.md](research/features.md) — Feature-Mapping
- [research/architecture.md](research/architecture.md) — Architektur-Details
- [research/pitfalls.md](research/pitfalls.md) — Risiken
- [decisions/2026-04-07-polyglot-stack-selection.md](decisions/2026-04-07-polyglot-stack-selection.md) — Finale Entscheidungen
- [knowledge/roadmap-v1.md](knowledge/roadmap-v1.md) — 12-Phasen Roadmap
