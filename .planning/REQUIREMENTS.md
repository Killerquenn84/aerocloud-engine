# Requirements: AeroCloud Engine

**Defined:** 2026-04-07
**Core Value:** Precise silhouette filling with semantic word hierarchy — words placed inside any shape with correct visual weight (Zipf-normalized) and zero overlap.

## v1 Requirements

### API (HTTP Service)

- [ ] **API-01**: Engine exposes Fastify v5 HTTP server on configurable port
- [ ] **API-02**: `POST /render` accepts JSON payload with `text`, `mask` (base64 PNG), and render options
- [ ] **API-03**: `GET /health` returns 200 with version, uptime (public, no auth)
- [ ] **API-04**: `GET /health/internal` returns RSS, queue depth, SDF cache stats (auth required)
- [ ] **API-05**: All routes use Ajv schema validation with hard limits (`maxWords: 500`, `maxTextLength: 50000`, `maxMaskDimensions: 2000x2000`)
- [ ] **API-06**: Server returns structured error JSON with HTTP status mapping for all 6 domain error classes
- [ ] **API-07**: Graceful shutdown on SIGTERM (drain in-flight requests, exit cleanly)

### NLP

- [ ] **NLP-01**: Tokenize input text using `natural` library with language-specific tokenizer
- [ ] **NLP-02**: Auto-detect input language using `franc` (minimum: English, German)
- [ ] **NLP-03**: Remove stopwords per detected language using `stopword` package
- [ ] **NLP-04**: Compute TF-IDF-AP scores with positional weighting (title/H1 boost +12.9%)
- [ ] **NLP-05**: Apply Zipf-law log-normalization for font sizing (NOT linear, NOT sqrt)
- [ ] **NLP-06**: Preserve display surface form while using stem for counting (stem→surface mapping)
- [ ] **NLP-07**: Guard against small-corpus division-by-zero (linear fallback below 20 unique words)

### Geometry

- [ ] **GEO-01**: Decode base64 silhouette mask via `sharp` to binary buffer
- [ ] **GEO-02**: Generate exact Signed Distance Field via Meijster EDT algorithm
- [ ] **GEO-03**: Compute Medial Axis Transform skeleton with branch detection
- [ ] **GEO-04**: Cache SDF in module-level LRU (50 entries max, key = sha256(maskBuffer))
- [ ] **GEO-05**: Provide bitmap collision board with 1-bit-per-pixel storage
- [ ] **GEO-06**: Index static SDF lookups via `flatbush` for O(log n) gradient queries
- [ ] **GEO-07**: Validate SDF correctness against reference fixtures (circle, square, star, crescent)

### Word Packing

- [ ] **PACK-01**: Place words via Archimedean spiral search seeded at MAT branch origins (multi-centric)
- [ ] **PACK-02**: Hard-cap spiral iterations at `MAX_SPIRAL_STEPS = 10000` per word
- [ ] **PACK-03**: Wrap entire packing loop in `Promise.race([place(), timeout(450)])` to prevent BullMQ job hangs
- [ ] **PACK-04**: Detect collisions via pixel-scanned bounding boxes (NOT `measureText` rectangles)
- [ ] **PACK-05**: Validate collisions on rotated text via rotated pixel sprites
- [ ] **PACK-06**: Index dynamic word collision via `rbush` R-tree (NOT quadtree)
- [ ] **PACK-07**: Guarantee zero dropped words via shrink-to-fit fallback (minimum font size 8px)
- [ ] **PACK-08**: Restrict word rotation to 0° or 90° only (no arbitrary angles)

### Renderer & Export

- [ ] **REND-01**: Render placed words via `@napi-rs/canvas` 2D context
- [ ] **REND-02**: Register all fonts ONCE at worker startup (never per-request) — track via module-level Set
- [ ] **REND-03**: Bundle fonts in-repo at `assets/fonts/` (no external font URLs)
- [ ] **REND-04**: Snap word positions to integers before `fillText` (prevent subpixel artifacts)
- [ ] **REND-05**: Export rendered output as PNG buffer via canvas `toBuffer('image/png')`
- [ ] **REND-06**: Export rendered output as SVG with allow-list-validated colors and font names
- [ ] **REND-07**: Validate hex colors against `^#[0-9a-fA-F]{3,8}$` regex
- [ ] **REND-08**: Validate `fontFamily` against allow-list of registered font names

### Performance & Production

- [ ] **PERF-01**: Implement coarse-to-fine pipeline (8px → 32px → 128px → target resolution)
- [ ] **PERF-02**: P99 render time < 500ms for 200 words on production VPS
- [ ] **PERF-03**: PM2 `max_memory_restart` configured to prevent runaway memory
- [ ] **PERF-04**: Structured logging (JSON) for all errors with correlation IDs
- [ ] **PERF-05**: Seed-based reproducibility — same input + seed produces identical output

### Testing

- [ ] **TEST-01**: Vitest unit tests for every pure function in pipeline (TDD red-green-refactor)
- [ ] **TEST-02**: Golden-image regression tests for renderer output
- [ ] **TEST-03**: Integration test: full pipeline from text+mask → rendered PNG
- [ ] **TEST-04**: Property-based tests via `fast-check` for collision detection invariants
- [ ] **TEST-05**: Performance benchmark suite measuring 50/100/200-word render times

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced ML

- **ML-01**: BERT semantic embeddings for color clustering (sentence-transformers or transformers.js)
- **ML-02**: Optimal Transport via Sinkhorn-Knopp for word placement
- **ML-03**: PyTorch differentiable rendering with autograd Inner Loop
- **ML-04**: MAP-Elites Quality-Diversity outer loop for layout exploration
- **ML-05**: BOP-Elites variant with 700-evaluation budget
- **ML-06**: CQD metrics (omega function) and Pareto-front slider

### Advanced Export

- **EXP-01**: Seam Carving whitespace compression
- **EXP-02**: Bezier curve-based SVG paths for sub-millimeter precision
- **EXP-03**: PDF export via PDFKit
- **EXP-04**: Three.js animated WebGL rendering

### Internationalization

- **I18N-01**: CJK language support (Japanese, Chinese, Korean) with separate tokenizer + font stack
- **I18N-02**: German compound word splitting (Komposita-Zerlegung)
- **I18N-03**: Right-to-left language support (Arabic, Hebrew)

### Self-Learning

- **LEARN-01**: Self-Play nightly training pipeline (Monte-Carlo sampling → mutation → evaluation)
- **LEARN-02**: PostgreSQL vector archive for MAP-Elites elites
- **LEARN-03**: Adaptive font/color suggestions based on historical renders

## Out of Scope

Explicitly excluded from v1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Python runtime | Stack constraint — Node.js only |
| Rust/WASM browser preview | Separate compilation target, frontend concern |
| GPU/CUDA | No GPU on production VPS, no PyTorch in Node |
| Real-time interactive editing | Engine is HTTP service, not browser library |
| Internal job queue | Parent app already uses BullMQ — second queue creates dual failure modes |
| File-path mask input | Path traversal attack surface — base64/binary uploads only |
| Arbitrary rotation angles | Documented UX failure (Apache Superset PR #19977, Berkeley iSchool research) |
| Noise-word padding | Degrades semantic meaning |
| `ctx.measureText` for collisions | Confirmed inaccurate (node-canvas #331, #1703) — pixel scan only |
| External font URLs | Security risk + non-determinism |
| Cookie-based authentication | Service is consumed by BullMQ workers, not browsers |

## Traceability

Updated during roadmap creation. Each requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 to API-07 | TBD | Pending |
| NLP-01 to NLP-07 | TBD | Pending |
| GEO-01 to GEO-07 | TBD | Pending |
| PACK-01 to PACK-08 | TBD | Pending |
| REND-01 to REND-08 | TBD | Pending |
| PERF-01 to PERF-05 | TBD | Pending |
| TEST-01 to TEST-05 | TBD | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 0 (filled by roadmapper)
- Unmapped: 47 ⚠️ (will be resolved by roadmap step)

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after research synthesis*
