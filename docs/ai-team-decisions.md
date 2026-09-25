# AI Team Decisions — AeroCloud Engine

> All architectural and design decisions made by the 3-AI team (Claude Code, Gemini, ChatGPT).
> Read this file BEFORE every work session. Decisions are only revisable through new 3-AI discussion.

---

## Decision Log

### [2026-04-06] Initial Project Setup
- **Topic:** Project architecture and LLM Wiki integration
- **Participants:** Claude Code (lead), Gemini, ChatGPT
- **Decision:** Dual-Loop architecture (Inner Loop: PyTorch GPU, Outer Loop: QD/MAP-Elites) with Karpathy LLM Wiki pattern for self-maintaining knowledge base
- **Consensus:** Unanimous
- **Zusammenfassung (DE):** Projektstruktur mit Dual-Loop-Architektur und selbstpflegendem Wiki-System beschlossen.

---

_New decisions are appended below. Format: Date, Topic, Participants, Decision, Consensus status, German summary._

---

### [2026-04-07] Polyglot Stack Selection (Bottom-Up Build Order)
- **Topic:** Full Blueprint v1 polyglot stack (Python engine core, Rust/WASM preview, Next.js frontend, FastAPI + Celery + Redis + PostgreSQL + pgvector)
- **Participants:** Claude Code (orchestrator), Gemini CLI (researcher), Codex CLI (code reviewer)
- **Decision:**
  - Python 3.11 as engine core, Rust ONLY for WASM browser preview (no PyO3 in Inner Loop hot path)
  - 12-phase roadmap with bottom-up build order (Geometry → NLP → Inner Loop → Outer Loop → Export)
  - Iterative reification per domain within v1 milestone (Geometry-v1 → Geometry-v2, Outer-Loop-v1 → Outer-Loop-v2)
  - All Blueprint features in v1, no scope reduction
  - Hostinger Cloud VPS with NVIDIA-Docker as deployment target
- **Consensus:** Unanimous after round 2 (Codex initially proposed iterative scope cuts; compromise is "all features in v1, but built in stages")
- **Zusammenfassung (DE):** 12-Phasen-Roadmap, alle Blueprint-Features in v1, iterative Reifung pro Modul. Python zentriert, Rust nur für WASM, Next.js 16 Frontend, Hostinger Cloud Deployment.

### [2026-04-07] Codex-Verified Library Versions
- **Topic:** Stack version verification against live PyPI / upstream
- **Participants:** Gemini CLI (proposal), Codex CLI (verification via web search)
- **Decision:** Use Codex-verified versions only. Six Gemini hallucinations corrected:
  - `nvdiffrast` 0.3.3.1 (NOT 0.4.0 — does not exist)
  - `POT` 0.9.6.post1 (NOT 1.0.2 — does not exist)
  - `spacy` 3.x (NOT 4.x — does not exist)
  - `scikit-fmm` 2025.6.23 (NOT 2025.12 — does not exist)
  - `svgelements` replaces `svgwrite` 1.5.1 (does not exist; svgwrite is inactive since 2022)
  - Next.js 16 (NOT 14 — Next.js 16 since 2025-10-21)
- **Architecture smells blocked by Codex:**
  - No `structlog + loguru` hybrid — only `structlog + stdlib logging`
  - Celery configured minimally — no power-user features (only needed for Self-Play scheduling)
  - Turborepo deferred — `uv workspace + Cargo + pnpm` is the default
- **Critical additions from Codex:**
  - Strict NumPy/PyTorch pinning (mandatory for nvdiffrast)
  - Alembic for SQL migrations with `CREATE EXTENSION vector`
  - `mypy --strict` + `ruff` (no Black)
  - OpenTelemetry tracing (not just Prometheus metrics)
  - `safetensors` instead of `pickle` for model checkpoints
- **Consensus:** Unanimous. Claude integrates Codex's verified versions into the planning artifacts.
- **Zusammenfassung (DE):** Codex hat alle Gemini-Stack-Vorschlaege live gegen PyPI verifiziert und 6 Halluzinationen entlarvt. Die korrigierten Versionen sind in `wiki/stack-versions.md` und `.planning/research/STACK.md` dokumentiert. Architektur-Smells (structlog+loguru Hybrid, Celery als Default, Turborepo im Greenfield) wurden blockiert. Lessons Learned in `wiki/codex-corrections.md`.

### [2026-04-07] Rule Correction — Research Ownership
- **Topic:** Who performs research in the 3-AI workflow?
- **Participants:** Jens (project owner), Claude Code
- **Decision:** Research is Gemini's exclusive responsibility via `gemini -p` CLI calls. Claude Code MUST NOT spawn Claude subagents (Sonnet) for research. Claude is the orchestrator and code writer, not a research delegator.
- **Trigger:** Claude initially spawned 4 `gsd-project-researcher` (Sonnet) subagents. Jens detected the rule violation and enforced correction.
- **Action taken:** All 4 Claude subagents stopped via TaskStop. Research redone with `gemini -p` (4 sequential calls) + `codex exec --skip-git-repo-check` for verification.
- **Consensus:** Binding. This rule is permanently documented in CLAUDE.md sections 1, 4, 6.
- **Zusammenfassung (DE):** Recherche gehoert GEMINI, nicht Claude-Subagents. Claude orchestriert, Gemini recherchiert, Codex reviewt. Regel-Verletzung erkannt und korrigiert, Artifacts neu erstellt.
