---
title: "Medial Axis Transform (MAT)"
tags: [medial-axis, skelett, topologie, multi-centric, wordle]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
---

# Medial Axis Transform (MAT)

## Definition

Der Medial Axis Transform berechnet das **topologische Skelett** einer Silhouette - die Menge aller Punkte, die mehr als einen naechsten Punkt auf der Kontur besitzen.

## Komponenten

### Hauptachsen
- Laengste zusammenhaengende Skelett-Pfade
- Definieren die primaere Ausrichtung der Silhouette
- Bestimmen die Hauptrichtungen fuer die Wort-Platzierung

### Lokale Breiten
- An jedem Skelett-Punkt: Abstand zur naechsten Kontur (= SDF-Wert)
- Gibt die **maximal moegliche Wortgroesse** an dieser Position an
- Schmale Stellen = kleine lokale Breite = nur kleine Woerter

### Verbindungsknoten
- Verzweigungspunkte des Skeletts
- Markieren Uebergaenge zwischen Form-Segmenten
- Wichtig fuer die Segmentierung der Silhouette

## Multi-Centric Wordle

Fuer **nicht-konvexe Silhouetten** (z.B. Stern, Buchstabe, Tier) reicht ein einzelner Startpunkt nicht aus:

### Problem
- Klassisches Wordle: Ein Zentrum, spiralfoermige Expansion
- Bei nicht-konvexen Formen bleiben Arme/Auslaufer leer
- Beispiel: Bei einem Stern wuerden die Zacken nicht gefuellt

### Loesung: Multi-Centric Wordle
1. **MAT berechnen** - Skelett der Silhouette extrahieren
2. **Segmentierung** - Silhouette in konvexe Sub-Regionen teilen (an Verbindungsknoten)
3. **Zentren bestimmen** - Pro Segment den tiefsten SDF-Punkt als Zentrum
4. **Parallele Spiral-Suchen** - Jedes Segment hat eigenen Startpunkt
5. **Optimal Transport** - Semantische Cluster den Segmenten zuordnen

### Vorteile
- Gleichmaessige Befuellung auch komplexer Silhouetten
- Grosse Woerter in breiten Bereichen, kleine in schmalen
- Semantisch kohaerente Gruppierung pro Segment

## Berechnung

```python
# Skelettierung via morphologische Operationen
skeleton = skimage.morphology.skeletonize(binary_mask)

# Oder via Voronoi-basiertem MAT
mat = medial_axis(binary_mask, return_distance=True)
skeleton, distance = mat
```
