---
title: "Differentiable Rendering"
tags: [differentiable, pytorch, tensor, loss, soft-rasterization, coarse-to-fine]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: differentiable-rendering
created: 2026-04-07

---

# Differentiable Rendering

## Tensor-Architektur

Jedes Wort wird als PyTorch-Tensor mit trainierbaren Parametern repraesentiert:

```python
params = {
    'x': torch.tensor(x0, requires_grad=True),      # x-Position
    'y': torch.tensor(y0, requires_grad=True),      # y-Position
    'scale': torch.tensor(1.0, requires_grad=True), # Skalierung
    'rot': torch.tensor(0.0, requires_grad=True),   # Rotation (Radiant)
}
```

- Alle 4 Parameter sind differenzierbar
- PyTorch Autograd berechnet Gradienten automatisch
- Font-Size bleibt eingefroren (aus Zipf/TF-IDF-AP)

## Soft-Rasterization

Statt harter Pixel-Zuordnung wird eine **weiche Rasterisierung** verwendet:

- Sigmoid-basierte Uebergaenge statt binaerem Rendering
- Differenzierbar - Gradienten fliessen durch den Rasterizer
- Approximation der tatsaechlichen Glyphen-Darstellung
- Temperatur-Parameter steuert Schaerfe der Kanten

## 4-teilige Loss-Funktion

### L_wmse - Weighted Mean Squared Error
- Misst die Abweichung der Wort-Positionen von Ziel-Positionen
- Gewichtet nach TF-IDF-AP Score (wichtige Woerter haben hoehere Prioritaet)

### L_overlap - Ueberlappungs-Loss
- Bestraft Ueberlappungen zwischen Woertern
- Berechnet ueber Soft-Rasterization (differenzierbar)
- Quadratische Bestrafung fuer starke Ueberlappungen

### L_fidelity - Formtreue-Loss
- Bestraft Woerter ausserhalb der Silhouette
- Nutzt das SDF: `max(0, SDF(p) + margin)²`
- Haelt Woerter innerhalb der Zielform

### L_temporal - Temporaler Glaettungs-Loss
- Bestraft grosse Positionsaenderungen zwischen Iterationen
- Stabilisiert die Optimierung
- Verhindert Spruenge im Layout

### Gesamt-Loss

```
L_total = λ_1 * L_wmse + λ_2 * L_overlap + λ_3 * L_fidelity + λ_4 * L_temporal
```

## Coarse-to-Fine Strategie

Die Aufloesung wird stufenweise erhoeht:

```
8×8 → 32×32 → 128×128 → Zielaufloesung
```

| Stufe | Aufloesung | Zweck |
|-------|-----------|-------|
| 1 | 8×8 | Grobe Platzierung, schnelle Konvergenz |
| 2 | 32×32 | Mittlere Genauigkeit, Feinabstimmung |
| 3 | 128×128 | Hohe Genauigkeit, Detail-Optimierung |
| 4 | Ziel | Finale Aufloesung, Sub-Pixel-Praezision |

### Vorteile
- Fruehe Stufen konvergieren schnell (wenige Pixel)
- Vermeidung lokaler Optima durch hierarchische Suche
- Spaete Stufen profitieren von guter Initialisierung
- Gesamtzeit deutlich reduziert gegenueber direkter Hochaufloesung

## Siehe auch

- [adam-optimizer.md](adam-optimizer.md) — Adam optimiert die Loss-Funktion
- [sdf-geometry.md](sdf-geometry.md) — SDF fliesst in L_wmse der 4-teiligen Loss
- [quality-metrics.md](quality-metrics.md) — Quality-Metriken steuern L_fidelity
