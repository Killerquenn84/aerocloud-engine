# Technology Stack

**Analysis Date:** 2026-04-06

## Languages

**Primary:**
- TypeScript 5.7+ - All source code, ESM only (no CommonJS)
- Node.js JavaScript - Runtime for scripts and build tools

**Secondary:**
- Markdown - Documentation and wiki content
- YAML - Configuration and frontmatter in wiki system

## Runtime

**Environment:**
- Node.js 22 LTS (see `.nvmrc`)

**Package Manager:**
- npm 10+ (lockfile: `package-lock.json` present)
- Note: Project inherited npm, transitioning planned to pnpm per parent project standards

## Frameworks

**Core:**
- None (standalone engine) - Pure Node.js modules

**Build/Dev:**
- TypeScript Compiler (tsc) - Build and typecheck
- tsx - Script runner for TypeScript execution
- Vitest 3.0.0 - Test framework and runner

## Key Dependencies

**Critical:**
- `natural` 8.0.1 - NLP library for tokenization, stemming, TF-IDF
  - Module: `src/nlp/` uses for text analysis and keyword extraction
- `compromise` 14.14.3 - Natural language processing library
  - Used for linguistic analysis and tokenization patterns
- `marked` 15.0.0 - Markdown parser for wiki content processing
  - Used in `scripts/query.ts` and `scripts/ingest.ts` for wiki management

**Infrastructure:**
- `@types/node` 22.0.0 - TypeScript definitions for Node.js APIs
- `tsx` 4.21.0 - TypeScript execution engine for scripts

## Configuration

**Environment:**
- `.env` file present (see `.gitignore` - not committed)
- Multi-AI integration via `mcp.json` with environment variables:
  - `GEMINI_API_KEY` - Google Gemini API key
  - `OPENAI_API_KEY` - OpenAI API key
  - `PERPLEXITY_API_KEY` - Perplexity API key
  - `DASHSCOPE_API_KEY` - Alibaba DashScope API key
  - `TELEGRAM_BOT_TOKEN` - Telegram bot for notifications

**Build:**
- `tsconfig.json` - TypeScript compilation configuration
  - Target: ES2022
  - Module: ESNext (ESM)
  - Strict mode enabled
  - Source maps enabled
  - Output directory: `dist/`

**Runtime Configuration:**
- `mcp.json` - MCP (Model Context Protocol) server configuration
  - Defines multi-AI router with Gemini 2.0 Flash, GPT-4o, Sonar Pro, Qwen Coder Plus
  - Location: `/var/www/wordcloud-app-v2/server/aerocloud-engine/mcp.json`

## Platform Requirements

**Development:**
- Node.js 22+
- TypeScript 5.7+
- Access to external AI APIs (Gemini, OpenAI, Perplexity, Alibaba DashScope)
- Optional: Telegram bot for notifications

**Production:**
- Node.js 22 LTS
- No external runtime dependencies (pure Node.js)
- Standalone CLI/module execution

## Scripts and Tooling

**Wiki Management:**
- `npm run wiki:ingest` - Process source documents into wiki format
  - Script: `scripts/ingest.ts`
  - Creates markdown with YAML frontmatter, updates index and log
- `npm run wiki:query` - Search and synthesize knowledge from wiki
  - Script: `scripts/query.ts`
  - Keyword-based search with relevance scoring
- `npm run wiki:lint` - Health-check wiki structure
  - Script: `scripts/lint-wiki.ts`
  - Validates frontmatter, finds broken links, orphaned pages

**Development Commands:**
- `npm run dev` - Watch mode development with tsx
- `npm run build` - Compile TypeScript to dist/
- `npm test` - Run Vitest suite once
- `npm run test:watch` - Continuous test watching
- `npm run typecheck` - TypeScript validation without emit

## Architecture Notes

- **Module Structure:** Organized by domain (`src/nlp/`, `src/geometry/`, `src/renderer/`, `src/optimizer/`, `src/export/`)
- **Wiki System:** Implements Karpathy LLM Wiki pattern for self-evolving knowledge base
  - Location: `wiki/` (LLM-maintained)
  - Source documents: `raw/sources/` (immutable)
  - Index: `wiki/index.md`
  - Log: `wiki/log.md`
- **BMAD Integration:** Quality-diversity optimization using BMAD v6.2.2 methodology
  - Stored in `./_bmad/` directory
  - Contains skill templates and workflow definitions

---

*Stack analysis: 2026-04-06*
