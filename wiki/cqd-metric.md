---
title: "CQD-Metrik (Continuous Quality-Diversity)"
tags: [cqd, quality-diversity, metrik, monte-carlo, hypervolume, gecco]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: cqd-metric
created: 2026-04-07

---

# CQD-Metrik (Continuous Quality-Diversity)

## Herkunft

- **Autoren**: Kent, Branke, Gaier, Mouret
- **Konferenz**: GECCO 2022 (Genetic and Evolutionary Computation Conference)
- Standardmetrik fuer Quality-Diversity-Algorithmen

## Definition

```
ω(x, G, θ)
```

- `x` = Loesung (Layout-Kandidat)
- `G` = Archiv/Grid (MAP-Elites Population)
- `θ` = Qualitaetsschwellenwert

Die CQD-Metrik bewertet **gleichzeitig** Qualitaet und Diversitaet eines QD-Archivs.

## Diskretisierungsfrei

Im Gegensatz zu klassischen Grid-basierten Metriken:
- **Keine feste Grid-Aufloesung** noetig
- Funktioniert mit beliebigen Behaviour-Raeumen
- Keine Artefakte durch Grid-Grenzen
- Kontinuierliche Bewertung der Archiv-Qualitaet

## Monte-Carlo-Sampling

Die CQD-Berechnung nutzt **Monte-Carlo-Sampling**:

1. Zufaellige Referenzpunkte im Behaviour-Raum samplen
2. Fuer jeden Referenzpunkt: Naechste Loesung im Archiv finden
3. Qualitaet und Distanz bewerten
4. Ueber alle Samples aggregieren

```python
def cqd_score(archive, n_samples=10000):
    ref_points = sample_uniform(behaviour_space, n_samples)
    scores = []
    for ref in ref_points:
        nearest = archive.nearest(ref)
        if nearest.quality >= threshold:
            scores.append(1.0 - distance(ref, nearest.behaviour))
    return np.mean(scores)
```

## CQD-Varianten

### CQD_β (mit Schwellenwert)
- Nur Loesungen oberhalb des Schwellenwerts β werden gezaehlt
- `β` steuert den Qualitaets-Mindeststandard
- Hoehere β-Werte = strengerer Qualitaetsfilter
- Nuetzlich fuer die Bewertung "brauchbarer" Loesungen

### CQD_HV (Hypervolume)
- Integration ueber den gesamten Schwellenwert-Bereich
- Berechnet die **Flaeche unter der CQD-β-Kurve**
- Einzelne Zahl fasst das gesamte Archiv zusammen
- Robuster als einzelne β-Werte

## Anwendung in AeroCloud

| Behaviour-Dimension | Beschreibung |
|---------------------|-------------|
| Space Similarity (SS) | Wie gut fuellt das Layout die Silhouette? |
| Rotationsverteilung | Vielfalt der Wort-Rotationen |
| Symmetrie | Grad der Layout-Symmetrie |
| Semantische Kohaerenz | BERT-basierte Cluster-Qualitaet |

## Siehe auch

- [map-elites.md](map-elites.md) — MAP-Elites nutzt CQD als Quality-Score
- [quality-metrics.md](quality-metrics.md) — CQD baut auf geometrischen Metriken auf
- [decisions/2026-04-07-polyglot-stack-selection.md](decisions/2026-04-07-polyglot-stack-selection.md) — pyribs als QD Framework
