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

## [2026-04-07] phase-02 | Datenmodell + Wiki completed
- Wave 1: 13 Pydantic models (tokens, shapes, layout, archive, api, base) with AeroCloudBase(frozen+strict+forbid)
- Wave 2: ReproducibilityID model + compute_id helper + canonical_input_hash (7 tests)
- Wave 3: Alembic baseline migration (archive_v1 table + HNSW index on descriptor vector(384))
- Wave 4: Safetensors policy test (no pickle imports in source)
- Wave 5: Verification — 34 unit tests passing, mypy strict 0 errors, uv build successful
- Wiki mirror: discussions/2026-04-07-phase-02-context.md, knowledge/phase-02-plan.md

## [2026-04-07] phase-03 Wave 1 | NLP Core (pure-Python, no heavy deps)
- nlp/tfidf.py: TF-IDF-AP with PositionalSignal (title/heading/first_sentence/emphasis boosts)
- nlp/zipf.py: log-normalization score -> font size (max log ratio compression)
- nlp/corpus_guard.py: linear fallback below 20 unique tokens
- tests/unit/test_nlp_core.py: 22 tests passing (TF-IDF: 7, Zipf: 8, corpus guard: 5, PositionalSignal: 3)
- Wave 2 (spaCy + lingua + stopwords) deferred to next session — heavy dep install
- Total unit tests: 56 (34 prior + 22 new)
- mypy strict: 0 errors in 23 source files

## [2026-04-08] nightly-research | 3 topics
- BERT Embeddings all-MiniLM-L6-v2
- POT Python Optimal Transport Library
- BOP-Elites Bayesian Optimization

## [2026-04-08] phase-03 Wave 2 | spaCy tokenizer + lingua detection + stopwords
- nlp/tokenize.py: spaCy adapter with thread-safe RLock registry, MissingSpacyModelError fail-fast (no auto-download), stem fallback to lowercased surface (works with spacy.blank in tests), Token emission drops whitespace + punctuation
- nlp/language.py: lingua LanguageDetectorBuilder limited to EN+DE, lazy RLock-guarded singleton, confidence threshold with 'und' fallback on short/ambiguous input
- nlp/stopwords.py: spaCy builtin word lists (spacy.lang.{en,de}.stop_words) — stopwordsiso PyPI package declared dead by Codex (letzter Release 2020-09, Alpha)
- tests/unit/test_nlp_wave2.py: 20 tests (stopwords 6, tokenize 10 incl. thread-safety race on cold cache, language detect 4)
- Hermetic tests: spacy.load patched to return real spacy.blank('en')/('de') — authentic Doc/Token object graph without 50 MB model downloads
- pyproject.toml [nlp] extra: added lingua-language-detector>=2.1,<2.2 (2.2+ only ships cp312+ wheels, engine pins py<3.12)
- 3-KI Konsens dokumentiert: wiki/discussions/2026-04-08-phase-03-wave-2-design.md — Gemini initial, Codex adversarial review entlarvte 4 Schwaechen (dict ohne Lock, MagicMock-Fragility, stopwordsiso-Tod, lingua-Pin), alle Fixes eingearbeitet
- Total unit tests: 76 (56 prior + 20 new), mypy strict: 0 errors in 24 source files, ruff: clean

## [2026-04-08] phase-03 Wave 3 | Pipeline orchestrator (single-doc TF-IDF via sentence-DF)
- nlp/pipeline.py: text_to_candidates(text, max_words=200, language='auto') -> list[WordCandidate]
- nlp/tokenize.py extended: tokenize_sentences() + idempotent _ensure_sentence_boundaries() that adds sentencizer if pipeline lacks parser/sentencizer (covers spacy.blank() in tests AND trained pipelines in production)
- Single-document TF-IDF: sentences ARE the documents — DF = number of sentences a stem appears in. Codex bestaetigt sound for single-doc IDF surrogate.
- Pipeline order (sequential, language-dependent): detect_language -> tokenize_sentences -> filter (stopwords + 1-char alpha) -> stems aggregate -> small-corpus guard OR compute_tfidf_ap with first-sentence + markdown-title PositionalSignal -> top-N by score -> zipf_font_sizes -> WordCandidate emit
- Determinism: score DESC, stem ASC tiebreak. Two runs on same input produce byte-identical output (test verifies via model_dump).
- 'und' from auto detect raises LanguageDetectionFailedError — explicit failure beats silent fallback to English
- Markdown title heuristic: first non-empty line starting with '# ' is the title; its content stems get title=True boost
- Display surface: most-frequent surface form per stem, tiebreak first-occurrence
- tests/unit/test_nlp_pipeline.py: 18 new tests across 4 classes (tokenize_sentences 3, small-corpus path 5, IDF path 4, edges 6)
- 3-KI Konsens: Codex review (8 questions answered, all approved before code) — sentencizer over regex, top-N before Zipf, raise on 'und', drop 1-char alphabetic, score-then-stem deterministic order
- Total unit tests: 94 (76 prior + 18 new), mypy strict: 0 errors in 25 source files, ruff: clean

## [2026-04-08] phase-03 Wave 4 | Code Review + Hardening + merge to main
- 3-Daumen-Code-Review per Regel 6: Claude self (3 findings), Codex (3 + 6 findings, APPROVED-WITH-FIXES), Gemini (BLOCK on 6 findings)
- Konsens must-fix Liste eingearbeitet:
  - F-1/N-1: _extract_markdown_title_line walks chars iteratively with scan budget 4096 + max title 256, KEIN splitlines() mehr (DoS guard against multi-megabyte first lines)
  - F-2: _apply_positional_boost neuer helper, small-corpus linear fallback bekommt jetzt title + first_sentence boost (vorher silently dropped)
  - F-3: text_to_candidates docstring listet alle 4 raises (ValueError, LanguageDetectionFailedError, UnsupportedLanguageError, MissingSpacyModelError)
  - Symbol/Numeric leak: _is_content_token droppt Tokens ohne jeden alpha-Char (covers spaCy SYM tokens '==', '+', '$' und numerische '2024', '100.0' die vorher Geschaeftsberichte fluteten)
  - N-6: min_font_size + max_font_size validation am Funktionsanfang vor jeder anderen Arbeit
- Codex Re-Review nach Fixes (mit code im prompt): APPROVED-WITH-NEXT-PHASE-NOTES — alle 5 Fixes korrekt implementiert, Tests substanziell (kein cargo-cult). Empfahl direkten Unit-Test fuer _extract_markdown_title_line.
- 17 neue Wave 4 Tests (8 hardening + 8 markdown title helper + 1 strengthening): oversized title rejected, scan-budget bails on 1MB no-newline input, exact-cap kept + one-over rejected, symbol/numeric drop, alphanumeric (covid-19) kept, small-corpus title boost flips ranking, font validation early
- Known Limits (next phase, v2 backlog): N-2 mixed-language, N-3 casing collapse, N-4 title double-count, N-5 stem-alphabetical tiebreak — alle dokumentiert in .planning/STATE.md
- Wave 4 doc: wiki/discussions/2026-04-08-phase-03-wave-4-codereview.md
- Total unit tests: 111 (94 prior + 17 new), mypy strict: 0 errors in 25 source files, ruff check + format: clean
- Phase 3 NLP-v1 abgeschlossen, ready fuer Phase 4 Geometry-v1

## [2026-04-09] nightly-research | 5 topics
- Alembic pgvector Migrations
- structlog OpenTelemetry Tracing
- NP-Hard Irregular Bin Packing
- Bezier Sub-Millimeter Precision Export
- Sinkhorn-Knopp Optimal Transport

## [2026-04-09] phase-04 | CONTEXT.md gathered (3-KI adversarial, Codex BLOCKED all 3 risk areas)
- Neue Dateien: .planning/phases/04-geometry-v1/04-CONTEXT.md (51 D-decisions), 04-DISCUSSION-LOG.md, 3ki-g3-g4-g5/{codex-g3,codex-g4,codex-g5,gemini-g3,gemini-g5}.md
- Wiki Mirror: discussions/2026-04-09-phase-04-context.md, discussions/2026-04-09-phase-04-discussion-log.md
- Architekt (Jens) triagierte 6 Gray Areas: G-1/G-2/G-6 Claude's Discretion, G-3/G-4/G-5 zwingend 3-KI; dazu 4 blind-spot constraints (SDF sign positive=inside D-09, (y,x) coord dogma D-14, EmptyMaskError fail-fast D-08, AEROCLOUD_DEBUG_GEO dump D-47)
- **Codex BLOCKED all 3 adversarial reviews** mit konkreten Failure-Szenarios:
  - G-3 SDF Cache: xxhash64 Kollisionsrisiko, int16-Quantisierung staircased Phase 6 Adam, maxsize=50 = 3.2 GB OOM, cachetools not thread-safe. Resolution: blake3+params+algo-salt Key, bytes-bounded 384 MiB, float32, RLock, no quantization
  - G-4 Glyph Raster: HALLUCI-CATCH `hint_style` Parameter existiert nicht in Pillow. Homebrew Pillow freetype 2.14.2 drift real. BASIC layout kills ligatures → render per codepoint. Image.resize() FP math unreliable. Resolution: `font.getmask(char, mode="L")` + `PIL.features.version("freetype2")` runtime assertion + Homebrew Pillow blocked + golden-corpus CI regression
  - G-5 Spiral: single-origin O(4.1e7) probes for 200 words confirmed by math, MAX_STEP=32 creates aliasing pockets, per-word adaptive origin mandatory. Resolution: per-word POI recompute, eps-band + centroid-distance + (y,x) lex tiebreak, integer candidate order, MAX_STEP=16, per-seed budgets, structured PlacementResult mit DropReason enum
- Gemini: g-3 + g-5 succeeded (g-5 via 2.5-flash fallback), g-4 capacity-exhausted (alle 3 Modelle 429) → Codex + Architekt als sole verification for G-4
- Scope: STRICT GEO-01..07, absolutes Phase-7-Pull-forward-Verbot
- Anti-Sycophancy Self-Check passed — jede Acceptance hat independent evidence
- Bereit fuer /gsd-plan-phase 4

## [2026-04-09] phase-04 | PLAN.md 7 plans / 22 tasks / 6 waves (plan-checker PASSED)
- Neue Dateien: .planning/phases/04-geometry-v1/04-RESEARCH.md (948 Zeilen, 12 findings + Validation Architecture + 6-wave topology + 9 Risks), 04-VALIDATION.md (Nyquist 8-dim, per-task map fuer alle 22 Tasks, nyquist_compliant=true), 04-01..04-07 PLAN.md (3750 Zeilen gesamt)
- Wiki Mirror: wiki/research/2026-04-09-phase-04-research.md, wiki/knowledge/phase-04-validation.md
- Wave-Topologie:
  - Wave 0: 04-01-scaffolding (ADRs 0004/0005/0006, errors.py, test subtree, cachetools+blake3 deps) — serial, blocks all
  - Wave 1: 04-02-mask-sdf (Pillow decoder + scipy EDT double-call + _assert_freetype import gate) — 3 tasks
  - Wave 2a: 04-03-sdf-cache (LRUCache 384 MiB bytes-bounded, blake3 composite key, module RLock, 16-thread concurrency test) — 2 tasks
  - Wave 2b: 04-04-glyph-golden (font.getmask mode='L', ~450 golden .npy fixtures Inter+IBM Plex, Pydantic AABB/GlyphBBox) — 3 tasks, PARALLEL zu 2a
  - Wave 3: 04-05-collision-placement (vectorized int AABB + per-word adaptive POI + integer Archimedean spiral + PlacementResult+DropReason + integration test) — 3 tasks
  - Wave 4: 04-06-observability-gates (AEROCLOUD_DEBUG_GEO dump, structlog+OTel, Nyquist dims 6/7/8: determinism+fuzz+benchmark 2048² SDF <1s, 11 wiki files) — 3 tasks
  - Wave 5: 04-07-3ki-review (Claude self + Codex adversarial + Gemini perf, 3-Daumen-Prinzip, autonomous=false checkpoint) — 5 tasks
- Plan-checker VERIFICATION PASSED (gsd-plan-checker, sonnet): 10 Dimensionen alle gruen
  - Alle 7 GEO-01..07 Requirements mapped
  - Alle 16 kritischen CONTEXT.md D-constraints in Task-Actions implementiert
  - Alle 51 D-XX Decisions mindestens einmal zitiert
  - Alle 8 Nyquist-Dimensionen (unit/integration/contract/state/concurrency/determinism/security/perf) covered
  - Alle 7 Threat-Model-Items (T-4-01..T-4-07) zu Tasks mapped
  - Scope-Sanity: max 3-5 Tasks pro Plan, files_modified realistisch, wiki-mandate erfuellt
  - D-26 hallucination protection: grep-assert `hint_style` nirgendwo im Glyph-Code
  - D-51 no-mocking: alle tests benutzen reale Pillow/scipy/numpy, mit einer dokumentierten Ausnahme (monkeypatch `PIL.features.version` fuer mismatch-test)
- INFO (non-blocking): REQUIREMENTS.md GEO-04 text ist stale (pre-Codex-redesign), wird waehrend Wave 0/2a aktualisiert. 04-05-T2 verify-tag hat kleines copy-paste-Artefakt (doppeltes `<automated>`), zweiter Block ist korrekt.
- Bereit fuer /gsd-execute-phase 4

## [2026-04-09] phase-04 | Wave 5 — 3-KI Code Review + Phase Close-Out (COMPLETE)

- 3-KI code review applied: Claude self (APPROVED-WITH-NOTES), Codex (BLOCKED), Gemini 2.5-pro (BLOCKED)
- Two deviations presented to Jens: performance gate miss (24.85s vs 5.0s) + FreeType pin mismatch
- Jens approved Action A = Decision A (Option 1) + Decision B (Option A):
  - Decision B: FreeType pin updated 2.13.2 -> 2.14.3; AEROCLOUD_SKIP_FREETYPE_CHECK bypass removed;
    conftest.py shims removed; test_package_init.py updated; ADR-0006 v2 written
  - Decision A: place_words 5.0s gate formally retired to 60s (VPS ceiling);
    wiki/knowledge/phase-4-known-limits.md created with root cause + Phase 7 mitigation paths
- Gemini bonus fixes applied: gc.collect RSS fix (cast edt_in to f32 first) + float32 promotion
  fix in select_origin (np.float32 threshold avoids widening)
- Result: 595/595 tests green WITHOUT bypass, mypy strict 0 errors, ruff clean
- consensus.md ratified at .planning/phases/04-geometry-v1/04-3ki-review/consensus.md
- Wiki: discussions/2026-04-09-phase-04-wave5-codereview.md + discussions/2026-04-09-phase-04-summary.md
- Phase 4 Geometry-v1: COMPLETE. All 7 plans, 22 tasks, 595 tests, GEO-01..07 requirements covered.

## [2026-04-09] phase-04 | Wave 4 — Observability Gates + Nyquist dims 6/7/8 + Wiki Mirror

- geometry/debug.py: AEROCLOUD_DEBUG_GEO dump (D-47) — mask.png, sdf_heatmap.png (lazy matplotlib R-7), spiral_trace.png, placement.json, env.json
- geometry/metrics.py: structlog logger + 3 OTel counters (sdf_cache_hits/misses, dropped_words) + 2 histograms (sdf_build_seconds, placement_seconds) (D-48, D-49)
- sdf_cache.py wired: hits/misses counters + sdf_build_seconds histogram
- placement.py wired: structlog bind (geometry_phase/word/budget_left) + placement_seconds + dropped_words counter + debug dump on failure path
- Nyquist dim 6 (determinism): test_byte_identical.py — 10-run byte-identity, clear_cache() between runs, wall_clock_ms excluded (D-45)
- Nyquist dim 7 (security): test_mask_fuzz.py — hypothesis 200 examples, random bytes to mask_from_bytes, only GeometryError may escape
- Nyquist dim 8 (performance): test_sdf_benchmark.py — pytest-benchmark, 2048x2048 SDF < 1.0s, 100-word 1024x1024 < 5.0s
- Wiki: 7 code/, 3 decisions/, 1 tests/geometry.md (11 files total — Regel 11 mandate)
- Next: Wave 5 3-KI code review per Regel 6

## [2026-04-10] nightly-research | 5 topics
- uv Python Monorepo Workspace
- PostgreSQL pgvector HNSW Index
- BERT Embeddings all-MiniLM-L6-v2
- FastAPI Async Patterns
- SVG Sanitization Security CVE

## [2026-04-11] nightly-research | 5 topics
- NP-Hard Irregular Bin Packing
- Signed Distance Field Meijster EDT
- PyTorch Autograd Graph Memory
- NVIDIA DCGM Exporter GPU Metrics
- Celery GPU Worker Pool Management

## [2026-04-12] nightly-research | 5 topics
- Signed Distance Field Meijster EDT
- PyTorch Autograd Graph Memory
- SVG Sanitization Security CVE
- FastAPI Async Patterns
- Sentence Transformers Library

## [2026-04-12] phase-05 | Renderer-v1 Plans 01-03 complete

- Plan 05-01: Renderer package scaffold — `_sprites.py` SPRITE_CACHE + FONT_REGISTRY with RLock, `register_glyph()` uint8->float32/255 tensor (1,1,H,W), `clear_caches()`, conftest autouse fixture, 13 unit tests, psutil to gpu optional-deps
- Plan 05-02: DifferentiableRenderer — `_renderer.py` with packed (N,4) nn.Parameter, `forward(h,w) -> Tensor[1,1,H,W]`, affine_grid+grid_sample (align_corners=False), alpha-over compositing, rotation clamping, 19 unit tests (RED->GREEN TDD)
- Plan 05-03: Test pyramid completion — 7 hypothesis property tests, 3 Phase4->Phase5 integration tests, 3 determinism tests (byte-identical D-18), 3 RSS/leak tests (<50 MiB D-20). Total: 48 tests, all pass on CPU. 2 plan template bugs auto-fixed (Rule 1): DropReason.OUTSIDE_MASK -> NO_FEASIBLE_ANCHOR, set_seed warn_only kwarg removed
- Requirements satisfied: REND-01, REND-02, REND-03, REND-04, REND-05, REND-06

## [2026-04-12] phase-05 | 3-KI Review + Wiki Update (Plan 04)

- Claude self-review completed: APPROVED. S-1..S-8 all pass. L-1..L-8 all pass. A-1..A-5 all pass.
- Deferred items: D-DEFER-01 N upper bound guard (Phase 12), D-DEFER-02 align_corners coordinate correction (Phase 6/7)
- Codex + Gemini reviews: PENDING (external tools not available in auto mode — prompts preserved in 05-3ki-review/)
- New wiki files: wiki/code/renderer-differentiable.md, wiki/knowledge/phase-5-renderer-design.md, wiki/discussions/2026-04-12-phase-5-codereview.md, wiki/discussions/2026-04-12-phase-5-summary.md
- Phase close-out gate: all 3 reviewers must APPROVE before ROADMAP.md update (Jens confirmation required)

## [2026-04-13] nightly-research | 5 topics
- Coarse-to-Fine Optimization Pipeline
- testcontainers Python Integration Tests
- Alembic pgvector Migrations
- Celery GPU Worker Pool Management
- Self-Play Training QD Archive
- Failures: 1

## [2026-04-14] nightly-research | 5 topics
- CUDA 12 PyTorch Compatibility Matrix
- 5-Stage Collision Hierarchy
- Seam Carving Word Cloud Whitespace
- safetensors Model Checkpoints Security
- Pareto-Front Hypervolume CQD_HV

## [2026-04-14] phase-06 | Inner Loop-v1 Plans 01-04 complete

- Plan 06-01: Inner loop scaffolding — 4-part composite loss (L_wmse + L_overlap + L_fidelity + L_temporal), compute_additive_density SUM-compositing helper, rolling-window convergence detection, Pydantic models (LossWeights, InnerLoopConfig, OptimizationResult). 38 unit tests, mypy strict clean, ruff clean.
- Plan 06-02: InnerLoop class — Coarse-to-Fine optimization pipeline, Adam with gradient clipping, _build_stage_schedule filtering, _downsample_sdf bilinear, warm-start per stage. 5 integration tests. Total: 43 tests.
- Plan 06-03: Test pyramid completion — 7 hypothesis property tests (NaN-freedom, value bounds), 3 determinism tests (10-run identity), 3 memory tests (RSS < 50 MiB, tensor count, float hygiene). Total: 56 tests. All ROADMAP success criteria 3/4/5 satisfied.
- Plan 06-04: 3-KI code review + wiki documentation:
  - Phase exit gates passed: 56 tests green, mypy strict 0 errors, ruff check+format clean
  - Ruff pre-existing issues fixed (unused imports, import sort, B905, F841) in test files from Plans 01-02
  - Claude self-review: APPROVED. S-1..S-8 all pass, L-1..L-8 all pass, A-1..A-5 all pass. 9 low-severity findings documented. Blueprint math verified.
  - Codex + Gemini review prompts prepared (full source included)
  - Wiki: 2 code docs (optimizer-inner-loop.md, optimizer-loss-functions.md), 1 knowledge doc (phase-6-inner-loop-design.md), 1 discussion doc (2026-04-14-phase-6-codereview.md)
  - Phase close-out checkpoint: awaiting Jens approval + Codex/Gemini external reviews

- Requirements satisfied: INNER-01..INNER-10 (all)
- Total optimizer tests: 56 (>= 35 D-22 requirement)
- ROADMAP success criteria: 1 (8px convergence), 3 (NaN-freedom), 4 (RSS stable), 5 (determinism) — all satisfied

## [2026-04-15] nightly-research | 5 topics
- BOP-Elites Bayesian Optimization
- POT Python Optimal Transport Library
- SAT Separating Axis Theorem
- Medial Axis Transform scikit-fmm
- 4-Part Loss Function Word Placement
- Failures: 2
