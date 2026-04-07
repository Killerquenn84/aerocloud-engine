---
title: "BERT Embeddings und Dimensionsreduktion"
tags: [bert, embeddings, cosinus, tsne, umap, warm-start, semantik]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: bert-embeddings
created: 2026-04-07

---

# BERT Embeddings und Dimensionsreduktion

## Modell: all-MiniLM-L6-v2

- **Sentence-Transformers** Modell von Hugging Face
- 6 Transformer-Layer, kompakt und schnell
- 384-dimensionale Embedding-Vektoren
- Optimiert fuer semantische Aehnlichkeit
- Unterstuetzt mehrsprachige Eingaben

## Cosinus-Aehnlichkeit

Die semantische Naehe zwischen Woertern wird ueber **Cosinus-Aehnlichkeit** gemessen:

```
cos_sim(a, b) = (a · b) / (||a|| * ||b||)
```

- Wertebereich: [-1, 1], typisch [0, 1] fuer Wort-Embeddings
- Semantisch aehnliche Woerter erhalten hohe Werte (> 0.7)
- Wird verwendet fuer:
  - Semantische Cluster-Bildung
  - Optimal-Transport-Kostenmatrix
  - Adjacency-Qualitaetsmetrik

## Dimensionsreduktion

### t-SNE (t-distributed Stochastic Neighbor Embedding)
- Reduziert 384D → 2D fuer Visualisierung
- Erhalt lokaler Nachbarschaftsstrukturen
- Nicht-deterministisch, Perplexity als Hyperparameter
- Primaer fuer Debugging und Analyse

### UMAP (Uniform Manifold Approximation and Projection)
- Schneller als t-SNE bei grossen Datensaetzen
- Besserer Erhalt globaler Strukturen
- Deterministischer mit festem Seed
- Geeignet fuer Produktions-Pipeline

## Warm-Start-Initialisierung

Anstatt Woerter zufaellig zu platzieren, nutzt AeroCloud die **BERT-Embeddings als Warm-Start**:

1. BERT-Embeddings fuer alle Woerter berechnen
2. Dimensionsreduktion auf 2D (UMAP bevorzugt)
3. Skalierung der 2D-Koordinaten auf die Silhouette
4. Semantisch aehnliche Woerter starten **raeumlich nahe beieinander**
5. Der Inner-Loop-Optimizer muss weniger Distanz ueberbruecken

### Vorteile
- Schnellere Konvergenz des Adam-Optimizers
- Hoehere semantische Kohaerenz im Endergebnis
- Besserer Startpunkt fuer Optimal Transport

## Siehe auch

- [optimal-transport.md](optimal-transport.md) — Sinkhorn-Knopp nutzt BERT-Embeddings fuer Initial Layout
- [tf-idf-ap.md](tf-idf-ap.md) — TF-IDF fuer Wort-Gewichtung
- [research/stack.md](research/stack.md) — sentence-transformers 5.3.0 Pinning
