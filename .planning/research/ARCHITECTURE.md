# Architecture Patterns: AeroCloud Word Cloud Engine

**Domain:** Word cloud rendering engine — HTTP API service
**Researched:** 2026-04-06
**Overall confidence:** HIGH (pipeline stages and module split), MEDIUM (SDF caching strategy), HIGH (BullMQ integration pattern)

---

## Recommended Architecture

The engine is a **sequential rendering pipeline** exposed as a Fastify v5 HTTP API. The parent Shopify app's BullMQ workers are the only callers. The engine itself does NOT run a queue — it receives a job payload, executes the pipeline, and returns a result synchronously over HTTP. The queue lives in the parent app.

```
Parent App (BullMQ Worker)
        |
        | HTTP POST /render  (job payload as JSON)
        v
  Fastify v5 Route Handler
        |
        v
  [1] InputValidator          validate + sanitize text, shape, options
        |
        v
  [2] NLP Processor           tokenize -> score -> normalize -> word list
        |
        v
  [3] ShapeAnalyzer           decode image -> SDF -> MAT -> regions
        |  (SDF cached by shape hash)
        v
  [4] Packer                  spiral search + quadtree + bitmap collision
        |
        v
  [5] LayoutRefiner           force-directed refinement (SDF gradient descent)
        |
        v
  [6] Renderer                canvas draw -> rasterize (skia-canvas)
        |
        v
  [7] Exporter                encode PNG/SVG -> return buffer
        |
        v
  HTTP Response { image: base64, format, metadata }
        |
        v
  BullMQ Worker stores result, updates DB, notifies Shopify app
```

---

## Component Boundaries

### What Talks to What

| Component | Receives From | Sends To | Data Type |
|-----------|--------------|----------|-----------|
| InputValidator | HTTP request body | NLP Processor, ShapeAnalyzer | `ValidatedRequest` |
| NLP Processor | ValidatedRequest.text | Packer | `ScoredWord[]` (text, weight, fontSize) |
| ShapeAnalyzer | ValidatedRequest.shapeBuffer | Packer, LayoutRefiner | `ShapeContext` (SDF grid, MAT regions, bounds) |
| Packer | ScoredWord[], ShapeContext | LayoutRefiner | `PackedLayout` (word positions, rotations, scales) |
| LayoutRefiner | PackedLayout, ShapeContext | Renderer | `RefinedLayout` (same shape, tightened positions) |
| Renderer | RefinedLayout, ScoredWord[] | Exporter | `CanvasFrame` (skia-canvas Canvas object) |
| Exporter | CanvasFrame | HTTP response | `Buffer` (PNG or SVG bytes) |

### Module-to-Directory Mapping

The existing module split (`src/nlp`, `src/geometry`, `src/renderer`, `src/optimizer`, `src/export`) is CORRECT but the internal responsibilities need to be clarified for v1, since PyTorch-dependent features are deferred.

| Directory | v1 Responsibility | Contains |
|-----------|------------------|----------|
| `src/nlp/` | Text processing only | Tokenizer, stop-word filter, TF-IDF-AP scorer, Zipf/log normalizer, positional weighter |
| `src/geometry/` | Shape analysis and collision | SDF generator, MAT extractor, Quadtree, bitmap collision board, AABB checks |
| `src/renderer/` | Canvas drawing | skia-canvas draw loop, font measurement, word placement onto canvas |
| `src/optimizer/` | Packing heuristic + refinement | Spiral search placer, force-directed refiner (SDF gradient descent, NOT PyTorch) |
| `src/export/` | Output encoding | PNG encoder, SVG serializer, format selector |
| `src/api/` | HTTP layer (ADD THIS) | Fastify app factory, route handler `/render`, health routes, schema validation |
| `src/pipeline/` | Orchestration (ADD THIS) | `renderPipeline()` function that calls each stage in order, collects errors |

The blueprint's `optimizer` directory conflates two distinct v1 concerns: word packing (finding non-overlapping positions) and layout refinement (tightening placed words). Both live in `src/optimizer/` but should be separate files: `packer.ts` and `refiner.ts`.

---

## Data Flow

### The Core Rendering Pass

**Stage 1 — Input Validation** (`src/api/`)

Input: raw HTTP body `{ text: string, shape: base64string, options: RenderOptions }`

Output: `ValidatedRequest` — text length bounded (max 50 000 chars), shape decoded to `Buffer`, options normalized to defaults. Throw `ValidationError` here; never let invalid input reach NLP or geometry.

**Stage 2 — NLP Processing** (`src/nlp/`)

Input: `ValidatedRequest.text`

Process: tokenize via `compromise` (lemmatization, POS filtering) → stop-word removal via `natural` → TF-IDF-AP score → log-normalize scores → apply positional weights (H1, title, sentence-start) → sort descending by score → cap at `options.maxWords` (default 200).

Output: `ScoredWord[]` — `{ text: string, score: number, fontSize: number }[]`. `fontSize` is computed here as `round(minSize + (score / maxScore) * (maxSize - minSize))`. The word list is frozen after this stage and never mutated.

**Stage 3 — Shape Analysis** (`src/geometry/`)

Input: shape `Buffer` (PNG/SVG bytes)

Process: decode to pixel array → compute SDF via Felzenszwalb/Huttenlocher EDT algorithm (the same algorithm used by mapbox/tiny-sdf — HIGH confidence, well-documented) → compute Medial Axis Transform for skeleton → identify MAT regions for multi-centric packing → detect bounding box.

Output: `ShapeContext` — `{ sdf: Float32Array, width: number, height: number, matRegions: Region[], bounds: BoundingBox }`.

**SDF lives here and is computed once per shape.** Cache `ShapeContext` by `sha256(shapeBuffer)` in a simple `Map<string, ShapeContext>` (LRU-eviction at 50 entries). Re-computation costs ~50–200ms depending on image size; caching turns repeated renders of the same shape from ~150ms overhead to ~0ms.

**Stage 4 — Packing** (`src/optimizer/packer.ts`)

Input: `ScoredWord[]`, `ShapeContext`

Process: for each word (largest first), measure glyph bounding box on a scratch canvas → attempt spiral placement starting from MAT centroid → at each candidate position check: (1) AABB against placed words O(n), (2) bitmap collision board (bitwise AND on 32-bit int array). If collision: advance spiral. If placed: paint word bits into board and record position. If spiral exhausted: skip word (not an error — log and continue).

Output: `PackedLayout` — `{ placed: PlacedWord[], skipped: string[] }`. `PlacedWord` = `{ text, x, y, rotation, fontSize, width, height }`.

**Stage 5 — Layout Refinement** (`src/optimizer/refiner.ts`)

Input: `PackedLayout`, `ShapeContext`

Process: for each placed word, compute SDF gradient at word centroid — this is a simple vector lookup into the pre-computed SDF grid, not PyTorch autograd. Apply small displacement in gradient direction (toward silhouette boundary, away from center) weighted by a damping factor. Re-check bitmap collision after each move; undo move if new collision introduced. Run for `maxIterations` (default 30) or until no word moves more than 1px.

Output: `RefinedLayout` — same shape as `PackedLayout`, positions updated in place.

This is the v1 replacement for the blueprint's differentiable Inner Loop. It uses SDF gradient as a steering signal but has no autograd. This is the correct architectural decision for Node.js (confirmed in PROJECT.md key decisions).

**Stage 6 — Rendering** (`src/renderer/`)

Input: `RefinedLayout`, `ScoredWord[]` (for font/color info)

Process: create `skia-canvas` Canvas at target resolution → set background → for each `PlacedWord`, set font, fill color, rotation transform, draw text at (x, y) → rasterize.

Output: `CanvasFrame` — the skia-canvas `Canvas` instance.

Use `skia-canvas` over `node-canvas` because skia-canvas is multi-threaded (thread pool via rayon), GPU-accelerated, and produces sub-pixel accurate text rendering. `node-canvas` is single-threaded and Cairo-backed. For word cloud quality this difference is significant.

**Stage 7 — Export** (`src/export/`)

Input: `CanvasFrame`, `options.format` (png | svg)

Process: call `canvas.toBuffer('png')` or `canvas.svg` → return buffer with mime type.

Output: `{ buffer: Buffer, mimeType: string, width: number, height: number }`.

---

## State Management

**Use pure functions with explicit data pass-through between stages. Do not use shared mutable context objects.**

Rationale: Each stage is independently testable. The pipeline function is the only place that threads data through. Vitest unit tests can call each stage in isolation. This is the correct choice for this domain — rendering pipelines are inherently sequential transforms, not event-driven systems that benefit from shared state.

The one legitimate exception is the SDF cache (a module-level `Map`). It is explicitly bounded (LRU, 50 entries) and only written by `ShapeAnalyzer`. All other stages are stateless.

```typescript
// Correct pattern — pure function stages
export async function renderPipeline(request: ValidatedRequest): Promise<RenderResult> {
  const words = await processNlp(request.text, request.options);
  const shape = await analyzeShape(request.shapeBuffer);        // reads SDF cache
  const packed = await packWords(words, shape, request.options);
  const refined = await refineLayout(packed, shape, request.options);
  const frame = await renderToCanvas(refined, words, request.options);
  return exportFrame(frame, request.options);
}

// Wrong pattern — avoid
class RenderContext {
  words: ScoredWord[] = [];
  shape: ShapeContext | null = null;
  // ... stages mutate this object — harder to test, harder to parallelize
}
```

---

## API Design

**Use synchronous Fastify route, not a second queue inside the engine.**

The parent Shopify app already manages the job lifecycle via BullMQ. Adding a second queue inside the engine creates two queues to monitor, two retry mechanisms to coordinate, and double the failure modes. The engine should be a pure function over HTTP: request in, rendered image out.

`POST /render` — synchronous, returns image buffer. Target P99 < 500ms for 200 words.

`GET /health` — public, returns `{ status: 'ok', version }`.

`GET /health/internal` — requires `x-internal-token` header, returns queue depth (if any future queue is added), memory usage, SDF cache hit rate.

**No streaming needed for v1.** Word cloud rendering is a single-shot transform. Streaming is only useful if the image is very large (>10MB) or if partial previews are needed. Neither applies here.

**Schema validation at the Fastify route level (Ajv).** Fastify v5 uses Ajv by default. Define a JSON Schema for the request body. This removes an entire class of validation bugs before the pipeline touches the data.

```typescript
// Fastify route schema — validate before pipeline runs
const renderSchema = {
  body: {
    type: 'object',
    required: ['text', 'shape'],
    properties: {
      text: { type: 'string', maxLength: 50000 },
      shape: { type: 'string' },  // base64-encoded image
      options: {
        type: 'object',
        properties: {
          maxWords:  { type: 'integer', minimum: 1, maximum: 500, default: 200 },
          width:     { type: 'integer', minimum: 100, maximum: 4000, default: 800 },
          height:    { type: 'integer', minimum: 100, maximum: 4000, default: 600 },
          format:    { type: 'string', enum: ['png', 'svg'], default: 'png' },
        },
        additionalProperties: false,
      },
    },
    additionalProperties: false,
  },
};
```

---

## Error Handling

Errors are typed domain errors thrown at the stage where they are detected. The pipeline orchestrator catches them and maps to HTTP status codes. No error should leak implementation details to the caller.

| Error Class | Where Thrown | HTTP Status | Recovery |
|-------------|-------------|-------------|----------|
| `ValidationError` | InputValidator, Fastify schema | 400 | Client must fix request |
| `EmptyWordListError` | NLP Processor (all words filtered) | 422 | Return error with suggestion to reduce stop-words |
| `ShapeDecodeError` | ShapeAnalyzer (can't decode image) | 422 | Client must provide valid PNG/SVG |
| `ShapeTooComplexError` | ShapeAnalyzer (MAT fails) | 422 | Return with simplified shape suggestion |
| `PackingFailureError` | Packer (0 words placed) | 422 | Font too large for shape; try fewer words or smaller min font |
| `RenderError` | Renderer (canvas exception) | 500 | Internal; log full trace, return generic message |
| `ExportError` | Exporter (encoding failed) | 500 | Internal; PNG fallback if SVG failed |

**Graceful degradation rules:**
- If packer skips words (normal), log skipped count but succeed.
- If refiner cannot improve a word's position, keep original pack position. Never fail on refinement.
- If SVG export fails, fall back to PNG automatically.
- If SDF cache is full, evict oldest entry and continue (never fail due to cache pressure).
- `PackingFailureError` (0 placed words) is the only packing outcome that is a hard error.

---

## BullMQ Integration

The engine is a **separate PM2 process** (or child process) on the same server. The parent app's BullMQ worker calls it over HTTP — not via `import`. This separation is important: if the rendering engine crashes or OOMs, it does not take down the Shopify app server.

```
Parent App (PM2: wordcloud-app)
  BullMQ Worker (packages/worker/)
    └── RenderJob processor
          HTTP POST http://localhost:3001/render
              ↓
AeroCloud Engine (PM2: aerocloud-engine)
  Fastify server :3001
    └── /render route → renderPipeline()
```

**Integration contract (job data in BullMQ):**

```typescript
// In parent app: packages/worker/src/jobs/renderJob.ts
export interface RenderJobData {
  jobId: string;          // Shopify order/product ID used for dedup
  text: string;
  shapeUrl: string;       // Shopify CDN URL — worker fetches and passes as base64
  options: RenderOptions;
}

// Worker calls engine:
const response = await fetch('http://localhost:3001/render', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-job-id': data.jobId },
  body: JSON.stringify({ text: data.text, shape: await fetchAsBase64(data.shapeUrl), options: data.options }),
  signal: AbortSignal.timeout(30_000),  // 30s timeout
});
```

**Why HTTP not direct import:** BullMQ sandboxed processors (child_process) must serialize all data through Redis anyway. Calling the engine via HTTP is equivalent in terms of data isolation and is simpler to reason about, monitor, and deploy independently. The engine can be scaled horizontally (multiple PM2 instances, load balanced) without touching the parent app.

**Idempotency:** The engine is stateless — same input always produces same output. BullMQ retry on engine failure is safe. The parent worker handles deduplication (checking if render result already exists in DB before enqueueing).

---

## Suggested Build Order (Phase Dependencies)

The pipeline has hard dependencies between stages — you cannot build Stage 4 (Packer) without Stage 3 (ShapeAnalyzer providing SDF) or Stage 2 (NLP providing word list). Build order must follow this dependency graph.

```
Phase 1: Foundation
  src/api/         Fastify app factory, /health, /render stub that returns 200
  src/pipeline/    renderPipeline() shell — calls stubs
  → Deliverable: Engine starts, BullMQ worker can make HTTP contact

Phase 2: NLP
  src/nlp/         Tokenizer, scorer, normalizer
  → Deliverable: POST /render with text returns ScoredWord[] in response metadata
  → Unblocks: Packer (needs word list with sizes)

Phase 3: Geometry
  src/geometry/    SDF generator, MAT, Quadtree, bitmap board
  → Deliverable: POST /render returns shape metadata (bounds, MAT region count)
  → Unblocks: Packer and Refiner (both need ShapeContext)

Phase 4: Packer
  src/optimizer/packer.ts    Spiral search + bitmap collision
  → Deliverable: POST /render returns PlacedWord positions (no rendering yet)
  → Requires: Phase 2 + Phase 3 complete

Phase 5: Renderer + Exporter
  src/renderer/    skia-canvas draw loop
  src/export/      PNG encoder
  → Deliverable: POST /render returns actual PNG image
  → Requires: Phase 4 complete

Phase 6: Refinement + SVG
  src/optimizer/refiner.ts   SDF gradient descent refinement
  src/export/      SVG serializer
  → Deliverable: Higher quality output, SVG format support
  → Requires: Phase 5 complete

Phase 7: Hardening
  SDF caching, error handling, schema validation, health endpoints, perf tuning
  → Deliverable: Production-ready, < 500ms P99
```

Phases 2 and 3 can be developed in parallel — NLP and Geometry are independent of each other. They converge at Phase 4 (Packer).

---

## Scalability Considerations

| Concern | Now (1 shop) | At 100 concurrent renders | At 1000 concurrent renders |
|---------|-------------|--------------------------|---------------------------|
| SDF compute | In-process Map cache (50 entries, LRU) | Same — shapes repeat per shop | Redis-backed cache, shared across PM2 instances |
| Canvas threads | skia-canvas thread pool (auto) | Adequate | Consider multiple PM2 engine instances behind nginx |
| Memory per render | ~30–80 MB (canvas + SDF grid) | Monitor RSS; skia-canvas releases after export | Cap worker concurrency in parent BullMQ worker |
| Response time | Target < 500ms | Adequate with cache | Coarse-to-fine resolution (8px → 128px → target) |

---

## Sources

- d3-cloud algorithm internals: [DeepWiki: jasondavies/d3-cloud](https://deepwiki.com/jasondavies/d3-cloud) — HIGH confidence
- Jason Davies word cloud description (canonical): [How the Word Cloud Generator Works](https://www.jasondavies.com/wordcloud/about/) — HIGH confidence (canonical source, 404 on direct fetch but algorithm is well-known)
- SDF/EDT algorithm: [mapbox/tiny-sdf DeepWiki](https://deepwiki.com/mapbox/tiny-sdf) — HIGH confidence (Felzenszwalb/Huttenlocher is the standard algorithm)
- skia-canvas multi-threaded rendering: [skia-canvas npm](https://www.npmjs.com/package/skia-canvas), [GitHub samizdatco/skia-canvas](https://github.com/samizdatco/skia-canvas) — HIGH confidence
- BullMQ sandboxed processors: [BullMQ Docs: Sandboxed Processors](https://docs.bullmq.io/guide/workers/sandboxed-processors) — HIGH confidence
- BullMQ TypeScript: [Typescript with BullMQ sandboxes](https://blog.taskforce.sh/using-typescript-with-bullmq/) — MEDIUM confidence
- Async Request-Reply pattern: [Microsoft Azure Architecture](https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply) — HIGH confidence
- Fastify v5 schema validation: [Fastify Migration Guide V5](https://fastify.dev/docs/latest/Guides/Migration-Guide-V5/) — HIGH confidence
- Blueprint document: `raw/sources/AeroCloud-Blueprint.md` — project canonical source
- PROJECT.md decisions: `.planning/PROJECT.md` — project canonical source

---

*Architecture research: 2026-04-06*
