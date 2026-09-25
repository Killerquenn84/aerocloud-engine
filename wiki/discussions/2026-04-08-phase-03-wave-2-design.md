---
title: Phase 3 Wave 2 — 3-KI Design Diskussion
slug: 2026-04-08-phase-03-wave-2-design
created: 2026-04-08
tags: [phase-3, wave-2, nlp, spacy, lingua, stopwords, discussion]
phase: 03-nlp-v1
participants: [claude, gemini, codex]
---

# Phase 3 Wave 2 — Design-Diskussion (3-KI Konsens)

**Datum:** 2026-04-08
**Ziel:** Design fuer Wave 2 vor jeglicher Implementierung festzurren (Regel 1).

## Ausgangslage

Wave 1 liefert bereits ausgeliefert:
- `nlp/tfidf.py` (TF-IDF-AP, numpy)
- `nlp/zipf.py` (log-normalization)
- `nlp/corpus_guard.py` (fallback < 20 tokens)
- 22 Unit-Tests gruen, mypy strict 0 Errors

Wave 2 Module laut `03-PLAN.md`:
- `nlp/tokenize.py` — spaCy wrapper + stem/surface mapping
- `nlp/language.py` — lingua wrapper
- `nlp/stopwords.py` — per-language filter
- Tests mit mock spaCy

## Claude Initial-Fragen (10 Punkte)

Siehe Prompt in Session-Transkript. Kurz: Cache-Strategie, Mocking, Versionen, Deadness-Check stopwords-iso, Auto-Download, Fixtures, Reihenfolge, Thread-safety, Mixed-Lang, mypy+spaCy.

## Gemini Empfehlungen (Initial Research)

| Frage | Gemini Empfehlung |
|---|---|
| Q1 Stopwords | `stopwords-iso` statt spaCy builtin (Konsistenz, Determinismus) |
| Q2 Cache | `get_nlp(lang)` Registry mit dict-cache (Testbarkeit) |
| Q3 Mock | MagicMock auf `spacy.load`, simuliert Doc/Token |
| Q4 Lang-Detect | lingua bleibt (unerreicht bei Short-Text) |
| Q5 API | `lang='auto'` als Default |

## Codex Adversarial Review (mit Websuche)

Codex hat live gegen PyPI + GitHub gecheckt und **4 Schwaechen im Gemini-Plan** entlarvt:

### 1. dict cache schlaegt lru_cache NICHT ohne Lock
- `lru_cache` hat internes Locking; nacktes dict ist nicht thread-safe.
- Fuer spaetere Celery-Worker noetig: `threading.RLock` um Cache-Miss-Init.
- **Konsens-Fix:** dict cache **mit** `RLock` + expliziter `clear_registry()` fuer Tests.

### 2. MagicMock auf spacy.load ist fragil
- Mocks lassen Duck-Type-Fehler durch.
- **Besser:** `spacy.blank("en")` / `spacy.blank("de")` als echte Doc-Quelle + nur `spacy.load` patchen.
- **Konsens-Fix:** Wave-2-Tests verwenden `spacy.blank()` fuer echte Doc-Objekte.

### 3. stopwords-iso (stopwordsiso auf PyPI) ist TOT
- Letzter Release 2020-09-02, `Development Status :: 3 - Alpha`.
- Datenrepo lebt noch, Python-Wrapper nicht.
- **Konsens-Fix:** NICHT stopwords-iso verwenden. Stattdessen spaCy's `Defaults.stop_words` — wir haengen ohnehin an spaCy. Speichert eine Dependency, reduziert Risiko.

### 4. lingua-language-detector Pin
- v2.2.0 am 2026-03-09 erschienen, v2.0 war Rust/API-Wechsel.
- **Konsens-Fix:** `>=2.2,<2.3` (nicht `>=2.0` offen).

### 5. Auto-Download in get_nlp() verboten
- Nicht CI-safe, nicht offline-safe, nicht reproduzierbar.
- **Konsens-Fix:** Fail-fast mit eigener `MissingSpacyModelError`. Modelle via separatem Dev-Setup-Script installieren.

### 6. Reihenfolge
- detect_language -> get_nlp(lang) -> tokenize (sequentiell, nicht parallel).
- `lang='auto'` detectet einmal pro Dokument; explizites `lang` ueberspringt Detection.

### 7. Mixed-Language
- Dokumentweit "best effort" akzeptieren in Wave 2.
- Low-Confidence fallback: `language='und'` (undefiniert) + Warnung im Log.

### 8. mypy strict + spaCy
- Keine verbreiteten spacy-stubs. `Any` leakt an spaCy-Boundaries.
- **Konsens-Fix:** Internes Protocol `TokenizerProtocol` im `tokenize.py`, `cast()`/`Any` nur an der spaCy-Grenze.

## Finaler Konsens fuer Wave 2

### Dependencies (packages/engine/pyproject.toml)

```toml
nlp = [
    "POT>=0.9.5",
    "spacy>=3.7.0,<4.0",
    "lingua-language-detector>=2.2,<2.3",
]
```

**KEINE** stopwords-iso Dependency. spaCy Defaults.stop_words nutzen.

### Module

#### `nlp/tokenize.py`
- `class MissingSpacyModelError(Exception)`
- `class TokenizerProtocol(Protocol)` — sauberes internes Interface
- `get_nlp(language: str) -> Language` — dict registry + `threading.RLock`
- `clear_registry() -> None` — fuer Tests
- `tokenize(text: str, language: str) -> list[Token]` — surface + stem + language + is_stopword
- Stem = `token.lemma_` falls vorhanden, sonst `token.text.lower()`

#### `nlp/language.py`
- `class LanguageDetector` — Lazy singleton mit `lingua.LanguageDetectorBuilder`
- `detect_language(text: str, confidence_threshold: float = 0.5) -> str` — liefert ISO-Code oder `'und'`
- Nur DE + EN in Wave 2 (v1 Scope)

#### `nlp/stopwords.py`
- `is_stopword(word: str, language: str) -> bool` — greift auf `spacy.lang.{de,en}.stop_words.STOP_WORDS` zu
- Direkt-Import, kein Modell-Load noetig
- Fallback: leere Menge fuer unbekannte Sprache

### Tests (tests/unit/test_nlp_wave2.py)

- Fixtures: 1 EN Satz, 1 DE Satz, 1 zu-kurz Fragment, 1 mixed-DE-EN Beispiel
- Tokenize-Tests nutzen `spacy.blank("en")` / `spacy.blank("de")` (keine Modelle noetig)
- Registry-Tests: patch `spacy.load` auf `spacy.blank` Return
- Thread-Safety-Test: 10 Threads rufen `get_nlp("en")` parallel — genau 1 Init
- MissingModelError-Test: patch `spacy.load` auf `OSError`
- Language-Detection-Tests: lingua (echte Lib, keine Mocks noetig — lightweight)
- Stopwords: `is_stopword("the", "en") == True`, `is_stopword("hund", "de") == True`

### Nicht in Wave 2 (deferred)

- Pipeline-Orchestrator (`nlp/pipeline.py`) — Wave 3
- Integration-Tests mit echten spaCy-Modellen — Wave 3 opt-in marker
- Compound Splitting — v2
- Mixed-Language-Handling ueber simples `und` hinaus — v2

## Status

- Claude: approved
- Gemini: approved (via initial research)
- Codex: approved (via adversarial review, alle Fixes eingearbeitet)

**Bereit fuer Implementierung.**
