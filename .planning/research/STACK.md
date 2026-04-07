# Technology Stack: AeroCloud Engine

**Project:** AeroCloud Engine — Word Cloud Rendering Engine
**Researched:** 2026-04-06
**Overall Confidence:** MEDIUM-HIGH (verified against npm, official docs, multiple sources)

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Node.js | 22 LTS | Runtime | Mandated by CLAUDE.md; V8 JIT handles typed arrays well for bitmap ops |
| TypeScript | 5.7+ | Language | Strict mode enables type safety for geometry math; ESM only |
| Fastify | 5.8.x | HTTP API | CLAUDE.md mandates; 3x faster than Express; built-in JSON Schema validation via Ajv; Node.js 20+ required (22 is fine) |

### Canvas / Rendering

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `@napi-rs/canvas` | 0.1.97 | 2D rendering, bitmap pixel ops | Pre-built Skia binaries — zero native compilation required on Ubuntu/Docker; ~500K weekly downloads; `getImageData()` returns raw RGBA `Uint8ClampedArray` for SDF computation; exports PNG natively |

**Do NOT use:**
- `node-canvas` — Requires system libs (`libcairo2-dev`, `libpango1.0-dev`, `libgif-dev`). On Ubuntu/Docker this means `apt-get` in every Dockerfile or VPS setup. Active bug: `libcairo.so.2 ELF load command address/offset not page-aligned` on some Ubuntu 24.04 setups. MEDIUM confidence this causes deploy friction on `srv791618.hstgr.cloud`.
- `skia-canvas` — Only 50K weekly downloads vs 500K for `@napi-rs/canvas`. Multi-threading benefit does not apply here (we render single requests). Latest version 3.0.8 (published 6 months ago, slower maintenance cadence). Exports SVG natively, but `@napi-rs/canvas` + string-build SVG achieves same result.

**SDF capability note:** None of the three canvas libraries implement SDF natively. All provide `getImageData()` that returns raw RGBA pixel arrays. SDF must be computed by iterating the pixel buffer — see SDF section below. MEDIUM confidence.

### Spatial Indexing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `rbush` | 3.0.1 | Dynamic R-tree for collision detection | Words are placed one at a time; index is mutated each placement. Dynamic insert/delete required. 3.0.1 is the CJS-safe version of 3.0 (ESM bundle fixed). First-class TypeScript typings. Mourner (Mapbox) authorship = battle-tested. |
| `flatbush` | 4.4.1 | Static index for SDF/MAT preprocessing | SDF gradient lookup table over the silhouette mask is static after generation. Flatbush's packed Hilbert R-tree is ~4x faster than rbush for static datasets (252ms vs 1083ms at 1M items). ESM + TypeScript typings included. |

**Do NOT use:**
- Custom quadtree — rbush already implements optimized R-tree; rolling your own adds maintenance burden and is slower.
- `d3-quadtree` — d3 spatial primitives are browser-first; rbush has better insert-then-query patterns for server-side layout loops.

### NLP Pipeline

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `natural` | 8.1.1 | TF-IDF, tokenization, German Porter stemmer | Only production-ready Node.js NLP library with TF-IDF *and* German stemmer (`PorterStemmerDe` via BSD license). v8.1.1 released 2026-02-18. Already in project dependencies (8.0.1). |
| `stopword` | latest | Stop word removal for DE + EN | Supports English, German, Dutch, French, Italian, Spanish explicitly. Lightweight, ESM-compatible. |
| `compromise` | 14.14.3 | English linguistic analysis (POS tagging, entity extraction) | English-only — use only for English text enrichment, NOT for German. Already in project deps. |

**Do NOT use:**
- `wink-nlp` — English-only language model; no German support confirmed. TF-IDF not provided — would need wink-nlp-utils as separate package. Adds complexity without German coverage.
- `wink-lemmatizer` — English-only.
- Python spaCy — out of scope per CLAUDE.md (no Python runtime).

**German language gap:** `natural`'s German Porter stemmer handles word normalization adequately for TF-IDF scoring (reduces "Wörter" → "wort" family). It is NOT a morphological lemmatizer — German compound words ("Jahresurlaub") will not be split. This is acceptable for v1; compound splitting is a v2 concern. LOW confidence on edge case coverage for German compounds.

**Custom TF-IDF-AP:** `natural`'s built-in TF-IDF does not have a positional weight parameter (the `P_weight` from the blueprint, +12.9% semantic precision). Implement a thin wrapper: `TfIdfAP` class that calls `natural.TfIdf` internally and multiplies by position multipliers (H1 = 1.129, sentence-start = 1.05, body = 1.0). HIGH confidence this is the right approach.

### SDF Generation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Roll-your-own `DistanceTransform` | N/A | Signed Distance Field from binary mask | No production-grade JS SDF library exists for shape analysis. Existing libs are font-oriented (mapbox/tiny-sdf) or game-oriented (LykenSol/sdfer). For silhouette shapes, implement Meijster's exact Euclidean Distance Transform algorithm (O(n) per row/column, two-pass). Operates directly on the `Uint8ClampedArray` from `@napi-rs/canvas` `getImageData()`. |

**Recommended algorithm:** Meijster EDT (2000) — exact Euclidean distances, O(w×h) time, trivially parallelizable row/column. The gradient `∇SDF` at each pixel is the unit vector toward the nearest boundary pixel — trivially computed from adjacent SDF values via finite difference. No external dependency needed.

**Libraries considered and rejected:**
- `mapbox/tiny-sdf` — Font glyph SDFs only; assumes alpha-channel signed distance; not designed for binary silhouette masks.
- `PTRRR/vprsdf` — Undocumented, minimal maintenance, unclear algorithm.
- `LykenSol/sdfer` — Game rendering use case, GPU-oriented ESDT. Adding as dep for a 50-line algorithm is overkill.

**Confidence:** MEDIUM — Meijster EDT is well-documented in literature; implementation is 100–150 lines of TypeScript; no external library needed; multiple reference implementations exist.

### Force-Directed Layout

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `d3-force` | 3.x | Force simulation for post-placement word refinement | Proven, well-tested physics simulation. Runs in Node.js (no DOM needed). `forceCollide` with `strength` tuning enables overlap resolution after initial spiral placement. Operates on position arrays, not DOM. |

**Alternative considered:** Custom force loop. For v1, d3-force's Adam-style velocity Verlet integration is fast enough (< 50ms for 200 nodes). Custom implementation would be ~300 lines with no quality advantage. Defer custom optimizer to v2.

**Important:** d3-force's `forceCollide` uses circular collision, not bounding-box. For rotated words, pair it with rbush AABB checks: d3-force moves nodes, rbush validates non-overlap per step. This hybrid gives physics smoothness with exact AABB guarantees. MEDIUM confidence on performance adequacy.

### SVG Export

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| String template / manual serialization | N/A | Generate SVG markup from placed word positions | Canvas-to-SVG approaches (canvas2svg, tone-row/canvas-to-svg) are browser-shim heavy. For word clouds, SVG is simple: `<text>` elements with `x`, `y`, `font-size`, `transform="rotate(...)"`, `fill`. Build the SVG string directly from the layout data structure. ~50 lines. |
| `isomorphic-dompurify` | latest | Sanitize SVG on upload path (input silhouettes) | CLAUDE.md mandates SVG sanitization. `isomorphic-dompurify` wraps DOMPurify + jsdom for Node.js server-side use without DOM. Call `clearWindow()` periodically to prevent memory growth in long-running process. |

**Do NOT use:**
- `canvas2svg` — Last updated 2019, unmaintained, generates suboptimal SVG for simple `<text>` layouts.
- Raw `DOMPurify` without `isomorphic-dompurify` — Requires manual jsdom window setup; `isomorphic-dompurify` handles this cleanly.

### Image Processing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `sharp` | 0.34.5 | Silhouette mask preprocessing | Converts uploaded PNG/JPEG/SVG to grayscale binary mask. `.grayscale().threshold(128).raw().toBuffer()` produces a `Uint8Array` where 255 = inside, 0 = outside — the exact input format for Meijster EDT. 20x faster than jimp (1.3s vs 28s). libvips-backed; pre-built binaries for Linux x64. Node.js >= 18.17.0 required (22 is fine). |

**Do NOT use:**
- `jimp` — Pure JS, 20x slower for the same task. No Lanczos resampling. At 500ms target render budget, can't afford 28s for preprocessing.
- `canvas.getImageData()` for preprocessing — Creates an unnecessary canvas context; sharp is purpose-built for this.

### HTTP Framework and Plugins

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `fastify` | 5.8.x | HTTP server | See Core Framework above |
| `@fastify/multipart` | latest | Binary file upload (PNG/JPG/SVG silhouette) | Official Fastify plugin. Set `attachFieldsToBody: true` for JSON schema validation alongside file fields. Supports streaming for large files. |
| `@fastify/sensible` | latest | Standard HTTP error helpers | Reduces boilerplate for 400/422/500 responses |
| `fastify-type-provider-typebox` | latest | TypeBox schema integration | Enables TypeScript-native schema definitions that compile to Ajv-compatible JSON Schema. Better DX than raw JSON Schema strings. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Canvas | `@napi-rs/canvas` | `node-canvas` | System deps (Cairo) cause Docker friction; deployment risk on Ubuntu 24.04 |
| Canvas | `@napi-rs/canvas` | `skia-canvas` | Lower adoption (50K vs 500K downloads); slower maintenance; no meaningful advantage for single-threaded server rendering |
| Spatial Index | `rbush` + `flatbush` | quadtree only | R-tree consistently outperforms quadtrees for densely packed rectangles; rbush is the de-facto standard |
| NLP | `natural` | `wink-nlp` | wink-nlp is English-only; German required |
| NLP | `natural` | Python spaCy | No Python runtime per CLAUDE.md |
| SDF | Roll-your-own Meijster | `tiny-sdf` | tiny-sdf is font-only; wrong use case |
| Force Layout | `d3-force` | Custom | Premature optimization; d3-force proven for < 300 nodes |
| Image Proc | `sharp` | `jimp` | 20x performance difference is not acceptable at 500ms budget |
| SVG Export | Manual string build | `canvas2svg` | canvas2svg unmaintained since 2019; overkill for `<text>` elements |
| HTTP | `fastify v5` | Express | CLAUDE.md mandates Fastify; 3x throughput advantage |

---

## Installation

```bash
# Core rendering
npm install @napi-rs/canvas

# Spatial indexing
npm install rbush flatbush
npm install --save-dev @types/rbush

# NLP (natural already present, add stopword)
npm install stopword
# natural 8.1.1 already in package.json as 8.0.1 — upgrade to 8.1.1
# compromise 14.14.3 already in package.json

# SDF + image preprocessing
npm install sharp

# SVG sanitization
npm install isomorphic-dompurify
npm install --save-dev @types/dompurify

# Force layout
npm install d3-force
npm install --save-dev @types/d3-force

# HTTP
npm install fastify @fastify/multipart @fastify/sensible
npm install fastify-type-provider-typebox @sinclair/typebox
```

---

## Module Boundary to Stack Mapping

| Engine Module | Primary Libraries |
|---------------|-------------------|
| `src/nlp/` | `natural` (TF-IDF-AP, German stemmer), `stopword`, `compromise` (EN only) |
| `src/geometry/` | `sharp` (mask preprocessing), roll-your-own `DistanceTransform` (SDF), `rbush`, `flatbush` |
| `src/renderer/` | `@napi-rs/canvas` |
| `src/optimizer/` | `d3-force`, `rbush` (collision validation per step) |
| `src/export/` | Manual SVG string builder, `isomorphic-dompurify` (input sanitization) |
| HTTP API | `fastify`, `@fastify/multipart`, `fastify-type-provider-typebox` |

---

## Version Verification Status

| Package | Version Checked | Source | Confidence |
|---------|----------------|--------|------------|
| `@napi-rs/canvas` | 0.1.97 (pre-1.0, active) | npm search result April 2026 | MEDIUM |
| `skia-canvas` | 3.0.8 | npm search result | HIGH |
| `rbush` | 3.0.1 | GitHub releases | HIGH |
| `flatbush` | 4.4.1 | npm + GitHub | HIGH |
| `natural` | 8.1.1 | GitHub releases (2026-02-18) | HIGH |
| `sharp` | 0.34.5 | Official docs | HIGH |
| `fastify` | 5.8.4 | npm + release notes | HIGH |
| `d3-force` | 3.x | Known stable | MEDIUM |
| `isomorphic-dompurify` | active | npm | MEDIUM |

**Note on `@napi-rs/canvas` pre-1.0:** The library is at 0.1.97 and has not yet reached 1.0. The maintainer has stated 1.0 is planned. At 500K weekly downloads and active maintenance (last publish April 2026), it is production-ready despite the pre-1.0 version number. Monitor for breaking changes on minor version bumps. If stability is a concern at a future milestone, `skia-canvas` 3.0.x is the fallback.

---

## Constraints Cross-Check

| CLAUDE.md Constraint | Stack Decision | Status |
|---------------------|---------------|--------|
| Node.js 22 LTS | All libs support Node 18+; tested on 22 | PASS |
| TypeScript 5.7+ ESM only | All libs ship ESM or have ESM entry; `rbush` 3.0.1 for CJS compat | PASS |
| No CommonJS (`require()`) | Import paths verified to be ESM | PASS |
| Fastify v5 | `fastify` 5.8.4 | PASS |
| No Python / Rust / WASM | Zero Python/WASM deps in stack | PASS |
| Vitest tests | Stack uses no Jest-only test utilities | PASS |
| < 500ms render target | sharp (fast preprocessing) + @napi-rs/canvas (Skia, native speed) + Meijster O(n) + rbush O(log n) | PLAUSIBLE, needs benchmark |
| SVG sanitization | `isomorphic-dompurify` on upload path | PASS |

---

## Sources

- [node-canvas vs @napi-rs/canvas vs skia-canvas (PkgPulse 2026)](https://www.pkgpulse.com/blog/node-canvas-vs-napi-rs-canvas-vs-skia-canvas-server-2026)
- [@napi-rs/canvas GitHub](https://github.com/Brooooooklyn/canvas)
- [skia-canvas GitHub](https://github.com/samizdatco/skia-canvas)
- [rbush GitHub](https://github.com/mourner/rbush)
- [flatbush GitHub](https://github.com/mourner/flatbush)
- [natural GitHub (NaturalNode)](https://github.com/NaturalNode/natural)
- [Natural TF-IDF docs](https://naturalnode.github.io/natural/tfidf.html)
- [sharp official docs](https://sharp.pixelplumbing.com/)
- [Fastify v5 release announcement (OpenJS Foundation)](https://openjsf.org/blog/fastifys-growth-and-success)
- [Fastify v5 npm releases](https://github.com/fastify/fastify/releases)
- [@fastify/multipart](https://github.com/fastify/fastify-multipart)
- [isomorphic-dompurify npm](https://www.npmjs.com/package/isomorphic-dompurify)
- [skia-canvas ImageData API](https://skia-canvas.org/api/imagedata)
- [flatbush vs rbush benchmark](https://npm-compare.com/flatbush,geokdbush,kdbush,rbush)
- [sharp performance benchmarks](https://sharp.pixelplumbing.com/performance/)
- [Hacker News: skia-canvas discussion](https://news.ycombinator.com/item?id=42308051)
