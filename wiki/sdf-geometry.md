---
title: "Signed Distance Field (SDF)"
tags: [sdf, geometrie, distanzfeld, gradient, spiral-suche, loss]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: sdf-geometry
created: 2026-04-07

---

# Signed Distance Field (SDF)

## Definition

Ein Signed Distance Field ordnet jedem Punkt im 2D-Raum einen **vorzeichenbehafteten Abstand** zur naechsten Kontur zu:

```
SDF(p) = {
  < 0   wenn p innerhalb der Silhouette liegt
  = 0   auf der Kontur
  > 0   wenn p ausserhalb der Silhouette liegt
}
```

## Eigenschaften

- **Innen negativ**: Je tiefer im Inneren, desto negativer der Wert
- **Aussen positiv**: Je weiter entfernt, desto groesser der Wert
- **Gradient zeigt zur Kontur**: `∇SDF(p)` zeigt in Richtung der naechsten Konturgrenze
- **Betrag = euklidischer Abstand** zur naechsten Kontur

## SDF-Berechnung

```python
# Diskretisierung auf Pixel-Grid
sdf_grid = np.zeros((height, width))
for y in range(height):
    for x in range(width):
        sdf_grid[y, x] = signed_distance(Point(x, y), contour)
```

In der Praxis: Effiziente Berechnung ueber **Distance Transform** auf der binarisierten Silhouette (OpenCV `distanceTransform`).

## Steuerung der Spiral-Suche

Die Spiral-Suche fuer die Wort-Platzierung nutzt das SDF:

1. **Start am Medial-Axis-Punkt** (tiefster negativer SDF-Wert)
2. **Spiralfoermige Expansion** nach aussen
3. **SDF-Wert prueft**: Liegt das gesamte Wort-Bounding-Box innerhalb? (`SDF < -margin`)
4. **Gradient-Richtung** als Hinweis fuer die naechste Suchrichtung

## Boundary-Fitness-Loss

Im differenzierbaren Rendering steuert das SDF den **Fidelity-Loss**:

```
L_fidelity = Σ_i max(0, SDF(p_i) + margin)²
```

- Bestraft Woerter, die ueber den Silhouettenrand hinausragen
- `margin` definiert einen Sicherheitsabstand zur Kontur
- Weicher Uebergang (quadratisch) fuer stabilen Gradienten
- Differenzierbar, daher kompatibel mit PyTorch Autograd

## Vorteile des SDF-Ansatzes

- **O(1) Inside/Outside-Test** pro Punkt (nach Vorberechnung)
- **Stetige Funktion** - ideal fuer Gradient-basierte Optimierung
- **Abstandsinformation** - nicht nur Boolean, sondern "wie weit drinnen/draussen"
- **Vorberechnung** einmalig pro Silhouette

## Siehe auch

- [medial-axis.md](medial-axis.md) — MAT baut auf SDF-Feldern auf
- [collision-detection.md](collision-detection.md) — SDF als Basis fuer Pixel-genaue Kollision
- [differentiable-rendering.md](differentiable-rendering.md) — SDF-Gradienten fliessen in die Loss-Funktion
