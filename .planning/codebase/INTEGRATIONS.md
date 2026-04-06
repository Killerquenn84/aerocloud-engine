# External Integrations

**Analysis Date:** 2026-04-06

## APIs & External Services

**Multi-AI Router (MCP Server):**
- Google Gemini - Advanced reasoning and code generation
  - SDK/Client: MCP protocol via stdio
  - Model: `gemini-2.0-flash`
  - Auth: `GEMINI_API_KEY` environment variable
  - Configuration: `mcp.json` lines 4-18

- OpenAI - Chat and reasoning API
  - SDK/Client: MCP protocol via stdio
  - Model: `gpt-4o`
  - Auth: `OPENAI_API_KEY` environment variable
  - Configuration: `mcp.json`

- Perplexity - Web search and synthesis
  - SDK/Client: MCP protocol via stdio
  - Model: `sonar-pro`
  - Auth: `PERPLEXITY_API_KEY` environment variable
  - Configuration: `mcp.json`

- Alibaba DashScope - Alternative AI provider
  - SDK/Client: MCP protocol via stdio
  - Model: `qwen-coder-plus`
  - Auth: `DASHSCOPE_API_KEY` environment variable
  - Configuration: `mcp.json`

**Multi-AI Router Configuration:**
- Location: `/var/www/wordcloud-app-v2/server/aerocloud-engine/mcp.json`
- Type: MCP (Model Context Protocol) server
- Command: `node C:\Users\flamm\multi-ai-mcp-server\src\index.js`
- All API keys passed via environment variables
- Used for collaborative AI decision-making (3-KI team discussions)

## Communication & Notifications

**Telegram Bot:**
- Purpose: Status updates and notifications to development team
- Bot Token: `TELEGRAM_BOT_TOKEN` environment variable
- Chat ID: 5697986530 (Jens - project owner)
- Integration: Referenced in `mcp.json` configuration
- Usage: All status messages and decision logs sent to Telegram

## Data Storage

**Wiki System (File-based):**
- Location: `wiki/` directory
- Format: Markdown with YAML frontmatter
- Content: Self-evolving knowledge base implementing Karpathy LLM Wiki pattern
- Components:
  - `wiki/index.md` - Index of all wiki pages with summaries
  - `wiki/log.md` - History of ingested sources
  - Individual topic pages (e.g., `adam-optimizer.md`, `sdf-geometry.md`)
- Client: Custom TypeScript scripts in `scripts/`

**Source Documents (Immutable):**
- Location: `raw/sources/` directory
- Format: Markdown files
- Content: Research papers, architecture documentation, algorithmic references
- Primary source: `raw/sources/AeroCloud-Blueprint.md`
- Management: Processed via `scripts/ingest.ts`

**No Persistent Database:**
- Project does not currently use PostgreSQL, MongoDB, or other database services
- All state exists in wiki markdown files and versioned source documents

## File Storage

- **Local Filesystem Only** - No cloud storage integration
- Wiki and source files stored locally in project directories
- No S3, Google Cloud Storage, or similar integrations

## Caching

- **Not Configured** - No Redis or caching layer detected
- No distributed caching or session storage
- Future optimization consideration for wiki queries

## Authentication & Identity

**Custom Implementation:**
- No OAuth, JWT, or third-party auth system
- API access authenticated via environment variables
- Each AI provider has own API key
- MCP server handles credential management via env vars
- All authentication is service-to-service (no user login system)

## Monitoring & Observability

**Error Tracking:**
- Not integrated - Project in early development phase
- No Sentry, DataDog, or similar error tracking

**Logs:**
- Console output from TypeScript execution
- Script output via stdout/stderr
- No structured logging framework

**Wiki Health:**
- `scripts/lint-wiki.ts` - Manual health checks
  - Validates wiki structure
  - Reports broken links
  - Detects orphaned pages
  - Tests frontmatter consistency

## CI/CD & Deployment

**Hosting:**
- Development: Local machine at `c:\Users\flamm\wordcloud-silhouette-app`
- Server: Hostinger VPS `srv791618.hstgr.cloud`, Ubuntu 24.04
- Server Path: `/var/www/wordcloud-app-v2/server/aerocloud-engine`

**Process Management:**
- PM2 on server (parent project uses PM2)
- Currently in development/testing phase
- No automated CI pipeline detected

**Build & Release:**
- No GitHub Actions, GitLab CI, or similar pipeline
- Manual build: `npm run build`
- Type checking: `npm run typecheck`
- Testing: `npm test`

## Environment Configuration

**Required Environment Variables:**
```
GEMINI_API_KEY          # Google Gemini API authentication
OPENAI_API_KEY          # OpenAI API authentication
PERPLEXITY_API_KEY      # Perplexity API authentication
DASHSCOPE_API_KEY       # Alibaba DashScope API authentication
TELEGRAM_BOT_TOKEN      # Telegram bot token for notifications
```

**Configuration File:**
- `mcp.json` - MCP server config with env var references
- `.env` - Local development environment file (not committed, ignored in `.gitignore`)

**Secrets Location:**
- Environment variables in `.env` (development)
- Shell environment on server
- Note: Never hardcode secrets in code (enforced by CLAUDE.md rules)

## Webhooks & Callbacks

**Incoming Webhooks:**
- None detected - Not applicable for standalone engine

**Outgoing Webhooks:**
- Telegram notifications (one-way push to bot)
- No callback mechanisms to external services

## Parent Project Integration

**Wordcloud Silhouette App v2 Integration:**
- Parent location: `/var/www/wordcloud-app-v2`
- Related components:
  - Admin app: `apps/admin/` (React Router v7 + Polaris)
  - Shared packages: `packages/shared/`, `packages/render-core/`, `packages/worker/`
  - Rendering uses this engine's modules
- Not tightly coupled at code level (library-style integration)
- Follows monorepo structure (pnpm workspaces + Turborepo)

## BMAD Integration

**Methodology Integration:**
- BMAD Method v6.2.2 for development workflow
- Tools and agents in `_bmad/` directory
- Skill templates for brainstorming, party mode, advanced elicitation
- Team discussion framework for multi-AI consensus
- Not a technical integration, but process/workflow integration

## Future Integrations (Planned)

Per `raw/sources/AeroCloud-Blueprint.md`:
- PyTorch/CUDA - GPU-accelerated rendering (planned)
- sentence-transformers - Advanced NLP embeddings (planned)
- Database integration - For larger-scale operations (future)

---

*Integration audit: 2026-04-06*
