# Codebase Structure

**Analysis Date:** 2026-04-06

## Directory Layout

```
/var/www/wordcloud-app-v2/server/aerocloud-engine/
├── src/                    # Application source code (stub modules)
│   └── index.ts            # Main entry point with module exports
├── scripts/                # CLI tooling for wiki management
│   ├── ingest.ts           # Wiki ingestion: parse source → create wiki page
│   ├── query.ts            # Wiki search: keyword → synthesis context
│   └── lint-wiki.ts        # Wiki maintenance: validate structure
├── wiki/                   # LLM-maintained knowledge base (Karpathy pattern)
│   ├── index.md            # Central index: all pages with summaries
│   ├── log.md              # Append-only audit log of ingestions
│   ├── overview.md         # Architecture overview
│   ├── source-blueprint.md # Ingested AeroCloud Blueprint summary
│   ├── *-*.md              # Domain-specific pages (19 pages)
│   └── ...                 # Organized by: Math, Semantics, Geometry, Inner/Outer Loop, Post-Processing
├── raw/sources/            # Immutable source documents for wiki ingestion
│   └── AeroCloud-Blueprint.md # Master specification document
├── docs/                   # Governance and process documentation
│   ├── ai-team-decisions.md # 3-AI decision log (immutable audit trail)
│   └── review-checklist.md # Code review mandatory checklist (S-1 to S-8, L-1 to L-8, A-1 to A-5)
├── _bmad/                  # BMAD Method v6.2.2 framework (multi-AI agents)
│   ├── core/               # BMAD skills and agents (brainstorming, distillation, review)
│   └── ...                 # Complete BMAD workflow system
├── .claude/                # Claude Code configuration and state
│   ├── agents/             # Agent definitions for workspace
│   ├── commands/gsd/       # GSD (Get-Shit-Done) commands implementation
│   ├── settings.json       # Claude Code workspace settings
│   └── ...
├── .planning/              # Planning and analysis output directory
│   └── codebase/           # Codebase analysis documents (THIS LOCATION)
│       ├── ARCHITECTURE.md # Architecture patterns and layers
│       └── STRUCTURE.md    # This document
├── .vscode/                # Visual Studio Code workspace settings
├── .git/                   # Git repository (GitHub: aerocloud-engine)
├── .gitignore              # Standard Node.js/TypeScript ignores
├── .nvmrc                  # Node.js version (22 LTS)
├── .env                    # Environment variables (NEVER read/commit)
├── package.json            # NPM dependencies and scripts
├── package-lock.json       # Dependency lockfile
├── tsconfig.json           # TypeScript configuration
├── CLAUDE.md               # Project rules for Claude agents (MANDATORY READ)
├── AGENTS.md               # LLM agent instructions (wiki maintenance)
├── README.md               # Project introduction and development commands
├── mcp.json                # MCP server configuration (if applicable)
└── node_modules/           # Installed dependencies (git-ignored)
```

## Directory Purposes

**`src/`:**
- Purpose: Application source code (currently stubs)
- Contains: Module implementations for NLP, Geometry, Renderer, Optimizer, Export
- Key files: `index.ts` (entry point)
- Status: Stub phase - modules declared but not implemented

**`scripts/`:**
- Purpose: CLI tooling for wiki ingestion, querying, and maintenance
- Contains: TypeScript scripts for knowledge base operations
- Key files: `ingest.ts` (source parsing), `query.ts` (keyword search), `lint-wiki.ts` (validation)
- Pattern: All use `import.meta.dirname` for path resolution (ESM-native)

**`wiki/`:**
- Purpose: LLM-maintained knowledge base following Karpathy pattern
- Contains: 19 markdown pages organized by domain sections
- Key files: `index.md` (central index), `log.md` (ingest audit trail), `overview.md` (architecture summary)
- Sections: Overview, Math Foundations, Semantics, Geometry, Inner Loop, Outer Loop, Post-Processing, Metrics, Sources
- Pattern: YAML frontmatter on all pages (title, slug, source, created, section, summary, cross_refs)

**`raw/sources/`:**
- Purpose: Immutable master source documents for wiki ingestion
- Contains: AeroCloud-Blueprint.md (6.5 KB specification)
- Pattern: Never modified after commit; only source of truth for new wiki pages
- Triggers: `npm run wiki:ingest` processes files here

**`docs/`:**
- Purpose: Governance, decisions, and quality processes
- Key files: `ai-team-decisions.md` (immutable 3-AI decision log), `review-checklist.md` (mandatory review gates)
- Pattern: Append-only (decisions), checklist-based (reviews)

**`_bmad/`:**
- Purpose: BMAD Method v6.2.2 multi-AI orchestration framework
- Contains: Skills (brainstorming, distillation, review), agents, prompts
- Pattern: Complete workflow system for collaborative AI work
- Status: Available but not activated for this project (yet)

**`.claude/`:**
- Purpose: Claude Code workspace configuration and GSD command infrastructure
- Contains: Agent definitions, GSD command implementations, workspace settings
- Pattern: Auto-generated and managed by Claude Code

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents (created by GSD-Map-Codebase command)
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md
- Pattern: Written by mapping agents, consumed by planning agents
- Location: Always `.planning/codebase/` with UPPERCASE filenames

## Key File Locations

**Entry Points:**
- `src/index.ts`: Main application entry point (exports 5 module stubs)
- `scripts/ingest.ts`: Wiki ingestion CLI entry point
- `scripts/query.ts`: Wiki query CLI entry point
- `scripts/lint-wiki.ts`: Wiki validation CLI entry point

**Configuration:**
- `package.json`: NPM scripts (dev, build, test, typecheck, wiki:ingest, wiki:query, wiki:lint)
- `tsconfig.json`: TypeScript strict mode, ES2022 target, ESNext modules (ESM)
- `.nvmrc`: Node.js 22 LTS
- `mcp.json`: MCP server configuration (model context protocol)

**Core Logic:**
- `src/nlp/` (to be implemented): TF-IDF-AP, BERT embeddings, Optimal Transport
- `src/geometry/` (to be implemented): SDF, MAT, Quadtree, Collision detection
- `src/renderer/` (to be implemented): Differentiable rendering, Adam optimizer integration
- `src/optimizer/` (to be implemented): MAP-Elites, CQD metrics, BOP-Elites variant
- `src/export/` (to be implemented): Seam carving, Bezier export, SVG/PDF generation

**Testing:**
- No test files present yet (test infrastructure ready: `vitest` configured in package.json)
- Test commands: `npm run test` (run), `npm run test:watch` (watch mode)

**Knowledge Base:**
- `wiki/index.md`: Central catalog of all wiki pages (read first by queries)
- `wiki/log.md`: Append-only audit log of ingestion operations
- `wiki/overview.md`: Architecture overview with dual-loop paradigm
- `wiki/*-*.md`: 17 domain-specific pages (see index.md for full list)

**Governance:**
- `docs/ai-team-decisions.md`: Immutable decision log (3-AI consensus required to revise)
- `docs/review-checklist.md`: Mandatory review gates (21 items: S-1–S-8, L-1–L-8, A-1–A-5)

## Naming Conventions

**Files:**
- **Source files:** `camelCase.ts` (e.g., `ingest.ts`, `index.ts`)
- **Wiki pages:** `kebab-case.md` (e.g., `sdf-geometry.md`, `map-elites.md`)
- **Directories:** `lowercase` no dashes (e.g., `src/nlp`, `scripts`, `wiki`)
- **Configuration:** UPPERCASE or dotfiles (e.g., `CLAUDE.md`, `.env`, `tsconfig.json`)

**Directories:**
- **Source modules:** `src/<domain>/` where domain ∈ {nlp, geometry, renderer, optimizer, export}
- **Scripts:** `scripts/<purpose>.ts` (e.g., `scripts/ingest.ts`)
- **Wiki structure:** `wiki/<section>/<slug>.md` organized by YAML `section` field
- **Documentation:** `docs/<process>/<detail>.md` (e.g., `docs/ai-team-decisions.md`)

**Variables and Functions:**
- Standard camelCase for functions, constants, variables
- TypeScript strict mode enforced (no implicit any)
- Modules export named exports, no default exports (following ESM convention)

## Where to Add New Code

**New Feature Implementation:**
- Primary code: Implement in appropriate `src/<domain>/` directory
- Tests: Create `src/<domain>/<feature>.test.ts` (Vitest)
- Wiki: If implementation introduces new knowledge, ingest source to wiki or create summary page
- Decision log: If architectural choice needed, record in `docs/ai-team-decisions.md` after 3-AI consensus

**New Module/Package:**
- Create directory: `src/<new-domain>/`
- Add index file: `src/<new-domain>/index.ts` with named exports
- Add to main exports: Update `src/index.ts` to include new module
- Add tests: Create `src/<new-domain>/*.test.ts` files
- Add wiki doc: If domain-specific knowledge, create wiki page in appropriate section

**Wiki Contributions:**
- Source document: Add to `raw/sources/<topic>.md`
- Ingest: Run `npm run wiki:ingest raw/sources/<topic>.md`
- Cross-reference: Script auto-updates `wiki/index.md` and `wiki/log.md`
- Manual cleanup: Run `npm run wiki:lint` to detect broken links or inconsistencies

**Utilities and Shared Functions:**
- Location: No shared utilities folder yet (modules are independent)
- If needed: Create `src/shared/` for cross-cutting utilities
- Pattern: Export named functions, keep pure and testable

## Special Directories

**`wiki/` Directory:**
- Purpose: Karpathy LLM Wiki - self-maintaining knowledge base
- Generated: Partially (auto-generated frontmatter during `npm run wiki:ingest`)
- Committed: Yes (all .md files committed to Git)
- Structure: Flat (all pages at `wiki/*.md`), no subdirectories
- Index: `wiki/index.md` is the golden source for page discovery
- Log: `wiki/log.md` maintains append-only audit trail of all ingestions

**`raw/sources/` Directory:**
- Purpose: Immutable master sources for wiki ingestion
- Generated: No (user-created or imported)
- Committed: Yes
- Pattern: Master documents never modified after import; only read by `npm run wiki:ingest`

**`_bmad/` Directory:**
- Purpose: BMAD Method v6.2.2 framework (not currently active)
- Generated: Yes (generated during framework setup)
- Committed: Yes (full framework included for future use)
- Pattern: Can be activated when multi-AI orchestration needed (team_discuss, bmad-help, etc.)

**`.planning/codebase/` Directory:**
- Purpose: Codebase analysis documents (read by planning agents)
- Generated: Yes (written by GSD-Map-Codebase agent)
- Committed: Yes (part of planning state)
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md
- Pattern: Consumed by `/gsd-plan-phase` and `/gsd-execute-phase` commands

---

*Structure analysis: 2026-04-06*
