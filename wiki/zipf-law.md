---
title: "Zipf-Gesetz und Font-Size-Skalierung"
tags: [zipf, font-size, power-law, skalierung, linguistik]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
---

# Zipf-Gesetz und Font-Size-Skalierung

## Zipf-Gesetz

Das Zipf-Gesetz beschreibt die Haeufigkeitsverteilung natuerlicher Sprache:

```
f(r) ∝ r^(-α)
```

- `f(r)` = Haeufigkeit des Wortes mit Rang `r`
- `α` ≈ 1.0 fuer natuerliche Sprache (Zipf-Exponent)
- Das haeufigste Wort kommt ca. doppelt so oft vor wie das zweithaeufigste

## Logarithmische Font-Size-Skalierung

Fuer Power-Law-verteilte Daten ist eine **logarithmische Font-Size-Zuordnung** optimal:

```
font_size(r) = base_size + scale * log(f(r))
```

### Begruendung
- Lineare Skalierung wuerde das Top-Wort ueberproportional gross darstellen
- Logarithmische Skalierung komprimiert den Dynamikbereich
- Visuell ausgewogenere Darstellung bei Beibehaltung der Rangordnung
- Bessere Flaechennutzung innerhalb der Silhouette

## Reference Weights einfrieren

Die `reference_weights` werden zu Beginn der Pipeline fixiert und waehrend der Optimierung **eingefroren**:

- Berechnung einmalig aus den TF-IDF-AP Gewichten
- Mapping auf Font-Sizes ueber logarithmische Zipf-Skalierung
- Waehrend der Inner-Loop-Optimierung (Adam) bleiben die Font-Sizes konstant
- Nur Position, Rotation und Skalierung werden optimiert - **nicht** die Wortgroesse
- Dies verhindert, dass der Optimizer Woerter schrumpft um Platz zu sparen

## Konfiguration

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `alpha` | 1.0 | Zipf-Exponent |
| `min_font_size` | 8 | Minimale Schriftgroesse in px |
| `max_font_size` | 120 | Maximale Schriftgroesse in px |
| `scale_mode` | `"log"` | Skalierungsmodus (`"log"`, `"sqrt"`, `"linear"`) |
