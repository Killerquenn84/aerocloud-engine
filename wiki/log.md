# AeroCloud Wiki – Log

> Chronologische Aufzeichnung aller Wiki-Aktivitaeten.

## [2026-04-06] ingest | AeroCloud-Blueprint.md
- Neue Seiten: overview, zipf-law, tf-idf-ap, np-hard-packing, bert-embeddings, optimal-transport, sdf-geometry, medial-axis, collision-detection, differentiable-rendering, adam-optimizer, cqd-metric, map-elites, seam-carving, bezier-export, quality-metrics, source-blueprint
- Aktualisierte Seiten: index.md (erstellt)
- Erkenntnisse: Blueprint deckt 5 mathematische Disziplinen ab. Implementierung sollte schrittweise erfolgen: NLP → Geometry → Renderer → Optimizer → Export

## [2026-04-07] stack-review | 3-KI Consensus + Codex Verifikation
- Neue Seiten: stack-versions.md, codex-corrections.md
- Aktualisierte Seiten: index.md (zwei neue Kategorie-Eintraege)
- Workflow: Gemini recherchierte Stack-Vorschlaege (Python + PyTorch + CUDA + FastAPI + Celery + Next.js + Rust/WASM). Codex verifizierte alle Versionen live gegen PyPI und offizielle Upstreams.
- Codex entlarvte 6 Halluzinationen: nvdiffrast v0.4.0 (real: 0.3.3.1), POT v1.0.2 (real: 0.9.6.post1), spaCy v4.1 (real: v3.x), scikit-fmm v2025.12 (real: 2025.6.23), svgwrite v1.5.1 (real: 1.4.3 + inaktiv), Next.js v14 (real: v16 seit 2025-10-21).
- Codex blockierte 3 Architektur-Smells: structlog+loguru Hybrid, Celery-als-Default, Turborepo-im-Greenfield.
- Codex ergaenzte kritisch: NumPy/PyTorch Pinning, Alembic, mypy/ruff, OpenTelemetry, safetensors statt pickle.
- Erkenntnisse: Anti-Sycophancy funktioniert. Version-Pinning ist nicht verhandelbar bei Dependencies mit C-Extensions. "Latest" ist kein Vertrauens-Signal. Inaktive Pakete sind technische Schuld. Produkt vor Plattform.
- Konsequenz: .planning/research/STACK.md wurde nach Codex-Review korrigiert. Alle zukuenftigen Stack-Entscheidungen laufen durch Codex-Verifikation.

## [2026-04-07] project-init | GSD Planning Artifacts
- Neue Artifacts: .planning/PROJECT.md, .planning/config.json, .planning/research/ (STACK + FEATURES + ARCHITECTURE + PITFALLS + SUMMARY), .planning/REQUIREMENTS.md (109 reqs), .planning/ROADMAP.md (12 Phasen), .planning/STATE.md
- 3-KI Workflow: Claude Code (Orchestrator + Code), Gemini CLI (Researcher), Codex CLI (Reviewer)
- 12-Phasen-Roadmap mit Bottom-Up Build Order (Geometrie → NLP → Inner Loop → Outer Loop → Export) und iterativer Reifung pro Domaene (v1 → v2 innerhalb v1 Milestone)
- Alle 11 Blueprint-Teile in v1 enthalten, KEINE Vereinfachung
- Hostinger Cloud VPS mit NVIDIA-Docker als Deployment-Ziel

## [2026-04-07] ingest | SUMMARY.md
- Neue Seite: summary
- Sektion: Mathematische Grundlagen
- Zusammenfassung: **Researched by:** Gemini CLI (4 dimensions) + Codex CLI (verification)

## [2026-04-07] ingest | REQUIREMENTS.md
- Neue Seite: requirements
- Sektion: Mathematische Grundlagen
- Zusammenfassung: **Defined:** 2026-04-07

## [2026-04-07] reorganization | Wiki-Kategorien-Struktur
- Neue Verzeichnisse: wiki/code/, wiki/corrections/, wiki/discussions/, wiki/research/, wiki/decisions/, wiki/tests/, wiki/bugs/, wiki/knowledge/
- Kopiert nach wiki/research/: stack.md, features.md, architecture.md, pitfalls.md, summary.md (aus .planning/research/)
- Verschoben: stack-versions.md -> wiki/knowledge/, codex-corrections.md -> wiki/corrections/2026-04-07-stack-hallucinations.md
- Geloescht: wiki/summary.md und wiki/requirements.md (auto-generated Ingest-Outputs, ersetzt durch wiki/research/summary.md)
- Neue Decision: wiki/decisions/2026-04-07-polyglot-stack-selection.md (gespiegelt aus docs/ai-team-decisions.md)
- Aktualisiert: wiki/index.md komplett neu strukturiert mit 8 Kategorien
- Neue Regel von Jens: ALLES landet im Wiki. Code -> wiki/code/, Korrektur -> wiki/corrections/YYYY-MM-DD-topic.md, Diskussion -> wiki/discussions/YYYY-MM-DD-topic.md, etc. Kein Kontextverlust zwischen Sessions.

## [2026-04-07] nightly-research | Initial Seed (manual test runs)
- Neue Seiten: research/nightly/2026-04-07-sinkhorn-knopp-optimal-transport.md, research/nightly/2026-04-07-spacy-transformer-models-german-english.md
- Methode: scripts/nightly-research.sh (dry run) + manuelle Regeneration zur Wiederherstellung des ersten Wissens
- Regel: Wissen wird NIEMALS geloescht. Es waechst nur. Auch Test-Runs sind Wissen.
- Crontab eingerichtet: 0 2 * * * (02:00 Berlin) fuer aerocloud user
- Naechster autonomer Lauf: heute Nacht 02:00 MESZ

## [2026-04-07] cron-setup | Nightly Research Orchestration
- scripts/nightly-research.sh mit --dry Flag getestet (1 topic, erfolgreich)
- scripts/nightly-topics.txt mit 43 Topics erstellt (Blueprint Teile + Engine Module + Stack Components)
- scripts/lint-wiki.ts aktualisiert: collectMarkdownFiles rekursiv, research/nightly/ orphan-check ausgenommen
- Crontab User 'aerocloud' gesetzt mit CRON_TZ=Europe/Berlin
- Log-Rotation in logs/nightly.log (gitignored)
- Dry-run Test: Gemini responded mit OTT-JAX v1.4.2 Update + ETH Zuerich Paper

## [2026-04-07] phase-01 | Foundation Context gathered
- Neue Dateien: .planning/phases/01-foundation/01-CONTEXT.md (40 Decisions), .planning/phases/01-foundation/01-DISCUSSION-LOG.md
- Neue Wiki-Mirrors: discussions/2026-04-07-phase-01-context.md, discussions/2026-04-07-phase-01-discussion-log.md
- 3-KI Workflow: Claude Orchestrator, Gemini Research (Option B Migration), Codex Review (blockierte Option B)
- Konsens: Option A Hybrid — TS Wiki bleibt im Root, Python in packages/engine/, scripts/ bleiben intakt
- 40 gelockte Decisions D-01 bis D-40 in 13 Bereichen: Repo Struktur, uv Workspace, Docker, Dev Stack, Determinism, CI, Config, Observability, GPU, Fonts, Tests, Code Quality, Scope Exclusions
- Phase 1 adressiert Pitfalls #10 (NVIDIA-Docker VPS), #11 (Determinismus), #18 (Reproduzierbarkeit) aus .planning/research/PITFALLS.md
- Naechster Schritt: /gsd-plan-phase 1

## [2026-04-07] phase-01 | PLAN.md created (Codex reviewed)
- Neue Dateien: .planning/phases/01-foundation/01-RESEARCH.md (Gemini templates), .planning/phases/01-foundation/01-PLAN.md (10 Waves, ~70 Tasks)
- Wiki Mirror: knowledge/phase-01-plan.md, research/phase-01-foundation-research.md
- Codex Review: 8 Punkte kritisiert, alle eingearbeitet:
  - Wave-Reorder: Docker (4) und GPU Smoke (5) vor Fonts (6)
  - Wave 0 Rollback verstaerkt: Tag + Branch + Clean Tree (3-Layer)
  - Fehlende Tasks ergaenzt: .python-version, .gitignore, .dockerignore, Font License Pre-Check, uv.lock integrity, uv build smoke, package import smoke, Docker build smoke, actionlint
  - GPU Smoke Test verstaerkt: get_device_capability + get_device_name + torch.version.cuda + Tensor alloc + nvdiffrast probe
  - Risks erweitert um CUDA/Torch/nvdiffrast ABI, Font licensing, Hybrid drift, Lockfile drift
  - FOUND-03 von 'partially satisfied' zu 'SUPERSEDED by D-01'
- Verification Wave 9 expandiert: uv sync --frozen, uv lock --locked, uv build, import smoke, npm tests, cron check, docker build+compose, actionlint, git status clean
- Bereit fuer Execution

## [2026-04-07] nightly-research | 1 topics
- mutmut Mutation Testing Strategy

## [2026-04-07] phase-01 | Execution Waves 0-8 completed
- Wave 0: rollback branch + baseline tag (phase-1-baseline)
- Wave 1: uv workspace skeleton (root pyproject.toml, .python-version, uv.lock, workspace members as deps)
- Wave 2: determinism + config + logging + observability + fonts.py modules
- Wave 3: unit/integration/gpu test skeleton (13 unit tests green)
- Wave 4: Docker dev stack (postgres-pgvector, redis, api, worker Dockerfiles, .dockerignore)
- Wave 5: GPU smoke test (package module + root wrapper, aerocloud-gpu-smoke CLI)
- Wave 6: Inter + IBM Plex Serif fonts bundled with SIL OFL, font discovery verified via importlib.resources
- Wave 7: GitHub Actions workflows (ci-python, ci-typescript, ci-rust, ci-integrity with secret scan + pickle policy)
- Wave 8: README rewritten for polyglot monorepo, FOUND-03 marked SUPERSEDED, wiki-log updated

Issues resolved during execution:
- uv not installed on host -> installed via official curl script
- pyribs on PyPI is 'ribs' not 'pyribs' -> corrected optional-dep
- uv workspace members not installed automatically -> added as root project.dependencies + tool.uv.sources = workspace
- structlog PrintLoggerFactory has no logger.name -> switched to stdlib LoggerFactory
- IBM Plex Serif URL path outdated -> packages/plex-serif/fonts/complete/ttf/
- Fonts in packages/engine/assets/ not found by importlib.resources -> moved into src/aerocloud/assets/

13 unit tests passing, 2 GPU tests gracefully skipped on CPU-only host.

## [2026-04-07] nightly-research | 1 topics
- Seam Carving Word Cloud Whitespace

## [2026-04-07] nightly-research | 1 topics
- Sentence Transformers Library
