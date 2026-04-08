---
title: Session Handover — Phase 3 Wave 2 complete
slug: 2026-04-08-1630-session-handover
created: 2026-04-08
tags: [handover, phase-3, wave-2, nlp]
---

# Session Handover — 2026-04-08

## Erledigt in dieser Session

**Phase 3 Wave 2 — NLP heavy-dep layer** (spaCy + lingua + stopwords)

### Design-Konsens (3-KI)
Gemini + Codex reviewed before any code was written. Codex blockierte 4 Schwaechen im ersten Entwurf:
1. `stopwordsiso` PyPI package ist tot (letzter Release 2020-09) -> spaCy `Defaults.stop_words` stattdessen
2. `dict` cache ohne Lock ist nicht thread-safe -> `threading.RLock` + double-check
3. `MagicMock` auf Doc/Token zu fragil -> `spacy.blank('en'/'de')` liefert echte Doc-Objekte in Tests
4. `lingua-language-detector>=2.2` scheiterte an py311 (cp312+ wheels only) -> pin auf `>=2.1,<2.2`

Diskussion: `wiki/discussions/2026-04-08-phase-03-wave-2-design.md`

### Neue Module (packages/engine/src/aerocloud/nlp/)
- `tokenize.py` — spaCy adapter, lazy per-language registry (`dict` + `RLock`), `MissingSpacyModelError` fail-fast, no auto-download, stem-fallback to lowercased surface (keeps `spacy.blank`-based tests hermetic)
- `language.py` — lingua LanguageDetectorBuilder restricted to EN+DE, lazy RLock singleton, confidence threshold with `'und'` fallback, empty-string short-circuit
- `stopwords.py` — direct access to `spacy.lang.{en,de}.stop_words.STOP_WORDS`, case-insensitive, unknown languages return empty set

### Tests
- `tests/unit/test_nlp_wave2.py` — 20 neue Tests (stopwords 6, tokenize 10 inkl. 10-thread race test auf Cold-Cache, lingua detect 4)
- Alle hermetisch: keine Netzwerkzugriffe, keine Modell-Downloads, spacy.load wird per `patch()` auf `spacy.blank` umgelenkt

### Verification
- pytest: **76/76** green (56 prior + 20 new)
- mypy --strict: **0 errors** in 24 source files
- ruff check: **clean**

### Dependency-Aenderung
- `packages/engine/pyproject.toml` [nlp] extra: `+ lingua-language-detector>=2.1,<2.2` (Kommentar: Upgrade tracked wenn Python 3.12)
- `pyproject.toml` (root) ruff tests ignore: `+ ARG002` (Fixture-Arguments die nur den spacy.load-Patch aktivieren, nicht im Test-Body referenziert)

## Offene Punkte Phase 3

**Wave 3 — Pipeline orchestrator** (noch nicht gestartet):
- `nlp/pipeline.py`: `text_to_candidates(text, max_words) -> list[WordCandidate]`
- Integration-Test mit *echtem* spaCy-Modell (opt-in marker, braucht `python -m spacy download en_core_web_sm` im Dev-Setup)
- Verdrahtet detect_language -> get_nlp -> tokenize -> tfidf -> zipf -> WordCandidate

**Wave 4 — Verification + merge to main:**
- Phase Exit Gate Checkliste (Gate 7 points)
- Code-Review 3-Daumen-Prinzip (Claude self + Codex + Gemini)

## Known Limitations (Wave 2)
- Gemischte Sprachen (DE/EN im selben Text): dokumentweit "best effort", low-confidence wird `'und'` -> v2 kann satz-weise detektieren
- Nur DE + EN im Scope, andere Sprachen sind `UnsupportedLanguageError`
- Modelle muessen extern via `python -m spacy download` installiert werden (kein Auto-Download — CI-safe)

## Naechste Session startet mit
1. `bash scripts/telegram-send.sh` Start-Meldung (Session-Reset lifecycle)
2. Lies dieses Handover + `wiki/log.md` letzte Eintraege
3. Wave 3 beginnen: `nlp/pipeline.py` + Integration-Test marker

## Git State am Session-Ende
- Commit mit allen Wave-2-Aenderungen (siehe `git log --oneline -5`)
- Branch: `main`, ahead of origin (kein push ohne Jens' OK per Regel 6)
