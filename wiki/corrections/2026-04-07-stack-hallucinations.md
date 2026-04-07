---
title: Codex Corrections — Lessons Learned aus 3-KI Stack-Review
tags: [lessons, codex, verification, anti-sycophancy, stack, versions]
source: .planning/research/STACK.md + Codex CLI Review
verified_on: 2026-04-07
slug: 2026-04-07-stack-hallucinations
created: 2026-04-07

---

# Codex Corrections — Lessons Learned

> Warum Anti-Sycophancy funktioniert: Codex entlarvte 6 von Gemini initial vorgeschlagenen Library-Versionen als Halluzinationen.
> Alle Verifikationen via Live-Web-Search gegen PyPI und offizielle Upstreams am 2026-04-07.

## Die 6 entlarvten Halluzinationen

### 1. `nvdiffrast 0.4.0` → **existiert nicht**

- **Gemini sagte:** "nvdiffrast v0.4.0"
- **Codex verifizierte:** PyPI zeigt nur **0.3.3.1** (veröffentlicht 2024-12-06)
- **NVlabs GitHub:** keine offiziellen Releases, nur Tags
- **Konsequenz:** Wir verwenden `nvdiffrast==0.3.3.1` und pinnen numpy/torch streng
- **Risiko:** Build/Runtime-Fragilität durch NVIDIA Source Code License und geringe Upstream-Offenheit

### 2. `POT 1.0.2` → **existiert nicht**

- **Gemini sagte:** "POT (Python Optimal Transport) v1.0.2"
- **Codex verifizierte:** PyPI aktuell **0.9.6.post1** (veröffentlicht 2025-09-22)
- **Konsequenz:** Wir verwenden `POT==0.9.6.post1`
- **Lesson:** Pre-1.0 Libraries niemals "auf 1.0 raten"

### 3. `spaCy 4.1` → **existiert nicht**

- **Gemini sagte:** "spaCy v4.1 mit de_dep_news_trf"
- **Codex verifizierte:** offizielle spaCy-Site zeigt weiterhin **v3.x** als current
- **Red Flag:** das war wahrscheinlich eine Halluzination oder "Wunschversion"
- **Konsequenz:** Wir verwenden `spacy` 3.x current
- **Zusätzlich (Codex-Warnung):** spaCy trf-Modelle sind schwergewichtig. Nach Phase 3 prüfen, ob ein kleineres Setup mit gezielten Transformer-Aufrufen billiger und stabiler ist.

### 4. `scikit-fmm 2025.12` → **erfundene Versionsnummer**

- **Gemini sagte:** "scikit-fmm v2025.12"
- **Codex verifizierte:** PyPI aktuell **2025.6.23** (veröffentlicht 2025-06-23)
- **Konsequenz:** Wir verwenden `scikit-fmm==2025.6.23`
- **Lesson:** Datumsbasierte Versionen (CalVer) nicht "weiterraten" — immer gegen PyPI prüfen

### 5. `svgwrite 1.5.1` → **existiert nicht + Paket inaktiv**

- **Gemini sagte:** "svgwrite v1.5.1"
- **Codex verifizierte:** PyPI aktuell **1.4.3** (veröffentlicht 2022-07-14), explizit als **inactive** markiert
- **Konsequenz:** **svgwrite komplett weggelassen** — wir nutzen `svgelements` (aktiv, gut gewartet) oder direkte XML-Erzeugung via `lxml.etree`
- **Lesson:** Inaktive Pakete sind keine Option, auch wenn sie initial "funktionieren" würden

### 6. `Next.js 14` → **überholt**

- **Gemini sagte:** "Next.js 14 (App Router)"
- **Codex verifizierte:** **Next.js 16** seit 2025-10-21 verfügbar
- **Konsequenz:** Wir verwenden Next.js 16 für Greenfield in 2026
- **Lesson:** Trainingsdaten von Gemini waren hier veraltet. Kritische Frameworks immer gegen aktuelle Docs prüfen.

## Weitere Codex-Blockierungen (keine Halluzinationen, aber Architektur-Smell)

### 7. `structlog + loguru` Hybrid

- **Gemini schlug vor:** "structlog für Production + loguru für Dev-Debugging"
- **Codex blockte:** "Zwei Logging-Abstraktionen erzeugen doppelte Handler, inkonsistente Kontextweitergabe und operativen Lärm"
- **Konsequenz:** Nur `structlog + stdlib logging`, kein loguru

### 8. `Celery` als Default für v1

- **Gemini schlug vor:** Celery für alle Async-Tasks inkl. Self-Play
- **Codex kritisierte:** "Celery ist nur sinnvoll bei komplexen Routing-/Retry-/ETA-Patterns. Für v1 ist es oft Overkill; Dramatiq oder RQ wären einfacher. Celery Beat plus 'Self-Play' klingt nach frühem Orchestrierungs-Bloat."
- **Konsequenz:** Celery 5.6.2 wird benutzt — **aber minimal konfiguriert**, nur weil Self-Play Scheduling zwingend ist (Blueprint Teil VIII). Keine Power-User-Features.

### 9. `Turborepo` im Greenfield

- **Gemini schlug vor:** "Turborepo + uv + Cargo + pnpm Monorepo"
- **Codex kritisierte:** "Turborepo nur sinnvoll, wenn apps/web wirklich ein eigenständiger JS/TS-Workspace mit eigener CI-/Build-Matrix ist. Für v1 klingt die Kombination mit FastAPI, Celery, Rust/WASM, Next, Turbo eher nach zu viel Plattform vor Produkt."
- **Konsequenz:** **Default: uv workspace + Cargo + pnpm**, Turborepo aufgeschoben bis JS-Task-Orchestrierung wirklich weh tut.

## Kritische Ergänzungen durch Codex

Was Gemini komplett vergessen hat:

1. **NumPy/PyTorch Version Pinning** — bei nvdiffrast absolut kritisch
2. **Alembic** für Datenbank-Migrationen inklusive `CREATE EXTENSION vector`
3. **Type Checking** (mypy --strict oder pyright) + Linting (ruff)
4. **OpenTelemetry Tracing** — nur Prometheus Metrics reichen nicht
5. **safetensors statt pickle** für Model Checkpoints (Security)

## Lessons Learned (Generalisierbar)

1. **Anti-Sycophancy ist essenziell.** Wenn Gemini "das übliche" sagt, muss jemand gegen PyPI verifizieren.
2. **Version-Pinning ist nicht verhandelbar** bei Dependencies mit C-Extensions (nvdiffrast, torch, numpy).
3. **"Latest" ist kein Vertrauens-Signal** — Gemini raten "nach oben" ist ein systematischer Bias.
4. **Inaktive Pakete sind technische Schuld** auch wenn sie initial funktionieren (svgwrite).
5. **Code Review muss Live-Quellen prüfen**, nicht nur "Erinnerung". Codex hat explizit Web-Search gemacht.
6. **Produkt vor Plattform** — Turborepo ist kein Default, Celery ist kein Default, Hybrid-Logger sind kein Default.

## Workflow-Konsequenz

Für alle zukünftigen Stack-Entscheidungen:

1. **Gemini** recherchiert und schlägt vor
2. **Codex** verifiziert **zwingend** gegen Live-PyPI / GitHub / offizielle Docs
3. **Claude** (Orchestrator) integriert nur die Codex-verifizierte Version in die Roadmap
4. **Wiki** (diese Datei) dokumentiert jede Abweichung für zukünftige Lessons

## Siehe auch

- [knowledge/stack-versions.md](knowledge/stack-versions.md) — die verifizierten Versionen als lebendige Referenz
- [research/stack.md](research/stack.md) — vollständige Gemini Stack Research (pre-Codex)
- [research/summary.md](research/summary.md) — Research Synthesis mit Cross-Cutting Risks
- [decisions/2026-04-07-polyglot-stack-selection.md](decisions/2026-04-07-polyglot-stack-selection.md) — Log der 3-KI Entscheidungen
