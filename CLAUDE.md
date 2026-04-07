# CLAUDE.md — AeroCloud Engine Regelwerk

> Diese Datei wird von Claude Code bei jedem Start automatisch geladen.
> Alle Regeln sind VERBINDLICH. Keine Ausnahmen.
> **Repo**: https://github.com/Killerquenn84/aerocloud-engine
> **Server**: /var/www/wordcloud-app-v2/server/aerocloud-engine
> **Telegram Chat-ID Jens**: 5697986530
> **Bot**: @AeroSuperEngineBot

---

## 1. ABSOLUTE PFLICHT: DISKUSSION VOR CODE

**Hoechste Prioritaet. Keine Ausnahme.**

- Wenn Jens eine Nachricht/Idee/Fix/Code/Snippet schickt → SOFORT `team_discuss` starten
- Alle 3 KIs (Claude, Gemini, ChatGPT) analysieren unabhaengig
- Diskussion bis **echter Konsens** — kein Rundenlimit, `max_rounds: 99`
- Erst nach Konsens Code schreiben
- Nach dem Code nochmal `team_discuss` Review
- Erst nach Review-Konsens committen

**VERBOTEN:** "Ich starte die Implementierung" bevor diskutiert wurde

---

## 2. AUTONOMIE-REGELN

### Innerhalb des Projekts — volle Autonomie:
- Dateien lesen/erstellen/bearbeiten/loeschen
- Tests, Build, npm install, Git-Operationen
- Multi-AI Router Tools (`ask_all`, `compare`, `pipeline`, `team_discuss`, `peer_review`, `consult`)
- Keine Permission-Fragen (`--dangerously-skip-permissions`)

### Ausserhalb des Projekts — Bestaetigung erforderlich:
- SSH, git push/pull, GitHub API, externe Zugriffe
- Detailliert erklaeren: warum, welche Daten, welches Risiko
- Auf Bestaetigung warten

---

## 3. TELEGRAM-KOMMUNIKATION

```
JEDE Frage an Jens ueber Telegram senden (chat_id: 5697986530)
JEDE Statusmeldung ueber Telegram
NIEMALS im Terminal auf Input warten ohne per Telegram zu fragen
BMAD-Workflow Fragen (z.B. [C] Continue) per Telegram weiterleiten
Zwischenstatus bei >2 Minuten Arbeit
Keine lokalen Dateipfade als Links — Inhalt direkt senden oder GitHub-Link
Kompletten MD-Inhalt jeder geschriebenen Datei per Telegram senden
```

---

## 4. 3-KI TEAM-KOLLABORATION

**Prinzip: Team-Entscheidungen, keine Einzelleistung**

- Alle 3 KIs als gleichberechtigtes Team
- Eigene Recherche zuerst — jede KI recherchiert selbststaendig
- Alle 3 teilen Ansichten — auch Claude Code muss eigene Analyse einbringen
- Detaillierte Diskussion — Positionen mit Gruenden, Gegenargumente, Kompromisse
- Konsens dokumentieren in `docs/ai-team-decisions.md`
- Vor jeder Arbeit `ai-team-decisions.md` lesen
- Entscheidungen nur durch neue 3-KI-Diskussion revidierbar

---

## 5. ARBEITSWEISE PRO AUFGABE (Step fuer Step)

- Innerhalb eines Steps: Komplett autonom (keine Rueckfragen fuer Dateien)
- Nach jedem Step: Kompletter MD-Inhalt per Telegram + auf Jens' Bestaetigung warten
- Zwischen Steps: Nicht alle auf einmal, sondern Step fuer Step

### Pro Epic/Feature:
1. Advanced Elicitation (alle 50 Methoden)
2. Party Mode mit BMAD-Agenten (PM, Architect, Analyst, QA, UX)
3. `team_discuss` mit Claude + Gemini + ChatGPT (3-KI prueft BMAD-Ergebnisse)
4. Zurueck an Party Mode zur Finalisierung

---

## 6. CODE-REVIEW: 3-DAUMEN-PRINZIP

Keine Einzelbewertungen — echte Diskussion:

1. **Claude Code Self-Review** (kritisch, als waere er ein anderer Reviewer)
2. **Gemini Review** (Performance + Security)
3. **ChatGPT Review** (UX + Edge Cases)
4. Alle 3 diskutieren gemeinsam via `team_discuss`
5. Jeder muss auf Argumente der anderen eingehen
6. Bei Dissens: weiterdiskutieren bis Konsens oder Eskalation an Jens
7. **Alle 3 muessen APPROVED geben**

---

## 7. ANTI-SYCOPHANCY-PROTOKOLL

Bei jedem Review:

- Aktiv nach Schwachstellen suchen — nicht nur ob offensichtlich falsch
- "Das sieht gut aus" **verboten** ohne konkrete Begruendung
- Zustimmen erst nachdem Gegenfall aktiv gesucht wurde
- Sycophancy-Self-Check: "Stimme ich zu weil ich ueberzeugt bin — oder weil es einfacher ist?"

### Pflicht-Fragekatalog:
- **S-1 bis S-8:** Security Checks (Injection, XSS, CSRF, Auth, Secrets, SSRF, Path Traversal, DoS)
- **L-1 bis L-8:** Stability Checks (Error Handling, Resource Leaks, Race Conditions, Timeouts, Memory, Retry Logic, Graceful Degradation, Logging)
- **A-1 bis A-5:** Architecture Checks (SRP, DRY, Coupling, API Contract, Backwards Compatibility)

---

## 8. TEST-VORGABEN (BINDING Policy)

```
Tests sind Gesetze — werden NIEMALS an den Code angepasst
Kommissionsverfahren bei Testversagen (3 KIs + Jens einstimmig)
```

### 10 Teststrategien:
1. Static Analysis (TypeScript strict, ESLint)
2. Unit Tests (FIRST Principles — Fast, Isolated, Repeatable, Self-validating, Timely)
3. Negative/Boundary Tests (mindestens so viele wie Happy-Path)
4. Integration Tests
5. E2E Tests
6. Property-Based Tests (fast-check)
7. Mutation Tests (StrykerJS) — Score < 50% auf kritischen Modulen blockiert Merge
8. Security Tests (DSGVO + OWASP)
9. Performance Tests
10. Determinism Tests

### CI-Enforcement: 10 Stufen, 8 blockierend
### DSGVO Canary-Tests auf allen User-Input-Pfaden

---

## 9. BMAD-METHOD COMPLIANCE (v6.2.2)

- **Conventional Commits:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **PR Size:** 200-400 Zeilen ideal, max 800
- **Ein Feature/Fix pro PR**
- BMAD Skills nutzen: `bmad-help`, `bmad-create-architecture`, `bmad-code-review`, `bmad-dev-story`, `bmad-sprint-planning`
- 14-Tage Auto-Update: Server Cron + Remote Trigger prueft npm-Version
- `npm run validate:refs` vor jedem Commit fuer BMAD-Dateien

---

## 10. SPRACH-REGELN

| Kontext | Sprache |
|---|---|
| **Codebase** | Immer Englisch (Code, Kommentare, Commits, Tests, API, Docs) |
| **KI-Prompts** | Englisch an Gemini/ChatGPT |
| **Telegram an Jens** | Immer Deutsch |
| **ai-team-decisions.md** | Diskussionen Englisch, Zusammenfassung fuer Jens Deutsch |

---

## 11. KNOWLEDGE WIKI (Karpathy LLM Wiki Pattern)

- Vor jeder Arbeit: `wiki/index.md` lesen
- Wiki-Schema: Siehe `AGENTS.md`
- **Nightly Deep Research:** 2:00-5:00 AM Berlin — Internet durchsuchen, Wiki aktualisieren
- Wissen waechst exponentiell — kein Kontextverlust

### Drei Schichten:
```
raw/sources/    → Unveraenderliche Quelldokumente
wiki/           → LLM-generierte Markdown-Seiten
CLAUDE.md       → Schema (dieses Dokument)
```

### Wiki-Befehle:
```bash
npm run wiki:ingest raw/sources/neue-quelle.md
npm run wiki:query "suchbegriff"
npm run wiki:lint
```

---

## 12. MVP PRODUCTION-HARDENING

- Node.js CVE-Tracking (gepinnt in `.nvmrc`)
- Fastify v5 Pflicht (Launch-Blocker)
- JSON-Depth-Limit, bodyLimit, `additionalProperties: false`
- Health-Endpoints: `/health` (public), `/health/internal` (authentifiziert)
- CORS: Kein CORS (Server-to-Server only)
- Graceful Shutdown (SIGTERM → drain → exit)
- PM2 als alleiniger Process-Manager
- Core-Dumps deaktiviert (`ulimit -c 0`)
- Pre-MVP Checklist: 85 Items in 5 Gates (Security, Runtime, Load, Webhook, DSGVO)

---

## 13. REGELN GEGEN RUECKSCHRITTE

```
Vor Code-Aenderungen: Immer ai-team-decisions.md lesen
Bei Widerspruechen: Neue Diskussion statt stillschweigend ueberschreiben
Keine Solo-Entscheidungen bei Architektur/Design
Recherche-Pflicht: Eigene Analyse, nicht nur anderen zustimmen
```

---

## Engine-Module

```
src/nlp/         → TF-IDF-AP, Tokenisierung, BERT-Embeddings
src/geometry/    → SDF, MAT, Quadtree, Kollisionserkennung
src/renderer/    → Differentiable Rendering, Soft-Rasterization
src/optimizer/   → Adam, CQD-Metrik, MAP-Elites, BOP-Elites
src/export/      → Seam Carving, Bezier-Export, SVG/PDF
```

---

## Tech-Stack

```
Runtime:        Node.js 22 LTS, TypeScript 5.7+, ESM only
Framework:      Fastify v5
Test:           Vitest + StrykerJS + fast-check + Playwright
NLP:            natural, compromise (spaeter: sentence-transformers)
Rendering:      Canvas API (spaeter: PyTorch/CUDA)
Process:        PM2
Wiki-Tools:     tsx scripts (ingest, query, lint)
BMAD:           v6.2.2 (Core + BMM)
```

---

> **Goldene Regel:** Diskutieren → Konsens → Implementieren → Review → Konsens → Committen

<!-- GSD:project-start source:PROJECT.md -->
## Project

**AeroCloud Engine**

A self-learning word cloud rendering engine that places words precisely within arbitrary silhouettes using semantic hierarchy and geometric optimization. Built as a standalone Node.js/TypeScript module that powers the AeroCloud Shopify app's rendering pipeline.

**Core Value:** Precise silhouette filling with semantic word hierarchy — words are placed inside any shape with correct visual weight (Zipf-normalized sizing) and zero overlap, producing aesthetically high-quality word clouds.

### Constraints

- **Runtime**: Node.js 22 LTS, TypeScript 5.7+ ESM only — no Python, no Rust, no WASM
- **Framework**: Fastify v5 — no Express, no Hapi
- **Testing**: Vitest + StrykerJS — TDD/BDD mandatory per CLAUDE.md
- **Process**: PM2 as process manager on production server
- **Performance**: < 500ms for 200 words target rendering time
- **Security**: SVG sanitization required, no SSRF, path traversal protection
- **Integration**: Must expose HTTP API consumable by parent Shopify app's BullMQ workers
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript 5.7+ - All source code, ESM only (no CommonJS)
- Node.js JavaScript - Runtime for scripts and build tools
- Markdown - Documentation and wiki content
- YAML - Configuration and frontmatter in wiki system
## Runtime
- Node.js 22 LTS (see `.nvmrc`)
- npm 10+ (lockfile: `package-lock.json` present)
- Note: Project inherited npm, transitioning planned to pnpm per parent project standards
## Frameworks
- None (standalone engine) - Pure Node.js modules
- TypeScript Compiler (tsc) - Build and typecheck
- tsx - Script runner for TypeScript execution
- Vitest 3.0.0 - Test framework and runner
## Key Dependencies
- `natural` 8.0.1 - NLP library for tokenization, stemming, TF-IDF
- `compromise` 14.14.3 - Natural language processing library
- `marked` 15.0.0 - Markdown parser for wiki content processing
- `@types/node` 22.0.0 - TypeScript definitions for Node.js APIs
- `tsx` 4.21.0 - TypeScript execution engine for scripts
## Configuration
- `.env` file present (see `.gitignore` - not committed)
- Multi-AI integration via `mcp.json` with environment variables:
- `tsconfig.json` - TypeScript compilation configuration
- `mcp.json` - MCP (Model Context Protocol) server configuration
## Platform Requirements
- Node.js 22+
- TypeScript 5.7+
- Access to external AI APIs (Gemini, OpenAI, Perplexity, Alibaba DashScope)
- Optional: Telegram bot for notifications
- Node.js 22 LTS
- No external runtime dependencies (pure Node.js)
- Standalone CLI/module execution
## Scripts and Tooling
- `npm run wiki:ingest` - Process source documents into wiki format
- `npm run wiki:query` - Search and synthesize knowledge from wiki
- `npm run wiki:lint` - Health-check wiki structure
- `npm run dev` - Watch mode development with tsx
- `npm run build` - Compile TypeScript to dist/
- `npm test` - Run Vitest suite once
- `npm run test:watch` - Continuous test watching
- `npm run typecheck` - TypeScript validation without emit
## Architecture Notes
- **Module Structure:** Organized by domain (`src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/export/`)
- **Wiki System:** Implements Karpathy LLM Wiki pattern for self-evolving knowledge base
- **BMAD Integration:** Quality-diversity optimization using BMAD v6.2.2 methodology
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Language & Codebase Rules
- All code written in **English only** (code, comments, variable names, commits, tests)
- German used only for Telegram communication and documentation summaries
- Reference: `CLAUDE.md` section 10 — Sprach-Regeln
- ESM only (`import`/`export`)
- No CommonJS (`require()`)
- Type: "module" in `package.json` enforced
## Naming Patterns
- camelCase for utility/service files: `ingest.ts`, `query.ts`, `lint-wiki.ts`
- PascalCase for class/interface files (future): `LintIssue`, `IndexEntry`
- kebab-case for scripts/tooling directories: `lint-wiki.ts` (example in `scripts/`)
- Pattern: Domain-specific organization preferred (`src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/export/`)
- camelCase for all functions and methods
- Verb-first naming pattern observed:
- Descriptive compound names preferred over abbreviations
- camelCase for local variables and parameters
- UPPER_SNAKE_CASE for constants (rarely used, see `ROOT`, `WIKI_DIR` in scripts)
- Avoid single-letter variables except in loops: `for (const file of files)`
- Descriptive names reflecting purpose: `sectionKeywords`, `linkPattern`, `fileScore`
- PascalCase for all type/interface names: `IndexEntry`, `LintIssue`
- Single responsibility per interface
- Example from `scripts/query.ts`:
- Directory paths: UPPER_SNAKE_CASE (`ROOT`, `WIKI_DIR`, `INDEX_PATH`)
- Configuration values: UPPER_SNAKE_CASE
- String literals for section names: `"Mathematische Grundlagen"` (quoted, specific)
## Code Style
- No explicit formatter config found (eslint/prettier files absent)
- Inferred style from codebase:
- TypeScript strict mode enforced via `tsconfig.json`:
- Run validation: `npm run typecheck`
- No ESLint config found — TypeScript `strict` mode is primary static analysis
- TypeScript strict mode mandatory
- Explicit return types on all functions required (not inferred)
- Example from `scripts/query.ts`:
## Import Organization
- None currently configured
- Future pattern: Consider `@src/*` for monorepo integration with parent `wordcloud-app-v2`
- Current approach: Relative paths with `path.resolve(import.meta.dirname, "..")`
## Error Handling
- Early exit via `process.exit()` for CLI errors
- Descriptive `console.error()` before exit
- Example:
- Input validation at function entry points
- Guard clauses preferred over nested conditionals
- No try/catch in scripts (errors cause exit, not recovery)
- Throw typed errors with context
- Per `CLAUDE.md` section 7: Anti-sycophancy protocol requires L-1 to L-8 stability checks
- L-1: All errors must be caught and handled gracefully
- L-8: Errors logged with sufficient context
## Logging
- `console.log()` for info/status messages
- `console.error()` for errors and validation failures
- No logging framework configured (future: consider structured logging for API)
- Status messages after successful operations:
- Progress indicators with separators (repeat "=" for clarity):
- All logging must be observable/traceable
- Log errors with full context (file, line, operation)
- No sensitive data in logs (API keys, secrets)
## Comments
- Required on all exported functions
- Single-line block comment format (/** ... */)
- Describe: what the function does, parameters (if non-obvious), return value
- Example from `scripts/ingest.ts`:
- Minimal — prefer self-documenting code
- Used only for non-obvious logic or workarounds
- Examples:
- Markdown-style comment separators for logical sections:
## Function Design
- Prefer 20-50 lines per function (observed in scripts)
- Break complex logic into helper functions
- Example: `extractTitle()`, `extractSummary()`, `detectSection()` are separate functions called by `ingest()`
- Single responsibility per parameter
- Avoid option objects for simple cases (use positional parameters)
- Use interfaces for complex parameter sets (future)
- Example:
- Always explicit return type annotation
- Return void if no return value
- Return consistent types (don't mix null/undefined/false for "no result")
- Example from `lint-wiki.ts`:
## Module Design
- Named exports preferred (not default export)
- Current code has no explicit exports (scripts are CLI, not modules)
- Future pattern for engine modules (`src/nlp/`, `src/geometry/`, etc.):
- Not currently used
- Consider for `src/index.ts` pattern when multiple modules exist
- Future guideline: Use barrel files for public API aggregation
## Code Organization Patterns
## Quality Gates (from CLAUDE.md)
- S-5: Secrets must be in env vars, never in code
- S-6: All outbound requests must be validated
- S-7: All file paths must be sanitized (use `path.resolve()`, `path.join()`)
- A-5: Backwards compatibility required — breaking changes must be documented
- When modifying interfaces/exports, update `ai-team-decisions.md` with rationale
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Inner Loop (GPU Exploitation):** PyTorch-based differentiable rendering with Adam optimizer for layout refinement
- **Outer Loop (Quality-Diversity Exploration):** MAP-Elites algorithm with CQD metrics for multi-objective optimization
- **Knowledge Layer:** Karpathy LLM Wiki pattern for self-maintaining technical documentation and domain knowledge
- **Modular Pipeline:** Clear separation of 5 core domains: NLP, Geometry, Renderer, Optimizer, Export
## Layers
- Purpose: Text analysis and semantic understanding - TF-IDF scoring, BERT embeddings, Zipf law normalization
- Location: `src/nlp/` (to be implemented)
- Contains: Keyword extraction, semantic similarity scoring, optimal transport (Sinkhorn-Knopp)
- Depends on: External NLP libraries (natural, compromise, sentence-transformers)
- Used by: Geometry layer for semantic-aware placement
- Purpose: Shape analysis, collision detection, medial axis transformation
- Location: `src/geometry/` (to be implemented)
- Contains: SDF (Signed Distance Fields), Medial Axis Transform, Quadtree spatial indexing, collision hierarchies
- Depends on: NLP layer outputs, mathematical primitives
- Used by: Renderer and Optimizer for layout constraints
- Purpose: Differentiable soft-rasterization and layout rendering with per-word optimization
- Location: `src/renderer/` (to be implemented)
- Contains: Differentiable rendering pipeline, loss function computation, gradient propagation
- Depends on: Geometry layer for collision/constraint data, PyTorch for differentiable operations
- Used by: Optimizer's inner loop for layout refinement
- Purpose: Meta-optimization combining inner loop (Adam) and outer loop (MAP-Elites) strategies
- Location: `src/optimizer/` (to be implemented)
- Contains: Adam optimizer for fine-grained layout, MAP-Elites archive, CQD metrics, BOP-Elites variant
- Depends on: Renderer for fitness evaluation, NLP for behavior dimensions
- Used by: Main entry point for orchestration
- Purpose: Post-processing and vector export with quality preservation
- Location: `src/export/` (to be implemented)
- Contains: Seam carving for whitespace compression, Bezier curve math, SVG/PDF generation
- Depends on: Geometry layer for final shape data
- Used by: Final output generation
- Purpose: Karpathy LLM Wiki - maintains evolving domain knowledge
- Location: `wiki/` (LLM-maintained), `raw/sources/` (immutable sources)
- Contains: Markdown pages organized by domain (Math, Semantics, Geometry, Inner/Outer Loop, Post-Processing)
- Depends on: Wiki tooling scripts in `scripts/`
- Used by: All development phases for reference and context preservation
## Data Flow
- **Frozen reference_weights tensor:** Immutable after TF-IDF-AP normalization
- **MAP-Elites archive:** Persistent multi-objective solution set indexed by behavior dimensions
- **Per-layout parameters:** Word positions, scales, rotations maintained during optimization
- **Silhouette SDF:** Precomputed and cached for all iterations
## Key Abstractions
- Purpose: Multi-objective fitness evaluation beyond single-objective optimization
- Examples: `wiki/cqd-metric.md`, `wiki/quality-metrics.md`
- Pattern: Behavior descriptor space (continuous features) + fitness archive allowing diverse solutions
- Purpose: Efficient collision detection with increasing precision
- Examples: `wiki/collision-detection.md`
- Pattern: AABB → Two-Level Box → Quadtree → SAT → Pixel-Perfect (progressive refinement)
- Purpose: Enable gradient-based optimization of layout parameters
- Examples: `wiki/differentiable-rendering.md`
- Pattern: Soft-rasterization with differentiable loss, not hard pixel collision
- Purpose: Continuous shape representation enabling gradient-based geometry operations
- Examples: `wiki/sdf-geometry.md`
- Pattern: Distance function with sign indicating inside/outside, gradient points to boundary
- Purpose: Formalize the core computational problem
- Examples: `wiki/np-hard-packing.md`
- Pattern: NP-hard problem requiring heuristic solutions via quality-diversity exploration
## Entry Points
- Location: `src/index.ts`
- Triggers: CLI invocation via `npm run dev` or `npm run build`
- Responsibilities: Module exports and version logging; currently stubs for all 5 modules
- Location: `scripts/ingest.ts`
- Triggers: `npm run wiki:ingest raw/sources/<file>`
- Responsibilities: Parse source documents, auto-detect sections, create wiki pages with frontmatter, maintain index and log
- Location: `scripts/query.ts`
- Triggers: `npm run wiki:query "<keywords>"`
- Responsibilities: Search wiki index by keyword relevance, synthesize knowledge for LLM context
- Location: `scripts/lint-wiki.ts`
- Triggers: `npm run wiki:lint`
- Responsibilities: Detect orphaned pages, broken links, inconsistencies, suggest corrections
## Error Handling
- **Input Validation:** Text normalization with explicit character bounds; silhouette polygon validation
- **Geometry Assertions:** SDF validity checks, collision detection thresholds, boundary crossings
- **Optimizer Convergence:** Loss monitoring, NaN detection, fallback to previous best state
- **Post-Processing Safety:** Bezier smoothing with smoothness bounds, export format validation
- **Graceful Degradation:** If inner loop fails to converge, use best-so-far; if collision resolution fails, skip word; if export fails, provide PNG fallback
## Cross-Cutting Concerns
- Type validation via TypeScript strict mode
- Geometry constraints: All coordinates bounded to silhouette, no negative scales
- Numeric stability: NaN/Inf guards in optimizer, soft-clipping in renderer
- SDF computation parallelizable via GPU (deferred to PyTorch layer)
- Quadtree O(n log n) for n words
- Optimal Transport O(n²) but computed once during initialization
- Inner loop (~100 epochs × ~50 words) vectorized via PyTorch
- Outer loop (700 iterations) decoupled from inner loop, can run asynchronously
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
