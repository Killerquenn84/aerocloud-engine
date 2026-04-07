---
title: "Bezier-Export und Schnittpunkt-Optimierung"
tags: [bezier, export, svg, pdf, png, kontrollpunkte, praezision]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: bezier-export
created: 2026-04-07

---

# Bezier-Export und Schnittpunkt-Optimierung

## Bezier-Schnittpunkt-Optimierung

Fuer den finalen Export werden Wort-Konturen als **Bezier-Kurven** dargestellt und an der Silhouette optimiert.

### Quadratische Bezier-Kurven
- 3 Kontrollpunkte: Start, Kontrollpunkt, Ende
- `B(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂`
- Einfacher, schneller zu berechnen
- Ausreichend fuer die meisten Glyphen-Segmente

### Kubische Bezier-Kurven
- 4 Kontrollpunkte: Start, 2 Kontrollpunkte, Ende
- `B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃`
- Hoehere Genauigkeit fuer komplexe Kurven
- Standard in TrueType/OpenType Fonts

## Sub-Millimeter Praezision

- Kontrollpunkte werden auf **Sub-Millimeter** genau positioniert
- Schnittpunktberechnung mit Newton-Raphson Iteration
- Numerische Praezision: < 0.01px Abweichung
- Garantiert saubere Schnitte an der Silhouettengrenze

## Export-Formate

### SVG (Scalable Vector Graphics)
- **Vektorformat** - verlustfrei skalierbar
- Bezier-Pfade direkt als SVG `<path>` Elemente
- Editierbar in Illustrator, Inkscape etc.
- Ideal fuer Web-Darstellung

### PDF (Portable Document Format)
- Vektorbasiert mit eingebetteten Fonts
- Druckfaehige Qualitaet
- Bezier-Kurven nativ unterstuetzt
- CMYK-Farbraum moeglich

### PNG (Portable Network Graphics)
- **Rasterformat** in konfigurierbarer Aufloesung
- Transparenter Hintergrund moeglich
- Fuer direkte Verwendung in Praesentationen
- Aufloesung: 72 DPI (Screen) bis 300+ DPI (Druck)

## Pipeline

```
Layout-Ergebnis (Positionen, Rotationen, Skalierungen)
  → Font-Rendering (FreeType/HarfBuzz)
  → Glyphen-Konturen als Bezier-Kurven
  → Schnittpunkt-Optimierung an Silhouettenrand
  → Clipping der ueberstehenden Teile
  → Export in Zielformat (SVG/PDF/PNG)
```

## Siehe auch

- [seam-carving.md](seam-carving.md) — Seam Carving als Vorstufe des Bezier-Exports
- [knowledge/stack-versions.md](knowledge/stack-versions.md) — svgelements + ReportLab fuer Export
- [knowledge/requirements-v1.md](knowledge/requirements-v1.md) — PROD-03 bis PROD-06 Requirements
