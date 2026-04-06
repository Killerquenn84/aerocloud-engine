# Coding Conventions

**Analysis Date:** 2026-04-06

## Language & Codebase Rules

**Primary Language:**
- All code written in **English only** (code, comments, variable names, commits, tests)
- German used only for Telegram communication and documentation summaries
- Reference: `CLAUDE.md` section 10 — Sprach-Regeln

**Module System:**
- ESM only (`import`/`export`)
- No CommonJS (`require()`)
- Type: "module" in `package.json` enforced

## Naming Patterns

**Files:**
- camelCase for utility/service files: `ingest.ts`, `query.ts`, `lint-wiki.ts`
- PascalCase for class/interface files (future): `LintIssue`, `IndexEntry`
- kebab-case for scripts/tooling directories: `lint-wiki.ts` (example in `scripts/`)
- Pattern: Domain-specific organization preferred (`src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/export/`)

**Functions:**
- camelCase for all functions and methods
- Verb-first naming pattern observed:
  - `extractTitle()`, `extractSummary()` — data extraction
  - `detectSection()`, `scoreEntry()` — data analysis
  - `collectMarkdownFiles()`, `parseIndex()` — parsing/collection
  - `checkFrontmatter()` — validation
- Descriptive compound names preferred over abbreviations

**Variables:**
- camelCase for local variables and parameters
- UPPER_SNAKE_CASE for constants (rarely used, see `ROOT`, `WIKI_DIR` in scripts)
- Avoid single-letter variables except in loops: `for (const file of files)`
- Descriptive names reflecting purpose: `sectionKeywords`, `linkPattern`, `fileScore`

**Types & Interfaces:**
- PascalCase for all type/interface names: `IndexEntry`, `LintIssue`
- Single responsibility per interface
- Example from `scripts/query.ts`:
  ```typescript
  interface IndexEntry {
    filename: string;
    title: string;
    summary: string;
  }

  interface LintIssue {
    file: string;
    severity: "error" | "warning";
    message: string;
  }
  ```

**Constants:**
- Directory paths: UPPER_SNAKE_CASE (`ROOT`, `WIKI_DIR`, `INDEX_PATH`)
- Configuration values: UPPER_SNAKE_CASE
- String literals for section names: `"Mathematische Grundlagen"` (quoted, specific)

## Code Style

**Formatting:**
- No explicit formatter config found (eslint/prettier files absent)
- Inferred style from codebase:
  - 2-space indentation (consistent in all TypeScript files)
  - 80-120 character line length target (observed in `lint-wiki.ts`)
  - Blank lines between logical sections (functions separated by single blank line)
  - Consistent spacing around operators and function parameters

**Linting:**
- TypeScript strict mode enforced via `tsconfig.json`:
  ```json
  "strict": true,
  "forceConsistentCasingInFileNames": true
  ```
- Run validation: `npm run typecheck`
- No ESLint config found — TypeScript `strict` mode is primary static analysis

**Type Safety:**
- TypeScript strict mode mandatory
- Explicit return types on all functions required (not inferred)
- Example from `scripts/query.ts`:
  ```typescript
  function scoreEntry(entry: IndexEntry, keywords: string[]): number
  function extractInternalLinks(content: string): string[]
  ```

## Import Organization

**Order:**
1. Node.js builtins first (`import { readFile } from "node:fs/promises"`)
2. Third-party packages (`import { marked } from "marked"` — future)
3. Local modules/relative imports (none in current code)
4. Type imports last (not yet used, but place before runtime imports conceptually)

**Path Aliases:**
- None currently configured
- Future pattern: Consider `@src/*` for monorepo integration with parent `wordcloud-app-v2`
- Current approach: Relative paths with `path.resolve(import.meta.dirname, "..")`

**Example from `scripts/ingest.ts`:**
```typescript
import { readFile, writeFile, appendFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
```

## Error Handling

**Pattern:**
- Early exit via `process.exit()` for CLI errors
- Descriptive `console.error()` before exit
- Example:
  ```typescript
  if (!existsSync(absSource)) {
    console.error(`Error: Source file not found: ${absSource}`);
    process.exit(1);
  }
  ```

**Validation:**
- Input validation at function entry points
- Guard clauses preferred over nested conditionals
- No try/catch in scripts (errors cause exit, not recovery)

**Future (when integrated with API):**
- Throw typed errors with context
- Per `CLAUDE.md` section 7: Anti-sycophancy protocol requires L-1 to L-8 stability checks
- L-1: All errors must be caught and handled gracefully
- L-8: Errors logged with sufficient context

## Logging

**Current Approach:**
- `console.log()` for info/status messages
- `console.error()` for errors and validation failures
- No logging framework configured (future: consider structured logging for API)

**Patterns Observed:**
- Status messages after successful operations:
  ```typescript
  console.log(`Created wiki page: wiki/${wikiFilename}`);
  console.log(`Updated wiki/index.md (section: ${section})`);
  ```
- Progress indicators with separators (repeat "=" for clarity):
  ```typescript
  console.log(`${"=".repeat(60)}`);
  console.log("RESULTS");
  console.log(`${"=".repeat(60)}`);
  ```

**Future Guidelines (from CLAUDE.md):**
- All logging must be observable/traceable
- Log errors with full context (file, line, operation)
- No sensitive data in logs (API keys, secrets)

## Comments

**JSDoc/TypeDoc:**
- Required on all exported functions
- Single-line block comment format (/** ... */)
- Describe: what the function does, parameters (if non-obvious), return value
- Example from `scripts/ingest.ts`:
  ```typescript
  /**
   * Extract a one-line summary from the first meaningful paragraph of the source.
   */
  function extractSummary(content: string): string
  ```

**Inline Comments:**
- Minimal — prefer self-documenting code
- Used only for non-obvious logic or workarounds
- Examples:
  ```typescript
  // Skip headings, find the first paragraph-like line
  if (trimmed.startsWith("#") || trimmed.startsWith("---")) {
    continue;
  }

  // Boost exact title matches
  score += 2;
  ```

**Section Comments:**
- Markdown-style comment separators for logical sections:
  ```typescript
  // --- CLI entry point ---
  const args = process.argv.slice(2);
  ```

## Function Design

**Size:**
- Prefer 20-50 lines per function (observed in scripts)
- Break complex logic into helper functions
- Example: `extractTitle()`, `extractSummary()`, `detectSection()` are separate functions called by `ingest()`

**Parameters:**
- Single responsibility per parameter
- Avoid option objects for simple cases (use positional parameters)
- Use interfaces for complex parameter sets (future)
- Example:
  ```typescript
  function scoreEntry(entry: IndexEntry, keywords: string[]): number
  ```

**Return Values:**
- Always explicit return type annotation
- Return void if no return value
- Return consistent types (don't mix null/undefined/false for "no result")
- Example from `lint-wiki.ts`:
  ```typescript
  function checkFrontmatter(content: string, filename: string): LintIssue[]
  // Returns array, empty array if no issues (not null/undefined)
  ```

## Module Design

**Exports:**
- Named exports preferred (not default export)
- Current code has no explicit exports (scripts are CLI, not modules)
- Future pattern for engine modules (`src/nlp/`, `src/geometry/`, etc.):
  - Export main class/function as default or named
  - Export helper types/interfaces as named
  - Example structure:
    ```typescript
    export interface TFIDFResult { /* ... */ }
    export function extractKeywords(text: string): TFIDFResult { /* ... */ }
    ```

**Barrel Files:**
- Not currently used
- Consider for `src/index.ts` pattern when multiple modules exist
- Future guideline: Use barrel files for public API aggregation

## Code Organization Patterns

**Script Structure (from `scripts/` analysis):**
1. JSDoc block comment describing script purpose
2. Imports (Node.js builtins, then third-party)
3. Constants and paths
4. Helper function definitions (in call order)
5. Main async function definition
6. CLI entry point (args parsing + invocation)

**Example flow from `ingest.ts`:**
```typescript
// 1. Comment block
/**
 * Wiki Ingest Script
 * ...
 */

// 2. Imports
import { readFile, writeFile } from "node:fs/promises";

// 3. Constants
const ROOT = path.resolve(import.meta.dirname, "..");
const WIKI_DIR = path.join(ROOT, "wiki");

// 4. Helpers
function slugify(name: string): string { /* ... */ }
function timestamp(): string { /* ... */ }
function extractSummary(content: string): string { /* ... */ }

// 5. Main function
async function ingest(sourcePath: string): Promise<void> { /* ... */ }

// 6. CLI entry
const args = process.argv.slice(2);
if (args.length === 0) { /* error */ }
await ingest(args[0]);
```

## Quality Gates (from CLAUDE.md)

**Before any commit (mandatory):**
1. `npm run typecheck` → 0 errors (TypeScript strict mode)
2. `npm run lint` → 0 errors (future, when ESLint added)
3. `npm test` → All tests pass (Vitest)
4. Code review via 3-AI team (Claude, Gemini, ChatGPT)
5. Anti-sycophancy protocol applied (S-1 to S-8, L-1 to L-8, A-1 to A-5 checks)

**Security constraints (from CLAUDE.md section 13):**
- S-5: Secrets must be in env vars, never in code
- S-6: All outbound requests must be validated
- S-7: All file paths must be sanitized (use `path.resolve()`, `path.join()`)

**Breaking Change Constraints:**
- A-5: Backwards compatibility required — breaking changes must be documented
- When modifying interfaces/exports, update `ai-team-decisions.md` with rationale

---

*Convention analysis: 2026-04-06*
