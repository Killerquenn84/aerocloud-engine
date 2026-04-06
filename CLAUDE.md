# CLAUDE.md — AeroCloud Engine Regelwerk

> Diese Datei wird von Claude Code bei jedem Start automatisch geladen.
> Alle Regeln sind VERBINDLICH. Keine Ausnahmen.
> **Repo**: https://github.com/Killerquenn84/aerocloud-engine
> **Server**: /var/www/wordcloud-app-v2/server/aerocloud-engine
> **Telegram Chat-ID Jens**: 5697986530
> **Bot**: @AeroSuperEngineBot

---

## 1. ABSOLUTE PFLICHT: DISKUSSION VOR CODE

**Hoechste Prioritaet. Keine Ausnahme.**

- Wenn Jens eine Nachricht/Idee/Fix/Code/Snippet schickt → SOFORT `team_discuss` starten
- Alle 3 KIs (Claude, Gemini, ChatGPT) analysieren unabhaengig
- Diskussion bis **echter Konsens** — kein Rundenlimit, `max_rounds: 99`
- Erst nach Konsens Code schreiben
- Nach dem Code nochmal `team_discuss` Review
- Erst nach Review-Konsens committen

**VERBOTEN:** "Ich starte die Implementierung" bevor diskutiert wurde

---

## 2. AUTONOMIE-REGELN

### Innerhalb des Projekts — volle Autonomie:
- Dateien lesen/erstellen/bearbeiten/loeschen
- Tests, Build, npm install, Git-Operationen
- Multi-AI Router Tools (`ask_all`, `compare`, `pipeline`, `team_discuss`, `peer_review`, `consult`)
- Keine Permission-Fragen (`--dangerously-skip-permissions`)

### Ausserhalb des Projekts — Bestaetigung erforderlich:
- SSH, git push/pull, GitHub API, externe Zugriffe
- Detailliert erklaeren: warum, welche Daten, welches Risiko
- Auf Bestaetigung warten

---

## 3. TELEGRAM-KOMMUNIKATION

```
JEDE Frage an Jens ueber Telegram senden (chat_id: 5697986530)
JEDE Statusmeldung ueber Telegram
NIEMALS im Terminal auf Input warten ohne per Telegram zu fragen
BMAD-Workflow Fragen (z.B. [C] Continue) per Telegram weiterleiten
Zwischenstatus bei >2 Minuten Arbeit
Keine lokalen Dateipfade als Links — Inhalt direkt senden oder GitHub-Link
Kompletten MD-Inhalt jeder geschriebenen Datei per Telegram senden
```

---

## 4. 3-KI TEAM-KOLLABORATION

**Prinzip: Team-Entscheidungen, keine Einzelleistung**

- Alle 3 KIs als gleichberechtigtes Team
- Eigene Recherche zuerst — jede KI recherchiert selbststaendig
- Alle 3 teilen Ansichten — auch Claude Code muss eigene Analyse einbringen
- Detaillierte Diskussion — Positionen mit Gruenden, Gegenargumente, Kompromisse
- Konsens dokumentieren in `docs/ai-team-decisions.md`
- Vor jeder Arbeit `ai-team-decisions.md` lesen
- Entscheidungen nur durch neue 3-KI-Diskussion revidierbar

---

## 5. ARBEITSWEISE PRO AUFGABE (Step fuer Step)

- Innerhalb eines Steps: Komplett autonom (keine Rueckfragen fuer Dateien)
- Nach jedem Step: Kompletter MD-Inhalt per Telegram + auf Jens' Bestaetigung warten
- Zwischen Steps: Nicht alle auf einmal, sondern Step fuer Step

### Pro Epic/Feature:
1. Advanced Elicitation (alle 50 Methoden)
2. Party Mode mit BMAD-Agenten (PM, Architect, Analyst, QA, UX)
3. `team_discuss` mit Claude + Gemini + ChatGPT (3-KI prueft BMAD-Ergebnisse)
4. Zurueck an Party Mode zur Finalisierung

---

## 6. CODE-REVIEW: 3-DAUMEN-PRINZIP

Keine Einzelbewertungen — echte Diskussion:

1. **Claude Code Self-Review** (kritisch, als waere er ein anderer Reviewer)
2. **Gemini Review** (Performance + Security)
3. **ChatGPT Review** (UX + Edge Cases)
4. Alle 3 diskutieren gemeinsam via `team_discuss`
5. Jeder muss auf Argumente der anderen eingehen
6. Bei Dissens: weiterdiskutieren bis Konsens oder Eskalation an Jens
7. **Alle 3 muessen APPROVED geben**

---

## 7. ANTI-SYCOPHANCY-PROTOKOLL

Bei jedem Review:

- Aktiv nach Schwachstellen suchen — nicht nur ob offensichtlich falsch
- "Das sieht gut aus" **verboten** ohne konkrete Begruendung
- Zustimmen erst nachdem Gegenfall aktiv gesucht wurde
- Sycophancy-Self-Check: "Stimme ich zu weil ich ueberzeugt bin — oder weil es einfacher ist?"

### Pflicht-Fragekatalog:
- **S-1 bis S-8:** Security Checks (Injection, XSS, CSRF, Auth, Secrets, SSRF, Path Traversal, DoS)
- **L-1 bis L-8:** Stability Checks (Error Handling, Resource Leaks, Race Conditions, Timeouts, Memory, Retry Logic, Graceful Degradation, Logging)
- **A-1 bis A-5:** Architecture Checks (SRP, DRY, Coupling, API Contract, Backwards Compatibility)

---

## 8. TEST-VORGABEN (BINDING Policy)

```
Tests sind Gesetze — werden NIEMALS an den Code angepasst
Kommissionsverfahren bei Testversagen (3 KIs + Jens einstimmig)
```

### 10 Teststrategien:
1. Static Analysis (TypeScript strict, ESLint)
2. Unit Tests (FIRST Principles — Fast, Isolated, Repeatable, Self-validating, Timely)
3. Negative/Boundary Tests (mindestens so viele wie Happy-Path)
4. Integration Tests
5. E2E Tests
6. Property-Based Tests (fast-check)
7. Mutation Tests (StrykerJS) — Score < 50% auf kritischen Modulen blockiert Merge
8. Security Tests (DSGVO + OWASP)
9. Performance Tests
10. Determinism Tests

### CI-Enforcement: 10 Stufen, 8 blockierend
### DSGVO Canary-Tests auf allen User-Input-Pfaden

---

## 9. BMAD-METHOD COMPLIANCE (v6.2.2)

- **Conventional Commits:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **PR Size:** 200-400 Zeilen ideal, max 800
- **Ein Feature/Fix pro PR**
- BMAD Skills nutzen: `bmad-help`, `bmad-create-architecture`, `bmad-code-review`, `bmad-dev-story`, `bmad-sprint-planning`
- 14-Tage Auto-Update: Server Cron + Remote Trigger prueft npm-Version
- `npm run validate:refs` vor jedem Commit fuer BMAD-Dateien

---

## 10. SPRACH-REGELN

| Kontext | Sprache |
|---|---|
| **Codebase** | Immer Englisch (Code, Kommentare, Commits, Tests, API, Docs) |
| **KI-Prompts** | Englisch an Gemini/ChatGPT |
| **Telegram an Jens** | Immer Deutsch |
| **ai-team-decisions.md** | Diskussionen Englisch, Zusammenfassung fuer Jens Deutsch |

---

## 11. KNOWLEDGE WIKI (Karpathy LLM Wiki Pattern)

- Vor jeder Arbeit: `wiki/index.md` lesen
- Wiki-Schema: Siehe `AGENTS.md`
- **Nightly Deep Research:** 2:00-5:00 AM Berlin — Internet durchsuchen, Wiki aktualisieren
- Wissen waechst exponentiell — kein Kontextverlust

### Drei Schichten:
```
raw/sources/    → Unveraenderliche Quelldokumente
wiki/           → LLM-generierte Markdown-Seiten
CLAUDE.md       → Schema (dieses Dokument)
```

### Wiki-Befehle:
```bash
npm run wiki:ingest raw/sources/neue-quelle.md
npm run wiki:query "suchbegriff"
npm run wiki:lint
```

---

## 12. MVP PRODUCTION-HARDENING

- Node.js CVE-Tracking (gepinnt in `.nvmrc`)
- Fastify v5 Pflicht (Launch-Blocker)
- JSON-Depth-Limit, bodyLimit, `additionalProperties: false`
- Health-Endpoints: `/health` (public), `/health/internal` (authentifiziert)
- CORS: Kein CORS (Server-to-Server only)
- Graceful Shutdown (SIGTERM → drain → exit)
- PM2 als alleiniger Process-Manager
- Core-Dumps deaktiviert (`ulimit -c 0`)
- Pre-MVP Checklist: 85 Items in 5 Gates (Security, Runtime, Load, Webhook, DSGVO)

---

## 13. REGELN GEGEN RUECKSCHRITTE

```
Vor Code-Aenderungen: Immer ai-team-decisions.md lesen
Bei Widerspruechen: Neue Diskussion statt stillschweigend ueberschreiben
Keine Solo-Entscheidungen bei Architektur/Design
Recherche-Pflicht: Eigene Analyse, nicht nur anderen zustimmen
```

---

## Engine-Module

```
src/nlp/         → TF-IDF-AP, Tokenisierung, BERT-Embeddings
src/geometry/    → SDF, MAT, Quadtree, Kollisionserkennung
src/renderer/    → Differentiable Rendering, Soft-Rasterization
src/optimizer/   → Adam, CQD-Metrik, MAP-Elites, BOP-Elites
src/export/      → Seam Carving, Bezier-Export, SVG/PDF
```

---

## Tech-Stack

```
Runtime:        Node.js 22 LTS, TypeScript 5.7+, ESM only
Framework:      Fastify v5
Test:           Vitest + StrykerJS + fast-check + Playwright
NLP:            natural, compromise (spaeter: sentence-transformers)
Rendering:      Canvas API (spaeter: PyTorch/CUDA)
Process:        PM2
Wiki-Tools:     tsx scripts (ingest, query, lint)
BMAD:           v6.2.2 (Core + BMM)
```

---

> **Goldene Regel:** Diskutieren → Konsens → Implementieren → Review → Konsens → Committen
