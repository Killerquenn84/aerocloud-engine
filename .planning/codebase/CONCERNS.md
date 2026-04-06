# Codebase Concerns

**Analysis Date:** 2026-04-06

## Project Phase & Implementation Status

**Current State:** Greenfield MVP Foundation (v0.1.0)

This is an early-stage research project establishing foundational tooling and knowledge infrastructure. The codebase currently contains:
- Wiki infrastructure (`scripts/ingest.ts`, `scripts/query.ts`, `scripts/lint-wiki.ts`)
- Module stubs in `src/index.ts` (no actual implementations)
- Documentation and BMAD methodology integration

**Critical Implication:** All concerns below must be addressed BEFORE any production implementation.

---

## Tech Debt

### Incomplete Module Implementations

**Area:** Core Engine Modules

**Issue:** All five engine modules are stubs only — `src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/exporter/` do not exist or contain only placeholder exports.

**Files:**
- `src/index.ts` - Contains only module descriptors, no functional code

**Impact:** 
- Cannot run any actual word cloud generation
- No integration between layers
- No test coverage for algorithms
- MVP is currently non-functional for the primary use case

**Fix Approach:**
1. Implement modules sequentially per CLAUDE.md spec: NLP → Geometry → Renderer → Optimizer → Export
2. Start with NLP module (TF-IDF-AP, tokenization) as foundation
3. Build geometric primitives (SDF, MAT, collision detection) before rendering
4. Add test harness before each implementation phase

---

### Missing Framework Integration

**Area:** Framework Setup

**Issue:** CLAUDE.md specifies Fastify v5 as mandatory for MVP production-hardening, but package.json has no Fastify dependency. No HTTP server exists.

**Files:**
- `package.json` - Missing: fastify, @fastify/* plugins, node-based HTTP stack

**Impact:**
- Cannot expose engine as API
- No request/response handling for webhook integrations
- Production deployment will require major refactoring to add web layer
- Health endpoints (/health, /health/internal) not implemented

**Fix Approach:**
1. Add Fastify v5 and required plugins to package.json
2. Create `src/api/` directory for HTTP route handlers
3. Implement health check endpoints before other routes
4. Setup middleware: JSON parsing with depth limits, body size limits, CORS disabled

---

### Test Infrastructure Missing

**Area:** Testing & Quality Assurance

**Issue:** No test files exist (`*.test.ts`, `*.spec.ts`) despite Vitest being in devDependencies and testing being mandatory per CLAUDE.md section 8.

**Files:**
- No test directory structure
- No test configuration in vitest.config.ts

**Current:** Running `npm run test` will find zero tests and succeed vacuously.

**Impact:**
- CLAUDE.md section 8 mandates 10 test strategies; zero are implemented
- Mutation testing (StrykerJS) requirement cannot be met
- No CI enforcement possible
- Risk: Code changes untested, especially in critical NLP/geometry modules
- DSGVO Canary Tests on user-input paths missing

**Fix Approach:**
1. Create `tests/` directory structure (unit/, integration/, e2e/)
2. Configure Vitest with coverage tracking and mutation test hooks
3. Write baseline BDD scenarios for each module BEFORE implementation
4. Enforce: Negative tests ≥ Happy-path tests
5. Document test coverage requirements per module in README

---

## Architectural Risks

### Dual-Loop Complexity Without Integration Plan

**Area:** Core Algorithm Architecture

**Issue:** Blueprint describes sophisticated Dual-Loop paradigm (Inner: PyTorch GPU differentiable rendering, Outer: MAP-Elites QD optimization), but no integration code exists. Boundary conditions between loops undefined.

**Files:**
- `raw/sources/AeroCloud-Blueprint.md` - Describes architecture
- `wiki/overview.md`, `wiki/map-elites.md`, `wiki/differentiable-rendering.md` - Knowledge pages exist but no code

**Current State:** Theoretical foundation only; synchronization protocol between loops not designed.

**Impact:**
- Hyperparameter handoff between loops unknown (e.g., how does MAP-Elites seed Inner Loop?)
- GPU/CPU sync not planned (PyTorch tensors ↔ numpy arrays ↔ WebAssembly?)
- Self-Play training schedule mentioned (nightly) but job system not designed
- Dead-letter/error handling during parallel optimization loops not addressed

**Fix Approach:**
1. Define formal API contract between layers in `docs/api-contract.md` (per CLAUDE.md workflow)
2. Design message/queue schema for loop communication
3. Specify convergence criteria and escape conditions for Inner Loop
4. Plan monitoring/observability for long-running MAP-Elites iterations
5. Document GPU resource allocation strategy (CUDA memory limits, batch sizes)

---

### Missing NLP Pipeline Foundation

**Area:** Natural Language Processing

**Issue:** `package.json` lists `natural` and `compromise` but no actual NLP module. TF-IDF-AP, tokenization, lemmatization not implemented. BERT embeddings noted as "later" (spaeter).

**Files:**
- `src/nlp/` does not exist
- No integration with `natural` or `compromise` libraries
- Blueprint section on TF-IDF-AP and Zipf normalization not implemented

**Impact:**
- Cannot parse input text or compute word weights
- No font size scaling based on TF-IDF scores
- Semantic coherence (MAP-Elites dimension) cannot be computed
- P_weight position scoring (+12.9% precision improvement) unknown implementation

**Fix Approach:**
1. Create `src/nlp/tokenizer.ts` - Integrate `natural.Tokenizer` and `compromise`
2. Implement Zipf normalization per CLAUDE.md: Logarithmic scaling (linear/sqrt are wrong)
3. Build TF-IDF-AP scorer with P_weight multiplier for HTML position hints
4. Add test cases for Zipf distribution edge cases (single word, uniform distribution)
5. Plan BERT integration point (async pipeline, batch processing)

---

## Dependencies at Risk

### Python/PyTorch Dependency Gap

**Risk:** Blueprint mandates PyTorch/CUDA GPU worker for Inner Loop differentiable rendering, but package.json is Node.js only. No Python environment specified.

**Files:**
- `package.json` - Node.js 22 only, no Python toolchain
- CLAUDE.md tech-stack mentions "Rendering: Canvas API (spaeter: PyTorch/CUDA)"

**Current:** Browser Canvas API only; GPU acceleration deferred.

**Impact:**
- Cannot meet performance SLA for coarse-to-fine optimization (8px → 32px → 128px)
- Async job queue (BullMQ + Redis) waiting for GPU worker definition
- No convergence for large text collections (>500 words)
- Architecture decision: "Later" PyTorch adds risk of mid-project redesign

**Fix Approach:**
1. Define Python worker entrypoint and async RPC protocol (Celery/FastAPI or gRPC)
2. Create `worker/` directory with Python environment spec (pyproject.toml, Python 3.11+)
3. Specify CUDA 12.x version pinning in docs
4. Implement fallback: CPU-only mode for development/testing
5. Document GPU memory requirements per batch size

---

### Fastify v5 as Launch-Blocking Dependency

**Risk:** CLAUDE.md section 12 marks "Fastify v5 Pflicht (Launch-Blocker)" but it is not in package.json. Hard deadline without current implementation.

**Files:**
- `package.json` - Missing fastify dependency

**Impact:**
- Cannot launch production MVP without major refactoring
- No HTTP/REST layer for integration with n8n, Shopify, or external clients
- Pre-MVP Checklist (85 items in 5 gates) cannot pass Security/Runtime gates

**Fix Approach:**
1. Add `fastify@^5.0.0` to dependencies immediately
2. Create `src/server.ts` with minimal Fastify app
3. Configure mandatory settings per CLAUDE.md:
   - JSON depth limit (default: 32 nesting)
   - bodyLimit (default: 1MB)
   - additionalProperties: false on all schema validators
4. Implement graceful shutdown handler for SIGTERM

---

## Security Gaps

### Input Validation Not Defined

**Area:** User Input Handling

**Issue:** No validation schemas exist for text input, silhouette geometry, or configuration parameters. CLAUDE.md mandates security checks (S-1 to S-8) but no validators implemented.

**Files:**
- No `src/security/` directory
- No input schema definitions
- No svg-sanitization code (mentioned in parent CLAUDE.md but not here)

**Current:** Raw user input would flow directly into NLP pipeline.

**Impact:**
- **Path Traversal (S-7):** If file-based silhouettes allowed, unvalidated paths could escape directory
- **DoS (S-8):** No limits on text length, silhouette complexity, or geometric dimensions
- **Injection (S-1):** If silhouette format is SVG/XML, no sanitization
- **DSGVO (GDPR):** Canary tests for user-input paths not implemented

**Fix Approach:**
1. Create `src/security/validators.ts` with schema definitions (Zod or Ajv)
2. Define limits: Max text length (10,000 chars?), max word count (1,000?), max geometry vertices
3. Implement SVG sanitizer for silhouettes (DOMPurify model from parent app)
4. Add rate limiting per IP if exposed as HTTP API
5. Create DSGVO canary test for each user-input endpoint

---

### Secrets & Environment Configuration

**Risk:** `.env` file is present but not in `.gitignore`. Potential for credential leakage.

**Files:**
- `.env` exists (contents forbidden by task rules, but file is tracked)
- `.gitignore` minimal

**Impact:**
- If secrets committed (API keys, n8n webhook URL, database creds), cannot be revoked
- CI/CD may pick up dev secrets as defaults

**Fix Approach:**
1. Verify `.env` in `.gitignore` and all `.env.*` patterns
2. Create `.env.example` with placeholder variables
3. Document required env vars in README (AI_TEAM_DECISIONS.md mentions none currently)
4. Use environment validation at startup (throw on missing REQUIRED vars)

---

## Performance & Scaling Concerns

### Unbounded Geometry Complexity

**Area:** Spatial Data Structures

**Issue:** Collision detection uses 5-level hierarchy (AABB → Two-Level Box → Quadtree → SAT → Bitmap), but no cost model or early termination criteria defined.

**Files:**
- `wiki/collision-detection.md` - Describes hierarchy but no implementation
- No Quadtree bounds or max-depth limits

**Current:** Blueprint mentions O(n log n) for Quadtree, O(n*m/32) for bitmap, but no constants or thresholds.

**Impact:**
- Pathological input (1000 long thin words) could trigger quadtree depth explosion
- SAT algorithm O(n*k) uncontrolled if SAT attempted on all polygon pairs
- Bitmap approach O(n*m/32) relies on image memory proportional to silhouette area
- No timeout mechanism for expensive collision checks

**Fix Approach:**
1. Add limits to geometry module: `MAX_VERTICES_PER_POLYGON`, `MAX_POLYGONS`, `MAX_BITMAP_AREA`
2. Implement quadtree max-depth parameter (default: 16)
3. Early exit SAT if AABB already separated
4. Profile collision detection on 500+ word inputs; document performance curve
5. Add timeout wrapper: if collision check >500ms, fail the candidate

---

### GPU Memory Pressure Unknown

**Area:** Inner Loop Rendering

**Issue:** No GPU memory budget defined. PyTorch batching strategy not specified. Self-play training "nightly" but resource requirements unknown.

**Files:**
- `wiki/differentiable-rendering.md` - Describes algorithm, not resource constraints
- CLAUDE.md mentions PM2 as process manager but no GPU monitoring tool

**Impact:**
- PyTorch tensors for position, scale, rotation not pooled or pre-allocated
- Coarse-to-fine (8px → 32px → 128px) may allocate O(resolution²) memory per level
- MAP-Elites archive could grow unbounded (no eviction policy mentioned)
- Self-play training runaway could exhaust VRAM, crash server

**Fix Approach:**
1. Define GPU memory budget: Reserve X% for other processes
2. Implement tensor pooling/caching in renderer
3. Cap MAP-Elites archive size (e.g., max 10,000 solutions)
4. Add CUDA out-of-memory handler: graceful fallback to CPU
5. Monitor GPU memory in health endpoint `/health/internal`

---

## Test Coverage Gaps

### No Unit Tests for Wiki Scripts

**Area:** Wiki Infrastructure

**Issue:** `scripts/ingest.ts`, `scripts/query.ts`, `scripts/lint-wiki.ts` (697 lines total) have zero test coverage. These are critical for knowledge base integrity.

**Files:**
- `scripts/ingest.ts` (183 lines) - Section detection, frontmatter generation
- `scripts/query.ts` (203 lines) - Index parsing, keyword matching
- `scripts/lint-wiki.ts` (271 lines) - Frontmatter validation, link checking
- No test files in `tests/`

**Impact:**
- Ingest could create broken wiki pages (missing fields, bad links)
- Query algorithm weaknesses unknown (e.g., symlink handling)
- Lint-wiki errors could prevent valid pages from indexing
- AI team relying on untested knowledge base

**Fix Approach:**
1. Create `tests/wiki.test.ts` with fixtures in `tests/fixtures/wiki/`
2. Test `ingest.ts`: Valid/invalid YAML, section detection, relative paths
3. Test `query.ts`: Keyword matching edge cases, non-existent files, empty results
4. Test `lint-wiki.ts`: Orphaned pages, circular references, frontmatter errors
5. Setup GitHub Actions CI to run tests on push

---

### Missing Negative Test Cases

**Area:** General Testing Strategy

**Issue:** CLAUDE.md section 8 mandates "Negative/Boundary Tests (mindestens so viele wie Happy-Path)", but zero test files exist.

**Impact:**
- No edge case validation (empty input, max-length input, null values)
- NLP module will not be bulletproof before first deployment
- Mutation testing (StrykerJS, score < 50% blocks merge) cannot be satisfied

**Examples Needed:**
- NLP: Single-word input, input with only stopwords, non-ASCII characters
- Geometry: Zero-area polygons, self-intersecting paths, concave shapes
- Renderer: Empty word list, single word at extreme scale, rotation edge cases
- Optimizer: Single candidate (no evolution), flat fitness landscape

**Fix Approach:**
1. Establish test template: For every module feature, write ≥1 negative test
2. Use property-based testing (`fast-check`) for randomized stress tests
3. Document negative test cases in TESTING.md (to be created)

---

## Operational Concerns

### No Logging or Observability

**Area:** Monitoring

**Issue:** CLAUDE.md review checklist (L-8) requires "sufficient logging context", but no logger configured. No structured logging library (`pino`, `winston`, `bunyan`).

**Files:**
- `src/index.ts` uses console.log only
- No log aggregation strategy

**Impact:**
- Self-play training "nightly" runs with no visibility
- PyTorch GPU errors will appear in stderr only
- Cannot diagnose why candidates fail collision checks
- Pre-MVP Checklist Gate 2 (Runtime) cannot pass

**Fix Approach:**
1. Add logging library (recommend `pino` for JSON output)
2. Inject logger into all module constructors
3. Log at levels: DEBUG (optimizer iterations), INFO (job completion), ERROR (failures)
4. Configure log format: Include timestamp, module name, request ID (if HTTP)
5. Document observability in ARCHITECTURE.md (to be created)

---

### Graceful Shutdown Not Implemented

**Area:** Process Management

**Issue:** CLAUDE.md section 12 mandates "Graceful Shutdown (SIGTERM → drain → exit)" but no signal handlers exist.

**Files:**
- `src/index.ts` - No SIGTERM listener
- No BullMQ worker cleanup
- No database connection draining

**Impact:**
- Hard shutdown kills running optimizations mid-iteration
- Incomplete transactions in queue
- MAP-Elites archive may be corrupted if not flushed
- PM2 restart will lose in-flight jobs

**Fix Approach:**
1. Add SIGTERM handler in server.ts: Close HTTP server, drain BullMQ, exit
2. Implement queue.close() with timeout (default: 30 seconds)
3. Log graceful shutdown start/end
4. Test with: `kill -TERM <pid>`

---

## Architecture Fragility

### Wiki Knowledge Base Coupling

**Area:** Knowledge System Design

**Issue:** `wiki/` is central to team decisions (CLAUDE.md section 11: "Vor jeder Arbeit: wiki/index.md lesen"), but no versioning, backup, or recovery mechanism.

**Files:**
- `wiki/` directory (19 markdown files)
- No backup strategy
- No version control annotations in frontmatter
- No audit log

**Impact:**
- If wiki corrupted, team loses architectural context
- Manual edits could break ingest/query scripts
- No way to revert to previous wiki state
- Lint-wiki catches errors but cannot auto-repair

**Fix Approach:**
1. Add git tags/branches for wiki snapshots: `wiki/stable`, `wiki/latest`
2. Implement `wiki:backup` script to export to tarball
3. Add `modified_by`, `modified_at` fields to frontmatter
4. Create `wiki/AUDIT.md` log of all ingest operations
5. Monthly archival to `docs/wiki-archive/`

---

### Module Dependencies Not Specified

**Area:** Dependency Injection / Module Boundaries

**Issue:** `src/index.ts` exports modules as static objects. No dependency graph, no initialization order specified.

**Files:**
- `src/index.ts` - Modules are singletons, no factory pattern

**Impact:**
- Cannot mock modules for testing
- Circular dependencies will cause subtle failures
- Module initialization order assumptions not documented
- Difficult to parallelize module startup

**Fix Approach:**
1. Define module initialization DAG in `docs/MODULE_INIT.md`
2. Implement factory functions instead of static objects
3. Use dependency injection (tsyringe or manual container) for testing
4. Document initialization guarantees: "NLP ready before Optimizer"

---

## Definition of Done Gaps

Per CLAUDE.md section 14, these are BLOCKING for any feature:

- ✗ **BDD Acceptance Criteria (Gherkin):** Not present in codebase; no Given/When/Then scenarios
- ✗ **Unit + Integration Tests:** Zero tests exist
- ✗ **pnpm turbo typecheck:** Not configured; `pnpm turbo` not set up (no monorepo structure yet)
- ✗ **pnpm turbo lint:** No ESLint config
- ✗ **Observability:** No logging infrastructure
- ✗ **Security Checks:** Input validators, SSRF/Path Traversal guards missing
- ✗ **SESSION_LOG.md updates:** No session log file exists

**Fix Approach:**
1. Create `SESSION_LOG.md` template in project root
2. Setup ESLint config (`.eslintrc.json`) with strict rules
3. Configure turbo.json monorepo settings (even if single package for now)
4. Create `docs/WORKING_GUIDE.md` explaining Definition of Done process
5. Add pre-commit hook via husky to enforce BDD scenarios + tests

---

## Summary: Risk Priority

| Concern | Severity | Blocker | Fix Effort |
|---------|----------|---------|-----------|
| No implementations (all modules stub) | **CRITICAL** | YES | **High** |
| Missing Fastify (production blocker) | **CRITICAL** | YES | **Medium** |
| Zero test coverage | **HIGH** | YES | **High** |
| No logging/observability | **HIGH** | YES | **Medium** |
| GPU/PyTorch integration gap | **HIGH** | NO | **Very High** |
| Input validation missing | **HIGH** | YES | **Medium** |
| NLP pipeline undefined | **HIGH** | YES | **Very High** |
| Graceful shutdown missing | **MEDIUM** | NO | **Low** |
| Wiki versioning missing | **MEDIUM** | NO | **Low** |
| Collision detection limits | **MEDIUM** | NO | **Medium** |

**Recommendation:** Address CRITICAL blockers before any implementation PR. Schedule GPU integration discussion with team (requires 3-KI consensus per CLAUDE.md section 4).

---

*Concerns audit: 2026-04-06*
