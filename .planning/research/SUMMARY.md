# Project Research Summary

**Project:** AeroCloud Engine — Word Cloud Rendering Engine
**Domain:** Server-side geometric rendering pipeline (Node.js, TypeScript, Canvas API)
**Researched:** 2026-04-06
**Confidence:** MEDIUM-HIGH

## Executive Summary

AeroCloud Engine is a server-side word cloud rendering engine that places words precisely within arbitrary silhouettes using semantic hierarchy and geometric optimization. Unlike browser-first tools (d3-cloud, wordcloud2.js) or SaaS platforms (WordArt.com), the engine is an HTTP API service consumed exclusively by a BullMQ worker in the parent Shopify app — making throughput, output quality, and silhouette fidelity the primary success criteria rather than real-time interactivity. The engine must deliver sub-500ms renders for 200 words, guarantee zero word overlap, and fill silhouette shapes to the pixel boundary without dropping words — none of which any existing open-source Node.js library provides.

The recommended build approach is a 7-stage sequential rendering pipeline: InputValidator → NLP Processor (TF-IDF-AP) → ShapeAnalyzer (SDF + MAT) → Packer (spiral + bitmap collision) → LayoutRefiner (SDF gradient descent) → Renderer (@napi-rs/canvas) → Exporter (PNG/SVG). The blueprint's PyTorch Inner Loop is replaced in v1 with geometrically equivalent Node.js-native algorithms (SDF gradient descent + d3-force), which avoids a Python runtime dependency while delivering comparable placement quality. All stages are pure functions, making each independently testable and the pipeline easy to validate stage by stage.

The highest risks are in the geometry subsystem: the Signed Distance Field implementation choice determines overall placement quality (Meijster EDT is mandatory — approximations cause boundary moat artifacts), spiral search can deadlock on concave silhouettes without a hard iteration cap, and rotated-text collision requires operating on rotated pixel sprites rather than axis-aligned bounding boxes. Memory management in the long-running PM2 process is the second class of production risk — fonts must be registered once at startup, never per-request, and the @napi-rs/canvas async export path must be validated for memory leaks before production load.

## Key Findings

### Recommended Stack

The stack avoids native compilation complexity in favor of pre-built binary libraries. `@napi-rs/canvas` (0.1.97, Skia-backed, 500K weekly downloads) is the correct canvas choice over `node-canvas` (Cairo system-lib dependency causes Ubuntu 24.04 deployment friction) and `skia-canvas` (50K downloads, slower maintenance). `sharp` (0.34.5, libvips) preprocesses silhouette images 20x faster than jimp, which is non-negotiable at the 500ms render budget. Spatial indexing uses two complementary libraries: `rbush` (3.0.1) for the dynamic collision index during word placement, and `flatbush` (4.4.1) for the static SDF lookup index — the combination is significantly faster than a single quadtree. The SDF implementation is a hand-rolled Meijster EDT (100–150 lines TypeScript) as no production-grade JS SDF library exists for silhouette shapes.

**Core technologies (top 5):**
- `@napi-rs/canvas` 0.1.97 — 2D canvas rendering, pixel buffer access for SDF — pre-built Skia binaries, zero system deps, production-grade at 500K downloads/week
- `sharp` 0.34.5 — silhouette mask preprocessing to binary buffer — 20x faster than jimp, mandatory at 500ms budget
- `rbush` 3.0.1 + `flatbush` 4.4.1 — dynamic + static spatial indexing — R-tree outperforms quadtrees for densely packed rectangles; Mourner (Mapbox) authorship
- `natural` 8.1.1 + `stopword` — TF-IDF-AP scoring, German stemmer, multilingual stopword removal — only production-ready Node.js NLP with German support
- `d3-force` 3.x — force-directed layout refinement post-placement — proven physics simulation, runs in Node.js without DOM, adequate for < 300 nodes

**Critical version requirements:**
- Node.js 22 LTS (all libraries verified compatible)
- Fastify 5.8.x (CLAUDE.md mandate; 3x faster than Express)
- `@napi-rs/canvas` pre-1.0 — monitor for breaking changes on minor version bumps

### Expected Features

The engine's table stakes are non-negotiable for a Shopify merchant marketing tool: silhouette mask support (the primary reason the engine exists), collision-free word placement, Zipf-normalized font sizing, PNG and SVG export, and seed-based reproducibility (merchants must regenerate the same product image). The differentiating features that separate AeroCloud from every comparable open-source tool are: zero dropped words (d3-cloud drops words explicitly; AeroCloud shrinks to fit), Medial Axis Transform skeleton-aware placement, SDF-gradient descent for boundary-precise fills, and a coarse-to-fine pipeline that achieves the sub-500ms target.

**Must have (table stakes):**
- Silhouette/mask support with SDF-precise boundary fill — the product's reason to exist
- Collision-free placement with zero overlap guarantee — broken product without it
- Frequency-based Zipf-normalized font sizing (log normalization, not sqrt) — visual correctness
- Stopword removal with multilingual support (EN + DE minimum) — Shopify merchants are global
- PNG and SVG export — both required for social media, print, and merchandise
- Seed-based reproducibility — prevents merchant support tickets from day one
- Configurable canvas dimensions and color schemes — expected by every user

**Should have (competitive differentiators):**
- Zero dropped words — shrink-to-fit instead of d3-cloud's explicit word dropping
- Medial Axis Transform skeleton placement — fills limbs of complex shapes (horse, letters)
- TF-IDF-AP positional weighting — 12.9% semantic precision improvement over raw frequency
- Force-directed layout refinement — higher packing density than spiral-only placement
- Coarse-to-fine rendering pipeline — required to hit sub-500ms for 200 words
- Multi-centric spiral origins (one per MAT branch) — fills non-convex shapes correctly

**Defer (v2+):**
- BERT semantic color clustering — heavy ML dependency (Python/sentence-transformers)
- MAP-Elites / Quality-Diversity outer loop — requires thousands of evaluations
- CQD Pareto slider — depends on MAP-Elites archive
- CJK multi-language support (Japanese, Chinese, Korean) — separate font stack + segmentation investment
- Seam Carving whitespace compression, Bezier SVG paths, Three.js animation

**Explicit anti-features (do not build):**
- Arbitrary rotation angles — hard-cap to 0 or 0+90 degrees only (research confirms 45-degree words degrade readability)
- Noise-word padding to improve density — degrades semantic meaning
- File-path-based mask input — path traversal attack surface; base64/binary upload only

### Architecture Approach

The engine is a pure HTTP function: `POST /render` receives a JSON payload and returns an image buffer. It does NOT run an internal queue — the parent Shopify app's BullMQ manages the job lifecycle; adding a second queue inside the engine creates dual failure modes and monitoring complexity with no benefit. Each of the 7 pipeline stages is implemented as a pure function with explicit data pass-through; the only shared state is a module-level LRU-bounded SDF cache (50 entries, keyed by `sha256(shapeBuffer)`) that prevents ~150ms re-computation on repeated renders of the same shape.

**Major components:**
1. `src/api/` (ADD) — Fastify v5 app factory, `/render` route, `/health`, `/health/internal`; Ajv schema validation at the route level eliminates entire classes of validation bugs before the pipeline runs
2. `src/pipeline/` (ADD) — `renderPipeline()` orchestrator; threads data through stages, maps errors to HTTP status codes; the only place that knows the full stage sequence
3. `src/nlp/` — TF-IDF-AP scorer, Zipf normalizer, positional weighter, language detection (`franc`) + per-language stopword lists; stem-for-counting, surface-form-for-display
4. `src/geometry/` — Meijster EDT for SDF, MAT for skeleton regions, `rbush` dynamic collision board, `flatbush` static SDF lookup; SDF cached here
5. `src/optimizer/` — two files: `packer.ts` (spiral search + bitmap collision, multi-centric origins) and `refiner.ts` (SDF gradient descent force loop with convergence exit)
6. `src/renderer/` + `src/export/` — @napi-rs/canvas draw loop with integer-snapped positions; PNG/SVG export

**Pattern to follow:** Phases 2 (NLP) and 3 (Geometry) can be built in parallel — they are independent and converge at Phase 4 (Packer). All other phases are strictly sequential due to data dependencies.

### Critical Pitfalls

1. **measureText bounding box inaccuracy (node-canvas C-1)** — `ctx.measureText()` underreports glyph ink bounds, causing real visual overlaps that bypass collision checks. Prevention: pixel-scan each word glyph on a scratch canvas to find actual ink bounding box; use that for all collision rectangles. Applies even with @napi-rs/canvas (same API surface). Address before any collision logic is written.

2. **Spiral search deadlock on concave silhouettes (C-2)** — Archimedean spiral assumes convexity; a concave mask (star, crescent, skull) can exhaust all spiral candidates without placing a word, hanging the BullMQ job indefinitely. Prevention: hard cap `MAX_SPIRAL_STEPS = 10_000`; use MAT-derived multi-centric origins so each MAT branch gets its own spiral origin; wrap entire placement loop in `Promise.race([place(), timeout(450)])`.

3. **SDF gradient instability at shape boundary (C-5)** — Discrete EDT has a 1–2px discontinuous zero-crossing band where gradient vectors oscillate, causing force refinement to fail to converge and words to hover 1–3px from the silhouette edge. Prevention: use Meijster/Felzenszwalb exact EDT (not raster-scan approximation); add 1px SDF erosion to push the instability band outside the placement zone; clamp gradient forces to zero when `|SDF(x)| < 2.0`.

4. **Canvas memory leak in long-running PM2 workers (C-4)** — Font registration inside the per-request render loop causes unbounded RSS growth (confirmed node-canvas bug #1974). Prevention: register all fonts once at worker startup via a module-level `Set<string>`; never call `registerFont()` in the render loop. Add RSS monitoring to `/health/internal` with alert threshold at 500MB.

5. **SVG export XSS via user-supplied colors and font names (Mi-3)** — Unvalidated `colors[]` or `fontFamily` values written into SVG attribute slots enable event handler injection and SSRF. Two 2024 DOMPurify CVEs (CVE-2024-45801, CVE-2024-47875) show namespace-based bypasses. Prevention: validate colors against `^#[0-9a-fA-F]{3,8}$` regex; validate fontFamily against an allow-list of registered font names; use pre-escaped SVG template slots, not string concatenation.

## Implications for Roadmap

Based on combined research, 7 phases are recommended. Phases 2 and 3 can run in parallel; all others must be sequential due to hard data dependencies.

### Phase 1: Foundation — API Skeleton and Pipeline Shell
**Rationale:** BullMQ worker in parent app needs HTTP contact with the engine from day one. Fastify app factory, `/health` endpoint, and a `/render` stub that returns 200 establish the integration contract without requiring any rendering logic. This also sets up the Vitest test harness and CI pipeline.
**Delivers:** Engine process starts; parent app's BullMQ worker can reach `http://localhost:3001/render`; TDD infrastructure in place
**Addresses:** API-first design (table stakes from FEATURES.md); DoS input limits in Fastify schema (Pitfall Mi-5); path traversal security (Pitfall Mi-4)
**Avoids:** Pitfall Mi-5 (DoS) — Ajv schema limits (`maxWords: 500`, `maxTextLength: 50_000`, `maxMaskDimensions: 2000x2000`) must be in the schema from the first deployed endpoint, never retrofitted

### Phase 2: NLP Pipeline (parallel with Phase 3)
**Rationale:** NLP is independent of geometry and can be built and tested in isolation. Word list with correct font sizes is the required input to the Packer; nothing in the geometry system depends on NLP. Building NLP first also yields early-stage debug visibility (the `/render` response can include `ScoredWord[]` metadata before any rendering happens).
**Delivers:** `POST /render` returns `ScoredWord[]` metadata in response; verified TF-IDF-AP scoring, Zipf normalization, multilingual stopword removal
**Uses:** `natural` 8.1.1, `stopword`, `compromise` (EN-only enrichment), `franc` (language detection)
**Implements:** `src/nlp/` module — Tokenizer, TF-IDF-AP, Zipf normalizer, positional weighter
**Avoids:** Pitfall M-1 (Zipf division-by-zero on small corpora — corpus size guard + linear fallback below 20 unique words), Pitfall M-2 (language-blind stopwords — `franc` auto-detection before stopword removal), Pitfall M-4 (stemming destroys display form — stem-for-counting, surface-form-for-display data structure from day one)
**Research flag:** Standard NLP patterns; no additional research phase needed

### Phase 3: Geometry Foundation (parallel with Phase 2)
**Rationale:** SDF generation, MAT extraction, and bitmap collision board are the hardest technical problems in the engine and have the most research-validated risks. Building them before the Packer enables isolated testing of each geometric primitive against known reference fixtures (circle, square, star, concave crescent).
**Delivers:** `POST /render` returns shape metadata (bounds, MAT region count, SDF cache hit/miss); all geometric primitives validated against reference shapes
**Uses:** `sharp` 0.34.5 (mask preprocessing to binary buffer), hand-rolled Meijster EDT, `rbush` 3.0.1, `flatbush` 4.4.1
**Implements:** `src/geometry/` module — SDF generator, MAT extractor, bitmap collision board, SDF LRU cache
**Avoids:** Pitfall C-5 (SDF boundary instability — Meijster exact EDT is a day-one algorithm choice, not a retrofit), Pitfall C-1 (measureText inaccuracy — pixel-scan AABB contract established here for collision board)
**Research flag:** Algorithm implementation is high-risk; the Meijster EDT reference implementation should be validated against a known test fixture (circle mask: SDF values at center must equal radius in pixels) before Packer phase begins

### Phase 4: Word Packing
**Rationale:** Packer is the convergence point for NLP (word list with font sizes) and Geometry (SDF + MAT regions + collision board). It cannot start until both Phases 2 and 3 are complete. This is the most algorithmically complex phase.
**Delivers:** `POST /render` returns `PlacedWord[]` positions (no actual image yet); verified zero-collision placement across convex and concave test silhouettes
**Implements:** `src/optimizer/packer.ts` — spiral search, multi-centric MAT origins, bitmap collision, shrink-to-fit fallback (zero dropped words guarantee)
**Avoids:** Pitfall C-2 (spiral deadlock on concave shapes — MAX_SPIRAL_STEPS + multi-centric origins + async timeout), Pitfall M-3 (quadtree O(n²) degeneration — rbush R-tree avoids this entirely; verify rbush 3.0.1 behavior with 500-word stress test), Pitfall C-3 (rotated text false negatives — rotated sprites in bitmap from the start, not retrofitted)
**Research flag:** Multi-centric MAT origin selection may need additional research during planning — the Blueprint's Teil III §3.3 covers the theory but implementation details for branch detection are not fully specified in research files

### Phase 5: Renderer and PNG Export
**Rationale:** First phase that produces an actual image. Depends on the complete Packer output. Validates the full pipeline end-to-end for the first time.
**Delivers:** `POST /render` returns actual PNG image; golden-image regression tests established
**Uses:** `@napi-rs/canvas` 0.1.97 for draw loop and PNG export
**Implements:** `src/renderer/` + `src/export/` (PNG only)
**Avoids:** Pitfall C-4 (memory leak — fonts registered once at startup in module-level Set before any render), Pitfall Mi-1 (subpixel snap — positions integer-rounded at `fillText` call, float precision kept through optimization loop), Pitfall Mi-2 (font hinting drift — all fonts bundled in `assets/fonts/`, startup check verifies all registered fonts are resolvable)

### Phase 6: Refinement and SVG Export
**Rationale:** Force-directed refinement is a quality-improvement layer that requires the Packer to produce near-zero-overlap input first (refinement is a fine-tuner, not a collision resolver). SVG export is straightforward once the Renderer is working.
**Delivers:** Higher packing density; SVG format output; improved silhouette boundary fill (words closer to edge)
**Implements:** `src/optimizer/refiner.ts` (SDF gradient descent, convergence detection), `src/export/` SVG serializer
**Avoids:** Pitfall M-5 (force refinement divergence — enter refinement only if ≥95% of words pass bitmap collision; force magnitude clamped to MAX_FORCE = 5.0px/step; boundary containment force for out-of-mask words), Pitfall Mi-3 (SVG XSS — color allow-list regex + fontFamily allow-list + pre-escaped SVG template slots)

### Phase 7: Production Hardening
**Rationale:** Final phase before integration with parent Shopify app. Addresses all moderate/minor pitfalls not resolved in earlier phases and validates the sub-500ms performance target under realistic load.
**Delivers:** `< 500ms P99` for 200 words benchmark; RSS monitoring via `/health/internal`; SDF cache hit rate metrics; coarse-to-fine resolution pipeline; PM2 `max_memory_restart` configured
**Implements:** Coarse-to-fine rendering (8px → 32px → 128px → target resolution); SDF cache instrumentation; graceful shutdown (SIGTERM → drain); structured error logging
**Avoids:** All remaining pitfalls; validates Phase 7 architecture hardening checklist from ARCHITECTURE.md

### Phase Ordering Rationale

- **Foundation first** (Phase 1): Integration contract with BullMQ must exist before any other work proceeds; security limits must be in the schema from the first endpoint.
- **NLP and Geometry in parallel** (Phases 2 and 3): They share no data dependencies and can be validated independently against reference fixtures.
- **Packer after both** (Phase 4): Hard data dependency on both word list (NLP) and shape context (Geometry); the most complex phase benefits from isolated predecessor validation.
- **Render before Refine** (Phase 5 before 6): Refinement requires real rendered output to validate improvement; golden-image tests from Phase 5 become the regression baseline for Phase 6.
- **Hardening last** (Phase 7): Performance optimization and coarse-to-fine pipeline require a working end-to-end render to profile against.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Geometry):** MAT branch detection algorithm is not fully specified in research; Meijster EDT implementation details should be validated against a reference implementation before coding begins. Consider running `/gsd-research-phase` specifically on MAT skeleton extraction.
- **Phase 4 (Packer):** Multi-centric MAT origin selection strategy — the Blueprint's Teil III §3.3 provides theory but the implementation decision for how many spiral origins to spawn and how to score candidate origins needs a deeper dive.

Phases with standard patterns (no research phase needed):
- **Phase 1 (Foundation):** Fastify v5 setup is well-documented; BullMQ HTTP integration pattern is an established async request-reply pattern.
- **Phase 2 (NLP):** `natural`, `stopword`, `compromise`, and `franc` are all well-documented; TF-IDF-AP is a thin wrapper on `natural`'s built-in TF-IDF.
- **Phase 5 (Renderer):** Canvas draw loop is standard; @napi-rs/canvas API mirrors browser Canvas API.
- **Phase 7 (Hardening):** Performance profiling and PM2 configuration are standard Node.js production patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core libs (@napi-rs/canvas, sharp, rbush, natural) verified against npm April 2026; @napi-rs/canvas pre-1.0 is a minor risk; d3-force integration is MEDIUM (no explicit Node.js benchmark for this use case) |
| Features | HIGH | Grounded in d3-cloud source, competitor analysis (WordArt, Mentimeter, Python wordcloud), AeroCloud Blueprint, and academic literature on word cloud UX |
| Architecture | HIGH | Pipeline pattern and module boundaries are HIGH confidence; SDF caching strategy is MEDIUM (LRU eviction behavior under concurrent load not profiled); BullMQ integration pattern is HIGH |
| Pitfalls | HIGH | Majority of pitfalls verified against official issue trackers (node-canvas #1703, #1974, skia-canvas #145), CVE databases, and d3-cloud canonical source |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **@napi-rs/canvas pre-1.0 stability:** Library is at 0.1.97 and has not reached 1.0. Monitor for breaking changes on minor version bumps. Fallback path is `skia-canvas` 3.0.8. Flag this at Phase 5 planning — if any breaking change appears, evaluate migration cost before committing to renderer implementation.
- **500ms performance target validation:** The P99 < 500ms target is plausible based on the selected stack (Meijster O(n), rbush O(log n), Skia native rendering) but has not been benchmarked. The coarse-to-fine pipeline in Phase 7 may be required even for the base case, not just for optimization. Flag this for measurement at end of Phase 5.
- **German compound word splitting:** `natural`'s German Porter stemmer handles normalization but does not split compound words ("Jahresurlaub" stays unsplit). For v1 this is acceptable; for German-market merchants this is a known quality gap. Document as a known limitation, not a bug.
- **MAT implementation specifics:** The Medial Axis Transform branch detection algorithm is referenced in the Blueprint but specific implementation guidance (algorithm choice, skeleton pruning strategy) is not detailed in research files. This is the highest-risk technical gap for Phase 3.

## Sources

### Primary (HIGH confidence)
- `raw/sources/AeroCloud-Blueprint.md` — canonical engine specification (all 10 parts)
- `.planning/PROJECT.md` — current scope, out-of-scope decisions, key decisions log
- d3-cloud GitHub (jasondavies/d3-cloud) — canonical JS word cloud algorithm and documented limitations
- Jason Davies word cloud description — algorithm canonical reference
- node-canvas issues #1703, #331, #1974 — measureText and memory leak bugs confirmed
- skia-canvas issue #145 — async memory leak confirmed
- sharp official docs (pixelplumbing.com) — performance benchmarks, API
- Fastify v5 release notes and migration guide
- BullMQ docs: sandboxed processors pattern
- CVE-2024-45801, CVE-2024-47875 — DOMPurify SVG bypass vectors

### Secondary (MEDIUM confidence)
- PkgPulse 2026 canvas library comparison — @napi-rs/canvas vs node-canvas vs skia-canvas
- npm-compare.com flatbush vs rbush benchmark
- Berkeley iSchool 2019 — rotation angle UX research
- Apache Superset PR #19977 — engineering evidence on rotation anti-feature
- IXD@Pratt word cloud UX analysis
- Sub-pixel Distance Transform (Acko.net) — EDT boundary artifacts
- Image.sc EDT raster-scan propagation error discussion

### Tertiary (LOW confidence — validate during implementation)
- @napi-rs/canvas performance characteristics under concurrent load (no explicit benchmark found)
- d3-force convergence time for 200 nodes on Node.js 22 (MEDIUM confidence; no server-side benchmark)
- German compound word impact on TF-IDF quality (no empirical data found for this domain)

---
*Research completed: 2026-04-06*
*Ready for roadmap: yes*
