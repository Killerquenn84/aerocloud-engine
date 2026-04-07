# Roadmap: AeroCloud Engine

## Overview

AeroCloud Engine is built in five phases. Phase 1 establishes the Fastify HTTP API and pipeline shell so the parent Shopify app's BullMQ workers can reach the engine over HTTP from day one. Phases 2 and 3 build the two independent subsystems (NLP and Geometry) that converge at Phase 3 (Word Packer) — these can be executed in parallel by a two-person or AI-assisted team. Phase 4 completes the rendering pipeline (canvas draw loop, PNG/SVG export, force-directed refinement). Phase 5 hardens the service for production (coarse-to-fine pipeline, performance benchmarks, structured logging, full test suite). Every v1 requirement maps to exactly one phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Fastify v5 HTTP server, /render stub, /health endpoints, Ajv schema validation, pipeline shell, TDD harness
- [ ] **Phase 2: NLP Pipeline** - TF-IDF-AP scoring, Zipf normalization, multilingual stopword removal, language detection (PARALLEL with Phase 3)
- [ ] **Phase 3: Geometry Foundation** - Meijster EDT SDF, MAT skeleton, bitmap collision board, SDF LRU cache, spatial indexes (PARALLEL with Phase 2)
- [ ] **Phase 4: Packer + Renderer + Export** - Spiral word packing, canvas rendering, PNG/SVG export, SDF gradient refinement
- [ ] **Phase 5: Production Hardening** - Coarse-to-fine pipeline, performance benchmarks, structured logging, full test suite, PM2 config

## Phase Details

### Phase 1: Foundation
**Goal**: Parent app's BullMQ workers can reach the engine over HTTP and receive a valid response; all input limits enforced at schema layer before any pipeline logic runs
**Depends on**: Nothing (first phase)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, API-07
**Success Criteria** (what must be TRUE):
  1. `GET /health` returns HTTP 200 JSON with version and uptime from a running PM2 process
  2. `POST /render` with a valid payload returns HTTP 200 with a stub response (no rendering yet); `POST /render` with an oversized text field (> 50 000 chars) or mask dimension exceeding 2000px returns HTTP 400 before any pipeline code runs
  3. `GET /health/internal` returns HTTP 401 without the `x-internal-token` header and HTTP 200 with RSS/uptime stats when the token is present
  4. `POST /render` with a payload missing required fields returns a structured error JSON with the correct HTTP status code (400/422) matching the domain error class
  5. Sending SIGTERM to the process allows in-flight requests to drain and exits cleanly with code 0
**Plans**: TBD

### Phase 2: NLP Pipeline
**Goal**: Given raw merchant text, the pipeline produces a scored, normalized, multilingual word list with correct Zipf-weighted font sizes ready to feed the Packer
**Depends on**: Phase 1
**Requirements**: NLP-01, NLP-02, NLP-03, NLP-04, NLP-05, NLP-06, NLP-07
**Parallelization hint**: Can be built and tested in parallel with Phase 3 — NLP and Geometry share no data dependencies and both converge at Phase 4
**Success Criteria** (what must be TRUE):
  1. `POST /render` with English merchant review text returns a `ScoredWord[]` metadata array in the response body with correctly removed stopwords (no "the", "and", "is" in output)
  2. `POST /render` with German text detects the language automatically and removes German stopwords ("und", "die", "der", "das" absent from output)
  3. The word with the highest TF-IDF-AP score receives `fontSize` equal to `maxFontSize`; all other words scale logarithmically (Zipf) — not linearly and not by square root
  4. Input text "running runner runs run" produces display token "running" (stem-for-counting, surface-form-for-display) not the stem "run"
  5. Input text with fewer than 20 unique words uses linear normalization fallback with no NaN or division-by-zero errors; single-word input returns a single word entry at default font size
**Plans**: TBD
**UI hint**: no

### Phase 3: Geometry Foundation
**Goal**: Given a base64 PNG silhouette, the pipeline produces an exact Signed Distance Field, a Medial Axis Transform skeleton, and a bitmap collision board — all validated against reference fixtures
**Depends on**: Phase 1
**Requirements**: GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07
**Parallelization hint**: Can be built and tested in parallel with Phase 2 — convergence point is Phase 4
**Success Criteria** (what must be TRUE):
  1. `POST /render` with a circle mask returns shape metadata (bounds, MAT region count, SDF cache hit/miss) in the response; the SDF value at the circle center equals the circle radius in pixels within ±1px tolerance
  2. Submitting the same mask twice results in a cache hit on the second request (SDF not recomputed); cache stats visible via `/health/internal`
  3. The SDF for a star-shaped mask and a crescent mask each produce a non-zero MAT region count greater than 1 (multi-branch detection confirmed), validated against stored reference fixtures
  4. The bitmap collision board correctly reports a pixel as occupied after a word sprite is painted into it; pixel-scanned bounding boxes (not `measureText`) are used for all AABB calculations
  5. The `flatbush` static index over SDF lookup points reports O(log n) query time (benchmark verifies < 5ms for 2000×2000 mask)
**Plans**: TBD
**UI hint**: no

### Phase 4: Packer + Renderer + Export
**Goal**: `POST /render` returns an actual PNG image with zero visually overlapping words placed entirely within the silhouette boundary, and an SVG variant with XSS-safe output
**Depends on**: Phase 2, Phase 3
**Requirements**: PACK-01, PACK-02, PACK-03, PACK-04, PACK-05, PACK-06, PACK-07, PACK-08, REND-01, REND-02, REND-03, REND-04, REND-05, REND-06, REND-07, REND-08
**Success Criteria** (what must be TRUE):
  1. `POST /render` returns a valid PNG buffer; pixel-inspection confirms no two words share a non-transparent pixel (zero overlap) in the output image for both convex (circle) and concave (star, crescent) silhouettes
  2. All 200 test words are present in the output image — no words are dropped; words that would exceed the available space are shrunk to minimum 8px font size rather than omitted
  3. The spiral search for each word terminates within `MAX_SPIRAL_STEPS = 10000` iterations and the entire packing loop completes within 450ms (enforced by `Promise.race` timeout); no BullMQ job hangs
  4. SVG output contains only hex colors matching `^#[0-9a-fA-F]{3,8}$` and only font-family values from the registered font allow-list; submitting `fontFamily: "serif</style><script>alert(1)</script>"` returns HTTP 400
  5. RSS memory does not grow between requests when the same render is called 100 consecutive times (font registration happens once at startup via module-level Set, never per-request)
**Plans**: TBD
**UI hint**: no

### Phase 5: Production Hardening
**Goal**: The engine meets the < 500ms P99 render target for 200 words, operates safely under sustained BullMQ load, and has a complete test suite (unit, integration, golden-image, property-based, performance)
**Depends on**: Phase 4
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. The benchmark suite reports P99 render time < 500ms for 200-word input at 800×600 resolution on the production VPS; the coarse-to-fine pipeline (8px → 32px → 128px → target) is the active code path
  2. Same input text + same seed value produces byte-identical PNG output on two consecutive requests (seed-based reproducibility verified by binary diff)
  3. All Vitest unit tests pass for every pure function in the pipeline (TDD red-green-refactor); golden-image regression tests pass for circle, square, star, and crescent reference masks
  4. `fast-check` property-based tests confirm that the collision detection invariant holds for all word sizes and rotation values (0° and 90°) across 10 000 generated test cases
  5. PM2 ecosystem config includes `max_memory_restart` and `/health/internal` reports RSS; a test call with 500-word input + 2000×2000 mask completes without triggering `max_memory_restart`
**Plans**: TBD
**UI hint**: no

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5
Note: Phases 2 and 3 can be worked in parallel — they are independent and converge at Phase 4.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/TBD | Not started | - |
| 2. NLP Pipeline | 0/TBD | Not started | - |
| 3. Geometry Foundation | 0/TBD | Not started | - |
| 4. Packer + Renderer + Export | 0/TBD | Not started | - |
| 5. Production Hardening | 0/TBD | Not started | - |
