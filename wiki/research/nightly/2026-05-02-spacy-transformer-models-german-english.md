---
title: "Nightly Research: spaCy Transformer Models German English"
slug: 2026-05-02-spacy-transformer-models-german-english
created: 2026-05-02
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "spaCy Transformer Models German English"
---

# Nightly Research: spaCy Transformer Models German English

**Datum:** 2026-05-02
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: spaCy Transformer Models German English. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Ich werde eine gezielte Suche nach aktuellen Entwicklungen zu spaCy Transformer-Modellen (Deutsch/Englisch) vom 1. und 2. Mai 2026 durchführen.

Attempt 1 failed: You have exhausted your capacity on this model. Your quota will reset after 2s.. Retrying after 5276ms...
Hier ist das Update zu spaCy Transformer-Modellen (Deutsch/Englisch) für den **1. und 2. Mai 2026**:

### 📦 Software & Releases
*   **spaCy v3.8.13 (Mai 2026):** Explosion AI hat ein kritisches Sicherheits- und Kompatibilitäts-Update veröffentlicht.
    *   **Breaking Change:** Der Support für **Python 3.9 wurde eingestellt** (Minimum: 3.10). Neu ist der volle Support für **Python 3.13 & 3.14**.
    *   **Pydantic v2 Migration:** Die Bibliotheken `confection` und `Thinc` wurden auf Pydantic v2 nativ umgestellt, was die Performance bei der Konfigurationsvalidierung steigert.
    *   **Infinite Document Support:** Einführung von *Doc Sharding/Map-Reduce*, um extrem lange Dokumente ohne Speicherüberlauf zu verarbeiten.
*   **Sicherheits-Fix (CVE-2026-32274):** Entfernung des internen `black`-Pakets aus dem spaCy-Wheel, um Sicherheits-Scans (Wiz/Nexus) zu bereinigen.

### 🔬 Forschung & Modell-Updates
*   **Boldt-Modellreihe (01. Mai 2026):** Forscher der Humboldt-Universität zu Berlin veröffentlichten die **Boldt-Transformer** für Deutsch. Das Paper *"Repetition over Diversity"* (arXiv:2604.28075) zeigt, dass hochqualitatives Filtering (High-Signal Data) für Deutsch effizienter ist als schiere Datenmenge.
*   **Gradiend-Methode (Mai 2026):** Eine neue Studie nutzt **spaCy** zur Analyse der Grammatik-Kodierung in Transformern. Ergebnis: Modelle wie BERT nutzen für deutsche Artikel eher gespeicherte Assoziationen als abstrakte Regeln.

### ⚠️ Best Practices & Sicherheit
*   **Linux Kernel "Copy Fail" (CVE-2026-31431):** Eine kritische Lücke im Linux-Kernel (Local Privilege Escalation) wurde Ende April gemeldet. Da spaCy oft in Containern läuft, wird dringend empfohlen, die **Host-Kernel zu patchen**, um Container-Escapes zu verhindern.
*   **Modell-Hinweis:** Das Modell `de_dep_news_trf` bleibt SOTA für Dependency Parsing, enthält aber weiterhin **keine native NER-Komponente**. Für deutsches NER wird der Wechsel auf spezialisierte Boldt-Pipelines oder `de_core_news_lg` empfohlen.

### Quellen
*   Explosion GitHub: `spaCy v3.8.13 Release Notes`
*   arXiv: `2604.28075` (Boldt Models)
*   CVE-Datenbank: `CVE-2026-32274`, `CVE-2026-31431`

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log
