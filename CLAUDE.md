# CLAUDE.md – AeroCloud Engine Wiki Schema

> Dieses Dokument definiert die Struktur, Konventionen und Workflows
> fuer das LLM-Wiki der AeroCloud Engine. Es wird bei jedem Start geladen.

---

## 1. Projektkontext

- **Typ**: Self-learning Word Cloud Engine (NP-hard 2D Irregular Bin Packing)
- **Architektur**: Dual-Loop (Inner Loop: PyTorch GPU, Outer Loop: QD/MAP-Elites)
- **Ziel**: Mathematisch optimale, semantisch kohaerente Word Clouds
- **Repo**: https://github.com/Killerquenn84/aerocloud-engine
- **Server-Pfad**: Innerhalb von wordcloud-silhouette-app/server/aerocloud-engine

---

## 2. LLM-Wiki Architektur (nach Karpathy-Pattern)

### Drei Schichten

```
raw/sources/    → Unveraenderliche Quelldokumente (Papers, Blueprints, Code-Analysen)
wiki/           → LLM-generierte Markdown-Seiten (Zusammenfassungen, Entitaeten, Konzepte)
CLAUDE.md       → Schema-Datei (dieses Dokument) – steuert LLM-Verhalten
```

### Konventionen

- **Wiki-Seiten**: Markdown mit YAML-Frontmatter (title, tags, sources, updated)
- **Dateinamen**: Kebab-Case, z.B. `optimal-transport.md`, `sdf-geometry.md`
- **Cross-References**: Standard Markdown-Links `[Seite](dateiname.md)`
- **index.md**: Katalog aller Wiki-Seiten mit Einzeiler-Zusammenfassung
- **log.md**: Append-only Chronik aller Aktivitaeten

---

## 3. Wiki-Seitenformat

```markdown
---
title: Seitentitel
tags: [tag1, tag2]
sources: [quelldatei.md]
updated: 2026-04-06
---

# Seitentitel

Inhalt der Seite...

## Siehe auch
- [Verwandte Seite](verwandte-seite.md)
```

---

## 4. Workflows

### Ingest (neue Quelle verarbeiten)

1. Quelle in `raw/sources/` ablegen
2. LLM liest die Quelle vollstaendig
3. Zusammenfassungsseite in `wiki/` erstellen
4. Bestehende Entity- und Konzeptseiten aktualisieren
5. `wiki/index.md` aktualisieren
6. `wiki/log.md` Eintrag anhaengen

### Query (Wissen abfragen)

1. `wiki/index.md` lesen, relevante Seiten identifizieren
2. Relevante Wiki-Seiten lesen und synthetisieren
3. Antwort mit Zitaten aus Wiki-Seiten
4. Wertvolle Antworten als neue Wiki-Seite speichern

### Lint (Wiki-Gesundheitscheck)

1. Widersprueche zwischen Seiten finden
2. Verwaiste Seiten ohne eingehende Links identifizieren
3. Fehlende Cross-References ergaenzen
4. Luecken im Wissen aufzeigen
5. Veraltete Behauptungen markieren

---

## 5. Engine-Module

```
src/nlp/         → TF-IDF-AP, Tokenisierung, BERT-Embeddings
src/geometry/    → SDF, MAT, Quadtree, Kollisionserkennung
src/renderer/    → Differentiable Rendering, Soft-Rasterization
src/optimizer/   → Adam, CQD-Metrik, MAP-Elites, BOP-Elites
src/export/      → Seam Carving, Bezier-Export, SVG/PDF
```

---

## 6. Kernregeln

```
IMMER: Wiki-Seiten aktualisieren wenn neues Wissen entsteht
IMMER: index.md und log.md synchron halten
IMMER: Cross-References zwischen verwandten Konzepten pflegen
IMMER: YAML-Frontmatter in jeder Wiki-Seite
NIEMALS: raw/sources/ Dateien modifizieren (immutabel)
NIEMALS: Wiki-Seiten ohne Quellenangabe erstellen
NIEMALS: Widersprueche ignorieren – explizit dokumentieren
```

---

## 7. Technischer Stack

```
Runtime:        Node.js 22 LTS, TypeScript 5.7+, ESM only
Test:           Vitest
NLP:            natural, compromise (spaeter: sentence-transformers)
Rendering:      Canvas API (spaeter: PyTorch/CUDA fuer GPU Inner Loop)
Wiki-Tools:     tsx scripts (ingest, query, lint)
```
