# Project State: AeroCloud Engine

**Last updated:** 2026-04-09 after Phase 4 CONTEXT.md gathered (3-KI adversarial)
**Active milestone:** v1 — Full Blueprint Realization
**Active phase:** Phase 4 — Geometry-v1 (CONTEXT.md locked, awaiting `/gsd-plan-phase 4`)

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-07)

**Core value:** Mathematically optimal word placement in arbitrary silhouettes through GPU-accelerated differentiable optimization, exploring the entire continuous solution space (Quality-Diversity).

**Current focus:** Phase 4 — Geometry-v1 (CONTEXT.md locked 2026-04-09, next step `/gsd-plan-phase 4`)

## Roadmap Summary

12 phases, all in v1, full Blueprint realization. See `.planning/ROADMAP.md`.

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation | ✅ Complete (commit f141d86) |
| 2 | Datenmodell + Wiki | ✅ Complete (commit b770f57) |
| 3 | NLP-v1 | ✅ Complete (Wave 1 cced714, Wave 2 454ee36, Wave 3 beba7c4, Wave 4 hardening pending commit) |
| 4 | Geometry-v1 | 🟡 Context locked (51 decisions, 3-KI adversarial Codex BLOCKED-then-redesigned G-3/G-4/G-5) |
| 5 | Renderer-v1 | ⏸ Pending |
| 6 | Inner Loop-v1 | ⏸ Pending |
| 7 | Geometry-v2 | ⏸ Pending |
| 8 | Semantic Vector Space | ⏸ Pending |
| 9 | Outer Loop-v1 | ⏸ Pending |
| 10 | Self-Play | ⏸ Pending |
| 11 | Outer Loop-v2 | ⏸ Pending |
| 12 | Production v1 | ⏸ Pending |

## Requirements Coverage

109 v1 requirements, 100% mapped to phases. See `.planning/REQUIREMENTS.md`.

## Research Status

Complete. See `.planning/research/`:
- `STACK.md` — Codex-verified library versions
- `FEATURES.md` — Blueprint mapped to maturity levels
- `ARCHITECTURE.md` — Polyglot best practices
- `PITFALLS.md` — 18 known risks with mitigations
- `SUMMARY.md` — Synthesis + cross-cutting risks

## Configuration

See: `.planning/config.json`

- Mode: YOLO
- Granularity: Fine (12 phases)
- Parallelization: enabled
- Git tracking: enabled
- Workflow: Research + Plan Check + Verifier + Nyquist Validation enabled
- Model profile: Balanced (Sonnet)

## Workflow Notes

- 3-AI team workflow per CLAUDE.md: Claude (orchestrator + code), Gemini (research), Codex (review)
- Research uses `gemini -p`, code review uses `codex exec --skip-git-repo-check`
- All phase progress reported to Jens via `bash scripts/telegram-send.sh`
- Phase exit gates: tests + types + lint + wiki + benchmark + 3-AI review

## Next Action

`/gsd-plan-phase 4` — plan waves for Phase 4 Geometry-v1 based on 51 locked decisions in `.planning/phases/04-geometry-v1/04-CONTEXT.md`

## Phase 3 Known Limitations (carried into v2)

Documented in `wiki/discussions/2026-04-08-phase-03-wave-4-codereview.md`:
- **N-2 mixed-language detection** — `language='auto'` picks one spaCy pipeline
  for the whole document; mixed DE/EN inputs are mis-scored. Mitigation:
  callers can pass an explicit `language='en'`/`'de'`. Sentence-level detection
  is deferred to v2.
- **N-3 casing/spelling collapse** — `_pick_display_surface` picks the most
  frequent surface form per stem, so `'API'` (count 2) loses to `'api'`
  (count 3). Acceptable for v1; v2 will add a casing-preference heuristic.
- **N-4 title double-counting** — title tokens contribute to corpus counts
  AND to positional signals; small overcount on title-heavy texts.
- **N-5 stem-alphabetical tiebreak** — deterministic but feels arbitrary in
  rendered clouds; may switch to surface-alphabetical in v2.
- **spaCy models must be installed manually** — `python -m spacy download
  en_core_web_sm de_core_news_sm` is a Dev/CI setup task per Codex Q5
  (no auto-download because that breaks reproducibility).

---
*State initialized: 2026-04-07*
*Phase 3 complete: 2026-04-08*
