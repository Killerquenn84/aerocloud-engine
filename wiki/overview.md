---
title: "AeroCloud Engine - Gesamtuebersicht"
tags: [overview, architektur, dual-loop, pytorch, map-elites, bin-packing]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: overview
created: 2026-04-07

---

# AeroCloud Engine - Gesamtuebersicht

## Dual-Loop-Paradigma

Die AeroCloud Engine basiert auf einem zweistufigen Optimierungsansatz:

### Inner Loop (PyTorch GPU)
- **Differenzierbares Rendering** auf der GPU mittels PyTorch-Tensoren
- Jedes Wort besitzt trainierbare Parameter: Position `(x, y)`, Skalierung `scale` und Rotation `rot` (alle mit `requires_grad=True`)
- Optimierung ueber Adam-Optimizer mit Soft-Rasterization und mehrteiliger Loss-Funktion
- Konvergenz typischerweise nach ~100 Epochen pro Layout-Kandidat

### Outer Loop (Quality-Diversity / MAP-Elites)
- **MAP-Elites Grid** durchsucht den Raum moeglicher Layouts systematisch
- Behaviour-Dimensionen: Space-Similarity (SS), Rotationsverteilung, Symmetrie, semantische Kohaerenz
- Jede Zelle im Grid speichert den besten bisher gefundenen Kandidaten
- BOP-Elites Variante: 700 Iterationen entsprechen ca. 90.000 Evaluationen
- Naechtliches Self-Play Training zur kontinuierlichen Verbesserung

## NP-hartes 2D Irregular Bin Packing

Das Kernproblem ist ein **NP-schweres 2D Irregular Bin Packing**:
- Woerter sind keine Rechtecke, sondern **irregulare Polygone** (konvex und nicht-konvex)
- Platzierung innerhalb einer beliebigen Silhouette (ebenfalls nicht-konvex)
- Keine polynomielle exakte Loesung bekannt - daher heuristische Optimierung

## 5 Mathematische Disziplinen

AeroCloud vereint fuenf mathematische Kernbereiche:

1. **Computational Geometry** - SDF, Medial Axis Transform, Bezier-Kurven, Kollisionserkennung
2. **Kombinatorische Optimierung** - Bin Packing, MAP-Elites, Seam Carving
3. **Stochastische Optimierung** - Quality-Diversity, Monte-Carlo-Sampling, Escape-Moves
4. **Differenzierbare Optimierung** - PyTorch Autograd, Adam, Soft-Rasterization
5. **NLP / Semantische Analyse** - TF-IDF, BERT Embeddings, Optimal Transport

## Architektur-Fluss

```
Eingabe (Text + Silhouette)
  → NLP-Pipeline (TF-IDF-AP, BERT)
  → Optimal Transport (Sinkhorn → Zuordnung)
  → MAP-Elites Outer Loop
    → Inner Loop (Differentiable Rendering + Adam)
  → Post-Processing (Seam Carving, Bezier Export)
  → Ausgabe (SVG/PDF/PNG)
```

## Siehe auch

- [source-blueprint.md](source-blueprint.md) — Blueprint Master-Dokument
- [knowledge/project-specification.md](knowledge/project-specification.md) — PROJECT.md Spiegel
- [knowledge/roadmap-v1.md](knowledge/roadmap-v1.md) — 12-Phasen Bauplan
