# AeroCloud Engine

## What This Is

A self-learning word cloud rendering engine that places words precisely within arbitrary silhouettes using semantic hierarchy and geometric optimization. Built as a standalone Node.js/TypeScript module that powers the AeroCloud Shopify app's rendering pipeline.

## Core Value

Precise silhouette filling with semantic word hierarchy — words are placed inside any shape with correct visual weight (Zipf-normalized sizing) and zero overlap, producing aesthetically high-quality word clouds.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] NLP pipeline with TF-IDF-AP scoring, Zipf-normalization, and positional weighting
- [ ] SDF (Signed Distance Field) generation from silhouette images
- [ ] Medial Axis Transform for shape skeleton analysis
- [ ] Multi-stage collision detection (AABB, Quadtree, Bitmap)
- [ ] Heuristic word packing using spiral search + SDF-gradient descent
- [ ] Force-directed layout refinement with analytical gradients
- [ ] Canvas-based rendering pipeline (Node.js canvas)
- [ ] SVG/PNG export with high-quality vector output
- [ ] Fastify v5 HTTP API for rendering requests
- [ ] Coarse-to-fine resolution strategy for performance

### Out of Scope

- PyTorch/CUDA differentiable rendering — requires Python runtime, deferred to v2
- BERT embeddings / sentence-transformers — heavy ML dependency, v2
- MAP-Elites / Quality-Diversity outer loop — needs thousands of evaluations, v2
- CQD metrics and Pareto-front slider — depends on MAP-Elites, v2
- Rust/WASM browser preview — separate compilation target, v2
- Seam Carving whitespace compression — optimization extra, v2
- Bezier curve SVG export — standard SVG sufficient for v1
- Optimal Transport (Sinkhorn-Knopp) — BERT dependency, v2
- Self-Play nightly training — requires QD infrastructure, v2
- Three.js/WebGL animation — frontend concern, v2

## Context

- Part of the AeroCloud Shopify app ecosystem (parent: `/var/www/wordcloud-app-v2`)
- Blueprint in `raw/sources/AeroCloud-Blueprint.md` describes the full vision (10 parts)
- Current codebase has wiki/knowledge base system (Karpathy LLM Wiki pattern) but no engine implementation yet — all `src/` modules are stubs
- Existing dependencies: `natural` (NLP), `compromise` (linguistics), `marked` (markdown)
- Missing dependencies: `node-canvas` or `skia-canvas`, `fastify`, spatial indexing libraries
- The blueprint's Inner Loop (PyTorch differentiable rendering) is replaced in v1 by SDF-gradient descent + force-directed layout — geometrically equivalent, Node.js native
- 3-AI team workflow: Claude Code (orchestrator), Gemini (researcher), Codex (reviewer)

## Constraints

- **Runtime**: Node.js 22 LTS, TypeScript 5.7+ ESM only — no Python, no Rust, no WASM
- **Framework**: Fastify v5 — no Express, no Hapi
- **Testing**: Vitest + StrykerJS — TDD/BDD mandatory per CLAUDE.md
- **Process**: PM2 as process manager on production server
- **Performance**: < 500ms for 200 words target rendering time
- **Security**: SVG sanitization required, no SSRF, path traversal protection
- **Integration**: Must expose HTTP API consumable by parent Shopify app's BullMQ workers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Node.js geometric engine over PyTorch | Blueprint requires Python/CUDA not in stack; geometric algorithms achieve similar quality for v1 | -- Pending |
| SDF-gradient descent as Inner Loop replacement | SDF gradient is a simple vector lookup, no autograd needed; Gemini confirmed viability | -- Pending |
| Force-directed layout over differentiable rendering | d3-force-style physics simulation is proven, performant in JS, visually similar results | -- Pending |
| Spiral + Quadtree packing over MAP-Elites | Single high-quality result sufficient for v1; QD exploration deferred to v2 | -- Pending |
| Fastify v5 over Express | CLAUDE.md mandates Fastify; better performance, schema validation built-in | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-06 after initialization*
