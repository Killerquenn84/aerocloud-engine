---
title: "MAP-Elites und BOP-Elites"
tags: [map-elites, bop-elites, quality-diversity, self-play, escape-move]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
---

# MAP-Elites und BOP-Elites

## MAP-Elites Grid

MAP-Elites (Multi-dimensional Archive of Phenotypic Elites) unterteilt den Behaviour-Raum in ein Grid und speichert den besten Kandidaten pro Zelle.

### Behaviour-Dimensionen

| Dimension | Beschreibung | Wertebereich |
|-----------|-------------|-------------|
| **Space Similarity (SS)** | Flaechenauslastung der Silhouette | [0, 1] |
| **Rotation** | Verteilung der Wort-Rotationen | [0, 1] |
| **Symmetrie** | Grad der Layout-Symmetrie | [0, 1] |
| **Semantik** | Semantische Cluster-Kohaerenz | [0, 1] |

### Algorithmus

```
1. Initialisierung: Zufaellige Layouts generieren
2. Repeat:
   a. Zelle aus Archiv waehlen
   b. Loesung mutieren (Position, Rotation, Skalierung)
   c. Inner Loop: Adam-Optimierung (100 Epochen)
   d. Behaviour-Deskriptor berechnen
   e. Zelle im Grid bestimmen
   f. Falls besser als bisheriger Bewohner: ersetzen
```

## BOP-Elites

**Batch-Optimized Phenotypic Elites** - effiziente Variante:

- **700 Iterationen** entsprechen ca. **90.000 Evaluationen**
- Batch-Verarbeitung mehrerer Mutationen parallel auf GPU
- Deutlich effizienter als sequentielles MAP-Elites
- Konvergiert schneller bei gleicher Archiv-Qualitaet

## Naechtliches Self-Play Training

Ausserhalb der Nutzungszeiten trainiert das System autonom:

1. **Bestehende Archiv-Eintraege** als Startpopulation
2. **Intensivierte Mutation** mit groesserem Suchradius
3. **Cross-Pollination** zwischen verschiedenen Silhouetten
4. **Verbesserung der Grid-Abdeckung** in schwach besetzten Zellen
5. Ergebnisse stehen am naechsten Tag als **Warm-Start** bereit

## Escape-Move

Strategie zum Verlassen lokaler Optima:

- **Erkennung**: Loss-Plateau ueber mehrere Epochen
- **Aktion**: Gezielte starke Perturbation eines oder mehrerer Woerter
- **Varianten**:
  - Swap: Zwei Woerter tauschen Positionen
  - Kick: Ein Wort wird in ein anderes Segment verschoben
  - Reset: Teilmenge der Woerter wird neu initialisiert
- **Reoptimierung** nach dem Escape-Move ueber Inner Loop
