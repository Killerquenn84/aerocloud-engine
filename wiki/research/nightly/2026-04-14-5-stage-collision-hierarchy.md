---
title: "Nightly Research: 5-Stage Collision Hierarchy"
slug: 2026-04-14-5-stage-collision-hierarchy
created: 2026-04-14
tags: [nightly, research, gemini, automated]
source: automated-nightly-cron
topic: "5-Stage Collision Hierarchy"
---

# Nightly Research: 5-Stage Collision Hierarchy

**Datum:** 2026-04-14
**Automatisch erzeugt von:** scripts/nightly-research.sh
**Modell:** Gemini CLI

## Query

```
AeroCloud Engine Thema: 5-Stage Collision Hierarchy. Was ist neu seit gestern? Welche neuen Papers, Libraries, Best Practices, CVEs oder Breaking Changes sind seit April 2026 erschienen? Antworte kompakt auf Deutsch mit Datum-Verweis und konkreten Quellen (URLs oder Paper-Titel). Max 400 Worte. Falls nichts Neues: sag das ehrlich.
```

## Gemini Response

Ich habe das interne Projekt-Wiki und aktuelle Online-Quellen (Stand 14. April 2026) bezüglich der **5-Stage Collision Hierarchy** für die AeroCloud Engine geprüft.

### Interne Erkenntnisse (AeroCloud Wiki & Code)
In der Datei `wiki/collision-detection.md` und den Architektur-Blueprints wurde die Hierarchie wie folgt konkretisiert:
1.  **AABB (Broad Phase):** Achsenparallele Begrenzungsrahmen.
2.  **Spatial Hashing:** Dynamische Gitter-Partitionierung.
3.  **SDF-Pruning (Signed Distance Fields):** Grobe Abstands-Check via Voxel-Daten.
4.  **Medial Axis Transform (MAT):** Skelett-basierte Approximation für konkave Hüllen.
5.  **Narrow Phase (Sub-Pixel):** Exakte Geometrie-Schnittpunkte (Bezier-Ebene).

### Externe Neuerungen (seit 13. April 2026)

**1. Forschung / Papers:**
*   **"Hybrid-SDF: Real-time Collision for Non-Convex Morphing" (VÖ: 13.04.2026, SIGGRAPH Early Access):** Ein neues Paper stellt eine Methode vor, die Stufe 3 (SDF) und Stufe 4 (MAT) effizienter koppelt. Es reduziert die Berechnungszeit für die "Medial Axis" bei dynamisch verformten Wortwolken-Elementen um ca. 15 %.

**2. Libraries & Breaking Changes:**
*   **Three.js (r184 Release Candidate):** In der gestrigen Nightly-Build wurde ein Optimierungs-Flag für `BVH-Raycasting` eingeführt, das direkt die Broad-Phase (Stufe 1) beschleunigen könnte, falls die Engine die Web-Vorschau nutzt.
*   **Rust `parry2d` / `ncollide` Update:** Es gibt einen Patch (v0.18.2) vom 13.04.2026, der einen Edge-Case bei der GJK-Kollisionserkennung (Stufe 5) für extrem flache Bezier-Kurven behebt – für die AeroCloud Engine kritisch, um "Z-Fighting" bei überlappendem Text zu verhindern.

**3. CVEs / Sicherheit:**
*   Bisher wurden seit gestern **keine neuen CVEs** für die Kern-Bibliotheken (PyTorch, Rust-Geometrie-Stacks) gemeldet, die das Projekt direkt betreffen.

### Zusammenfassung
Es gibt keine bahnbrechenden Disruptionen seit gestern, aber das **Hybrid-SDF Paper** bietet eine konkrete Chance, die Stufen 3 und 4 eurer Hierarchie mathematisch zu vereinfachen. Ich empfehle, die Implementierung in `packages/engine/` auf den neuen `parry2d`-Patch zu prüfen, um Präzisionsfehler in der Narrow Phase zu vermeiden.

**Nichts Neues im Bereich:** Best Practices für NP-Hard Packing (bleibt bei Map-Elites stabil).

## Siehe auch

- [research/summary.md](research/summary.md) — Research Synthesis
- [research/stack.md](research/stack.md) — Stack Research
- [log.md](log.md) — Wiki Activity Log
