---
title: "NP-Schwere des Irregular Bin Packing"
tags: [np-hard, bin-packing, geometrie, optimierung, komplexitaet]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: np-hard-packing
created: 2026-04-07

---

# NP-Schwere des 2D Irregular Bin Packing

## Problemdefinition

Das AeroCloud-Kernproblem ist ein **2D Irregular Bin Packing**:
- Gegeben: Eine Menge gewichteter Woerter (als irregulaere Polygone) und eine Ziel-Silhouette
- Gesucht: Platzierung aller Woerter innerhalb der Silhouette ohne Ueberlappung
- Optimierung: Maximale Flaechenausnutzung bei Einhaltung semantischer Constraints

## Konvexe und nicht-konvexe Polygone

- **Woerter** bilden nicht-konvexe Polygone (Glyphen-Umrisse)
- **Silhouetten** sind beliebig geformte, oft nicht-konvexe Konturen
- Nicht-Konvexitaet erhoeht die Komplexitaet der Kollisionserkennung erheblich
- Konvexe Dekomposition als moegliche Approximation

## 3 Mathematische Disziplinen

### 1. Geometrie und Topologie
- **Signed Distance Fields (SDF)** fuer Inside/Outside-Tests
- **Medial Axis Transform** fuer topologisches Skelett der Silhouette
- **Bezier-Kurven** fuer praezise Konturdarstellung
- Konvexe Huellenberechnung und Polygon-Clipping

### 2. Kombinatorische Optimierung
- NP-Schwere bedeutet: **kein polynomieller exakter Algorithmus bekannt**
- Reduktion auf Bin Packing (klassisch NP-schwer)
- Heuristische Ansaetze: Greedy-Platzierung, Spiral-Suche, MAP-Elites
- Quality-Diversity statt reiner Best-First-Suche

### 3. Stochastische Optimierung
- **Monte-Carlo-Sampling** fuer Initialisierung und CQD-Metrik
- **MAP-Elites** als stochastischer Quality-Diversity-Algorithmus
- **Escape-Moves** um lokale Optima zu verlassen
- Rauschinjizierung fuer Exploration

## Komplexitaetsbetrachtung

| Aspekt | Komplexitaet |
|--------|-------------|
| Platzierung von n Woertern | O(n!) Permutationen |
| Kollisionspruefung (naiv) | O(n²) pro Kandidat |
| Exakte Loesung | NP-schwer (exponentiell) |
| AeroCloud Heuristik | Polynomiell pro Iteration |

## Siehe auch

- [collision-detection.md](collision-detection.md) — die 5-stufige Hierarchie loest das NP-schwere Problem pragmatisch
- [map-elites.md](map-elites.md) — Quality-Diversity als alternative Herangehensweise
- [differentiable-rendering.md](differentiable-rendering.md) — Gradienten-basierte Loesung im Inner Loop
