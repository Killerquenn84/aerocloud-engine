---
title: "Nightly Research: Hypothesis Property-Based Testing"
slug: 2026-05-04-hypothesis-property-based-testing
created: 2026-05-04
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "Hypothesis Property-Based Testing"
---

# Nightly Research: Hypothesis Property-Based Testing

**Datum:** 2026-05-04
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: Hypothesis Property-Based Testing. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Hier ist das Update zu **Hypothesis Property-Based Testing** für AeroCloud Engine (Stand: 4. Mai 2026).

### Status: Gestern & Heute (3.–4. Mai 2026)
Es gibt **keine neuen Releases** seit gestern. Die Entwicklung auf GitHub ist jedoch aktiv:
*   **PR #4721 (04.05.2026):** Umstellung des PyPI-Deployments auf **Trusted Publishing** zur Erhöhung der Supply-Chain-Sicherheit.
*   **PR #4718 (Aktiv):** Optimierung der `Phase.explain`-Logik. Ziel ist es, gezielte (targeted) Kandidaten vor dem Zufalls-Sampling zu testen, um Fehlerursachen deterministischer zu erklären.

### Wichtigste Neuerungen seit April 2026

**1. Library & Features:**
*   **Hypothesis 6.152.4 (27.04.2026):** Aktueller Stable-Release. Fix für einen seltenen Fehler in `Phase.explain` bei komplexen Strategien (Issue #4708).
*   **Auto-Gitignore (14.04.2026):** Hypothesis erstellt nun automatisch eine `.gitignore` im `.hypothesis/`-Verzeichnis, um zu verhindern, dass lokale Test-Caches versehentlich committet werden (v6.152.0).
*   **Verbessertes Pretty-Printing (24.04.2026):** Bei Testfehlern werden nun bevorzugt die `repr`-Werte der generierten Daten statt der komplexen Code-Ausdrücke ihrer Erzeugung angezeigt.

**2. Forschung & Ökosystem:**
*   **The Hypothesis Corpus (14.04.2026):** Veröffentlichung eines Datensatzes mit **28.928 Hypothesis-Tests** aus über 1.500 Repositories durch Liam DeVoe. Dies dient dem Training von KI-Modellen zur automatisierten Testgenerierung.
*   **Paper: "Finding bugs across the Python ecosystem with Claude and property-based testing" (April 2026):** Maaz et al. beschreiben, wie LLM-Agenten Properties autonom aus Docstrings ableiten und Hypothesis-Tests für Core-Bibliotheken wie NumPy und Pandas schreiben.

**3. CVEs & Sicherheit:**
Es gibt **keine direkten CVEs** für Hypothesis. Die Library war jedoch maßgeblich an der Entdeckung kritischer Lücken beteiligt:
*   **CVE-2026-31431 (April 2026):** Eine High-Severity-Lücke im Linux-Kernel (Crypto-Subsystem) wurde mittels KI-gestütztem Hypothesis-Testing identifiziert.
*   **CVE-2026-33155 (März/April 2026):** Eine DoS-Schwachstelle in `DeepDiff`, nachgewiesen durch PBT-Prinzipien.

**Quellen:**
*   [Hypothesis Changelog](https://hypothesis.readthedocs.io/en/latest/changelog.html)
*   [GitHub Commits/PRs](https://github.com/HypothesisWorks/hypothesis/pulls)
*   DeVoe, L. (2026): *The Hypothesis Corpus* (Dataset on GitHub/HuggingFace)
*   Maaz et al. (2026): *Finding bugs across the Python ecosystem...* (Research Paper)

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log
