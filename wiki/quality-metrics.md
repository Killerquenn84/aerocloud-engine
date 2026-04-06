---
title: "Qualitaetsmetriken"
tags: [metriken, geometrisch, semantisch, vergleich, qualitaet]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
---

# Qualitaetsmetriken

## Geometrische Metriken

### LC - Layout Coverage
- Anteil der Silhouettenflaeche, der von Woertern bedeckt ist
- `LC = Σ(Wortflaeche) / Silhouettenflaeche`
- Ziel: Moeglichst hoch (> 0.7)

### LU - Layout Utilization
- Effizienz der Flaechennutzung unter Beruecksichtigung von Luecken
- Bewertet gleichmaessige Verteilung vs. Cluster-Bildung

### SS - Space Similarity
- Wie gut stimmt die Wortverteilung mit der Silhouettenform ueberein?
- Vergleich der Dichte-Verteilung von Woertern mit der Silhouetten-Geometrie
- Kernmetrik im MAP-Elites Behaviour-Raum

### Compactness
- Mass fuer die Dichtheit der Anordnung
- Wenig Leerraum zwischen benachbarten Woertern
- `Compactness = 1 - (Leerraum / Gesamtflaeche)`

### Aspect Ratio φ
- Verhaeltnis der Wort-Seitenverhaeltnisse zur Silhouetten-Geometrie
- Optimale Rotationen maximieren die Passung
- φ nahe 1.0 = natuerliche Proportionen

## Semantische Metriken

### Realized Adjacencies
- Anteil der semantisch verwandten Wortpaare, die im Layout **benachbart** platziert sind
- `RA = |realisierte Adj.| / |gewuenschte Adj.|`
- Basiert auf BERT Cosinus-Aehnlichkeit > Schwellenwert
- Hoeher = bessere semantische Kohaerenz

### Distortion
- Verzerrung der semantischen Abstande durch das Layout
- `Distortion = Korrelation(semantischer Abstand, raeumlicher Abstand)`
- Ideal: Hohe Korrelation (semantisch nahe = raeumlich nahe)

## Algorithmen-Vergleich

| Methode | Beschreibung | Staerke |
|---------|-------------|---------|
| **Cycle Cover** | Ueberdeckung durch Zyklen im Nachbarschaftsgraph | Maximale Flaechennutzung |
| **Star Forest** | Stern-foermige Anordnung um zentrale Woerter | Semantische Hierarchie |
| **Seam Carving** | Entfernung unwichtiger Leerraum-Bereiche | Kompaktheit |
| **Inflate** | Woerter aufblasen bis zur Beruehrung | Lueckenfuellung |

### Kombinierte Bewertung

```
Q_total = w_1 * LC + w_2 * SS + w_3 * Compactness 
        + w_4 * RA + w_5 * (1 - Distortion)
```

Die Gewichte `w_i` sind konfigurierbar und bestimmen die Priorisierung geometrischer vs. semantischer Qualitaet.
