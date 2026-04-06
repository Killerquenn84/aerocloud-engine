# Testing Patterns

**Analysis Date:** 2026-04-06

## Test Framework

**Runner:**
- Vitest 3.0.0
- Config: None explicitly configured (uses defaults)
- ESM-native (no CommonJS transpilation needed)

**Assertion Library:**
- Vitest built-in assertions (chai-based)
- Import: `import { expect, describe, it } from "vitest"`

**Run Commands:**
```bash
npm test              # Run all tests once (vitest run)
npm run test:watch    # Watch mode (vitest)
npm run typecheck     # TypeScript validation (tsc --noEmit)
```

## Test Framework Configuration

**Location:** No `vitest.config.ts` file exists yet

**Recommended Configuration** (to be created):
```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["src/**/*.test.ts", "scripts/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      all: true,
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
});
```

## Test File Organization

**Location Pattern:**
- Co-located with source files (preferred pattern)
- Test file naming: `[module].test.ts` or `[module].spec.ts`
- Future location structure:
  ```
  src/nlp/
    ├── tokenizer.ts
    ├── tokenizer.test.ts
    ├── tfidf.ts
    └── tfidf.test.ts
  scripts/
    ├── ingest.ts
    ├── ingest.test.ts
    ├── query.ts
    └── query.test.ts
  ```

**Naming Convention:**
- Suffix: `.test.ts` (primary)
- Alternative: `.spec.ts` (equivalent)
- Pattern: `${ModuleName}.test.ts` (e.g., `ingest.test.ts`)

## Test Structure

**Suite Organization Pattern** (recommended based on CLAUDE.md):

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";

describe("ingest()", () => {
  describe("valid source file", () => {
    it("should create wiki page with correct frontmatter", async () => {
      // Given: source file exists with valid markdown
      // When: ingest() is called
      // Then: wiki page created with YAML frontmatter
    });

    it("should update wiki/index.md with new entry", async () => {
      // Given: wiki/index.md exists
      // When: ingest() processes new source
      // Then: index updated in correct section
    });
  });

  describe("missing source file", () => {
    it("should exit with error code 1", async () => {
      // Given: source file does not exist
      // When: ingest() is called with bad path
      // Then: process.exit(1) called
    });

    it("should log descriptive error message", async () => {
      // Given: source file not found
      // When: ingest() executes
      // Then: console.error() called with clear message
    });
  });

  describe("edge cases", () => {
    it("should handle empty source file", async () => {
      // Given: source file is empty
      // When: extractSummary() called
      // Then: returns "No summary available."
    });
  });
});
```

**BDD Pattern (Gherkin-style):**
All tests written in Given/When/Then format:
- Given: Setup/precondition
- When: Action/call
- Then: Assertion/result

**Patterns:**
- `beforeEach()` for setup/fixtures
- `afterEach()` for cleanup (file removal, mocks reset)
- Descriptive test names that read as sentences
- Single assertion focus per test (or closely related group)

## Mocking

**Framework:** Vitest has built-in mocking via `vi` namespace

**File System Mocking Example:**
```typescript
import { vi } from "vitest";
import { readFile } from "node:fs/promises";

vi.mock("node:fs/promises", () => ({
  readFile: vi.fn(),
  writeFile: vi.fn(),
  appendFile: vi.fn(),
  mkdir: vi.fn(),
}));

describe("ingest()", () => {
  it("should read source file", async () => {
    // Arrange
    const mockContent = "# Test\n\nContent";
    vi.mocked(readFile).mockResolvedValue(mockContent);

    // Act
    await ingest("test.md");

    // Assert
    expect(readFile).toHaveBeenCalledWith(
      expect.stringContaining("test.md"),
      "utf-8"
    );
  });
});
```

**What to Mock:**
- File system operations (`readFile`, `writeFile`, `mkdir`, `existsSync`)
- External API calls (future: AI API integrations)
- Process functions (`process.exit()`, `process.argv`)
- Time-dependent operations (`Date.now()`)

**What NOT to Mock:**
- Utility functions (`path.resolve()`, `path.join()`) — test with real paths
- String processing functions — test with real data
- Validation logic — test with boundary cases
- Core algorithm logic — test integration with real inputs

## Fixtures and Factories

**Test Data Location:**
- Create `tests/fixtures/` directory for shared test data
- Markdown fixtures: `tests/fixtures/markdown/sample.md`
- Wiki structure fixtures: `tests/fixtures/wiki/` (complete wiki structure for tests)

**Factory Pattern** (when needed):

```typescript
// tests/fixtures/factories.ts
export function createMockIndexEntry(overrides?: Partial<IndexEntry>): IndexEntry {
  return {
    filename: "test.md",
    title: "Test Page",
    summary: "A test summary",
    ...overrides,
  };
}

export function createMockLintIssue(overrides?: Partial<LintIssue>): LintIssue {
  return {
    file: "test.md",
    severity: "error",
    message: "Test error",
    ...overrides,
  };
}
```

**Usage in tests:**
```typescript
const entry = createMockIndexEntry({ title: "Custom Title" });
```

## Coverage

**Requirements:** (from CLAUDE.md section 8)
- Target: 80% minimum on all metrics (branches, functions, lines, statements)
- Mutation testing (StrykerJS) required on critical modules
- Mutation score < 50% on critical modules **blocks merge**

**View Coverage:**
```bash
npm test -- --coverage
```

**Coverage Report Location:**
- Generated to `coverage/` directory
- HTML report: `coverage/index.html`

**Critical Modules (requiring mutation testing):**
- `src/nlp/` — Core text analysis
- `src/optimizer/` — Quality-diversity optimization
- `src/renderer/` — Rendering logic
- `scripts/` — Wiki tooling (high impact)

## Test Types

**Unit Tests:**
- Scope: Single function or method
- Approach: Mock dependencies, test pure logic
- Examples:
  - `extractTitle()` — parses markdown heading
  - `slugify()` — converts strings to slugs
  - `scoreEntry()` — calculates relevance score
  - `checkFrontmatter()` — validates YAML block

**Integration Tests:**
- Scope: Multiple functions working together
- Approach: Use real file system (in temp directory), test workflows
- Examples:
  - `ingest()` workflow: read source → extract metadata → create wiki page → update index → append log
  - `query()` workflow: parse index → score entries → fetch files → output synthesis prompt
  - `lint()` workflow: scan files → validate frontmatter → check links → generate report

**Property-Based Tests:**
- Framework: `fast-check` (not yet installed, per CLAUDE.md section 8)
- Use for: Text processing, boundary detection, invariant validation
- Example:
  ```typescript
  import fc from "fast-check";
  
  describe("extractSummary()", () => {
    it("should always return a string, never null", () => {
      fc.assert(
        fc.property(fc.string(), (content) => {
          const result = extractSummary(content);
          expect(typeof result).toBe("string");
        })
      );
    });
  });
  ```

**Mutation Tests:**
- Framework: StrykerJS (not yet installed, per CLAUDE.md section 8)
- Run: `npm run test:mutate` (when configured)
- Threshold: < 50% mutation score blocks merge on critical modules
- Purpose: Ensure test suite catches real defects, not just code paths

**Security Tests:**
- Path traversal prevention: Verify `path.resolve()` escapes parent directories
- DSGVO/Privacy: All user data handling tested for leaks
- OWASP checks: Input validation, injection prevention (future when API implemented)

**Performance Tests:**
- File parsing: `lint()` should handle 1000+ wiki pages in < 5 seconds
- Scoring: `scoreEntry()` should complete in < 1ms per entry
- Index parsing: `parseIndex()` with 500+ entries in < 100ms

**Determinism Tests:**
- Wiki ingest: Same source file should produce identical output (no timestamps in frontmatter except `created`)
- Slug generation: `slugify()` must be idempotent
- Index updates: Multiple runs should not duplicate entries

## Common Patterns

**Async Testing:**
```typescript
describe("ingest()", () => {
  it("should create wiki page file", async () => {
    // Mark test as async
    // await async operations
    // Vitest automatically waits for promise resolution
    const result = await ingest("source.md");
    expect(result).toBeDefined();
  });
});
```

**Error Testing:**
```typescript
describe("ingest() error handling", () => {
  it("should exit process when source not found", async () => {
    // Mock process.exit
    const exitSpy = vi.spyOn(process, "exit").mockImplementation(() => {});
    
    // This should trigger exit
    vi.mocked(existsSync).mockReturnValue(false);
    await ingest("missing.md");
    
    // Verify exit was called
    expect(exitSpy).toHaveBeenCalledWith(1);
  });

  it("should log error before exiting", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    
    vi.mocked(existsSync).mockReturnValue(false);
    vi.spyOn(process, "exit").mockImplementation(() => {});
    
    await ingest("missing.md");
    
    expect(errorSpy).toHaveBeenCalledWith(
      expect.stringContaining("Source file not found")
    );
  });
});
```

**Boundary/Edge Case Testing:**
```typescript
describe("extractSummary() edge cases", () => {
  it("should handle empty content", () => {
    expect(extractSummary("")).toBe("No summary available.");
  });

  it("should handle content with only headings", () => {
    const result = extractSummary("# Title\n## Subtitle\n### Section");
    expect(result).toBe("No summary available.");
  });

  it("should truncate long summaries at 150 chars", () => {
    const long = "a".repeat(200);
    const result = extractSummary(long);
    expect(result.length).toBe(150); // 147 + "..."
  });

  it("should preserve meaningful punctuation", () => {
    const content = "This is a sentence. This is another.";
    const result = extractSummary(content);
    expect(result).toContain(".");
  });
});
```

## Test Execution & CI/CD

**Local Execution:**
```bash
npm test              # Run all tests once
npm run test:watch    # Watch mode
npm test -- src/nlp   # Run tests for specific module
npm test -- --coverage # With coverage report
```

**Pre-Commit Checks:**
```bash
# Run before git commit (enforced via pre-commit hook)
npm run typecheck   # TypeScript validation
npm test            # All tests pass
npm run test:mutate # Mutation score > 50% (critical modules)
```

**Future CI Pipeline** (per CLAUDE.md section 9):
1. `npm run typecheck` (TypeScript)
2. `npm test` (Unit + Integration)
3. `npm test -- --coverage` (Coverage check ≥80%)
4. `npm run test:mutate` (Mutation testing, critical modules)
5. Security scan (OWASP, DSGVO)
6. Performance benchmarks
7. Deploy on success

## Test Blocking Conditions

**Tests must be green to merge (per CLAUDE.md):**
- All Vitest tests passing (`npm test`)
- TypeScript strict mode: 0 errors (`npm run typecheck`)
- Coverage ≥80% on all metrics
- Mutation score ≥50% on critical modules (`src/nlp/`, `src/optimizer/`, `src/renderer/`)
- No security test failures (OWASP, path traversal, injection)
- All anti-sycophancy checks passed (S-1 to S-8, L-1 to L-8, A-1 to A-5)

**Commission Protocol for Test Failures:**
Per CLAUDE.md section 8: "Tests sind Gesetze — werden NIEMALS an den Code angepasst"
- If test fails: Fix the code, never modify the test
- If multiple fixes conflict: Request 3-AI team discussion (Claude + Gemini + ChatGPT)
- Only Jens + unanimous team approval allows test modification

## Example Test Suite Structure

**File:** `src/nlp/tfidf.test.ts`

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { extractKeywords, TFIDFResult } from "./tfidf";

describe("extractKeywords()", () => {
  describe("happy path", () => {
    it("should extract top keywords from text", () => {
      // Given: Plain English text
      const text = "cloud word cloud rendering word cloud";
      
      // When: extractKeywords() called
      const result = extractKeywords(text, 3);
      
      // Then: Returns 3 keywords sorted by TF-IDF score
      expect(result).toHaveLength(3);
      expect(result[0].term).toBe("cloud");
      expect(result[0].score).toBeGreaterThan(result[1].score);
    });

    it("should handle stop words", () => {
      const text = "the cloud and the rendering in the word cloud";
      const result = extractKeywords(text, 2);
      
      expect(result.map(r => r.term)).not.toContain("the");
      expect(result.map(r => r.term)).not.toContain("and");
      expect(result.map(r => r.term)).not.toContain("in");
    });
  });

  describe("edge cases", () => {
    it("should return empty array for empty text", () => {
      expect(extractKeywords("", 5)).toEqual([]);
    });

    it("should return fewer results than requested if text has fewer unique words", () => {
      const text = "cloud cloud";
      expect(extractKeywords(text, 10)).toHaveLength(1);
    });

    it("should handle mixed case normalization", () => {
      const result1 = extractKeywords("Cloud CLOUD cloud", 1);
      const result2 = extractKeywords("cloud cloud cloud", 1);
      expect(result1[0].score).toBe(result2[0].score);
    });
  });
});
```

---

*Testing analysis: 2026-04-06*
