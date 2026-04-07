---
title: "Seam Carving"
tags: [seam-carving, energie, dynamische-programmierung, kompression, semantik]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: seam-carving
created: 2026-04-07

---

# Seam Carving

## Konzept

Seam Carving entfernt **semantisch unwichtige Bereiche** aus dem Layout, um die Flaechenauslastung zu erhoehen - adaptiert aus der Bildkompression (Avidan & Shamir, 2007).

## Energie-Funktion

Die Energie-Funktion definiert, welche Bereiche wichtig sind und erhalten bleiben muessen:

```python
E(x, y) = Σ_i w_i * G(x, y, μ_i, σ_i)
```

- **Gauss-Funktionen um Woerter**: Jedes Wort erzeugt einen Gauss-Kegel
- `w_i` = TF-IDF-AP Gewicht des Wortes (wichtige Woerter → hohe Energie)
- `μ_i` = Position des Wortes (Zentrum des Gauss)
- `σ_i` = Ausdehnung, abhaengig von der Wortgroesse
- Bereiche mit hoher Energie werden geschuetzt
- Bereiche mit niedriger Energie (Luecken) werden entfernt

## Dynamisches Programmieren

Optimale Seam-Berechnung ueber **Dynamic Programming**:

```
Komplexitaet: O(w · h)
```

- `w` = Breite des Layouts
- `h` = Hoehe des Layouts

### Algorithmus

```python
# Vertikaler Seam
M = np.copy(energy)
for y in range(1, h):
    for x in range(w):
        M[y, x] += min(
            M[y-1, max(0, x-1)],
            M[y-1, x],
            M[y-1, min(w-1, x+1)]
        )
# Backtracking: Minimaler Pfad von unten nach oben
seam = backtrack(M)
```

## Semantik-erhaltende Kompression

Die AeroCloud-Adaptierung stellt sicher, dass die **semantische Struktur** erhalten bleibt:

1. **Hohe Energie** um semantisch wichtige Woerter (via TF-IDF-AP Gewichte)
2. **Cluster-Schutz**: Semantische Cluster bleiben zusammen
3. **Nur Leerraum wird entfernt** - keine Woerter werden beschnitten
4. **Iterative Anwendung**: Mehrere Seams nacheinander entfernen
5. **Abbruchkriterium**: Minimale Seam-Energie ueberschreitet Schwellenwert

## Ergebnis

- Kompaktere Layouts mit weniger Leerraum
- Semantische Gruppierungen bleiben intakt
- Silhouettenform wird besser ausgefuellt
- Kombination mit Inflate-Algorithmus fuer finale Anpassung

## Siehe auch

- [bezier-export.md](bezier-export.md) — Seam Carving + Bezier fuer Sub-Millimeter Export
- [medial-axis.md](medial-axis.md) — MAT als Energie-Guide
- [quality-metrics.md](quality-metrics.md) — Kompression darf Qualitaet nicht reduzieren
