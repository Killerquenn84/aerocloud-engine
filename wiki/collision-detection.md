---
title: "Kollisionserkennung - 5 Stufen"
tags: [kollision, aabb, quadtree, sat, bitmap, bvh, cache]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: collision-detection
created: 2026-04-07

---

# Kollisionserkennung - 5-Stufen-Pipeline

## Ueberblick

Die Kollisionserkennung prueft, ob sich platzierte Woerter ueberlappen. Eine mehrstufige Pipeline filtert von grob nach fein:

## Stufe 1: AABB (Axis-Aligned Bounding Box)

- Schnellster Test: Ueberlappen sich die achsenparallelen Bounding Boxes?
- O(1) pro Paar, extrem effizient
- Viele False Positives bei rotierten Woertern

```
Overlap = (A.left < B.right) && (A.right > B.left) &&
          (A.top < B.bottom) && (A.bottom > B.top)
```

## Stufe 2: Two-Level Box (EdWordle)

- Jedes Wort wird in ein **groeberes und feineres Box-Grid** unterteilt
- Inspiriert von EdWordle (Wang et al.)
- Reduziert False Positives der AABB-Stufe
- Beruecksichtigt die tatsaechliche Wortform besser

## Stufe 3: Quadtree

- **Raeumliche Indexstruktur** fuer effiziente Nachbarschaftsabfragen
- Nur benachbarte Woerter werden paarweise geprueft
- Reduziert O(n²) auf O(n log n) im Durchschnitt
- Dynamische Aktualisierung bei Wort-Verschiebung

## Stufe 4: SAT (Separating Axis Theorem)

- **Exakter Ueberlappungstest** fuer konvexe Polygone
- Projiziert Polygone auf potenzielle Trennachsen
- Keine Ueberlappung, wenn eine Trennachse existiert
- Fuer nicht-konvexe Woerter: konvexe Dekomposition

## Stufe 5: Bitmap 32-bit

- **Pixel-genaue Kollisionspruefung** als letzte Instanz
- Rasterisierung der Wort-Glyphen in 32-bit Bitmaps
- Bitweises AND: `collision = (bitmap_A & bitmap_B) != 0`
- Nutzt CPU-Bitoperationen fuer Parallelitaet (32 Pixel gleichzeitig)

## Ergaenzende Techniken

### BVH (Bounding Volume Hierarchy)
- Baumstruktur ueber verschachtelte Bounding Volumes
- Top-Down-Konstruktion ueber die gesamte Szene
- Alternative/Ergaenzung zum Quadtree
- Besonders effizient bei vielen statischen Objekten

### LRU-Cache
- **Least Recently Used Cache** fuer Kollisionsergebnisse
- Wiederholte Abfragen derselben Wortpaare vermeiden
- Invalidierung bei Positionsaenderung
- Deutliche Beschleunigung bei iterativer Optimierung

## Performance-Vergleich

| Stufe | Komplexitaet | Genauigkeit | Geschwindigkeit |
|-------|-------------|-------------|-----------------|
| AABB | O(1) | Grob | Sehr schnell |
| Two-Level Box | O(k) | Mittel | Schnell |
| Quadtree | O(log n) | Filterung | Schnell |
| SAT | O(v) | Exakt (konvex) | Mittel |
| Bitmap 32-bit | O(p) | Pixel-genau | Langsam |

## Siehe auch

- [sdf-geometry.md](sdf-geometry.md) — SDF liefert Pixel-Distanzen fuer Stage 5
- [np-hard-packing.md](np-hard-packing.md) — Kollisionsfreiheit ist die Kernanforderung
- [research/pitfalls.md](research/pitfalls.md) — Kollisions-Fallen und Quadtree-Tiefe
