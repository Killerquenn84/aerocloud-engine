---
title: "Optimal Transport - Sinkhorn-Knopp"
tags: [optimal-transport, sinkhorn, wasserstein, clustering, semantik]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: optimal-transport
created: 2026-04-07

---

# Optimal Transport - Sinkhorn-Knopp

## Konzept

Optimal Transport ordnet **semantische Cluster den Form-Segmenten** der Silhouette zu:
- Cluster = Gruppen semantisch verwandter Woerter (via BERT-Embeddings)
- Form-Segmente = Regionen der Silhouette (via Medial Axis Transform)
- Ziel: Minimierung der Transportkosten bei Beibehaltung semantischer Naehe

## Sinkhorn-Knopp Algorithmus

Entropie-regularisierte Loesung des Optimal-Transport-Problems:

```
K = exp(-C / ε)         # Gibbs-Kernel aus Kostenmatrix C
u = 1/n                  # Initialisierung
for iteration in range(max_iter):
    u = a / (K @ v)      # Zeilen-Normalisierung
    v = b / (K.T @ u)    # Spalten-Normalisierung
T = diag(u) @ K @ diag(v)  # Transportplan
```

- `C` = Kostenmatrix (Cosinus-Distanz zwischen Cluster-Centroiden und Segment-Positionen)
- `ε` = Regularisierungsparameter (Entropie)
- Konvergiert schnell bei geeignetem ε

## Wasserstein-Distanz

Die optimalen Transportkosten ergeben die **Wasserstein-Distanz** (Earth Mover's Distance):

```
W(μ, ν) = min_T Σ_ij T_ij * C_ij
```

## Deterministisch vs. Force-Directed

| Eigenschaft | Optimal Transport | Force-Directed (Wordle) |
|-------------|------------------|------------------------|
| **Berechnung** | Deterministisch, einmalig | Iterativ, viele Schritte |
| **Komplexitaet** | O(n²) einmalig | O(n² * k) fuer k Iterationen |
| **Ergebnis** | Globales Optimum (regularisiert) | Lokales Gleichgewicht |
| **Semantik** | Explizite Cluster-Zuordnung | Implizit ueber Kraefte |
| **Reproduzierbarkeit** | Deterministisch | Abhaengig von Startposition |

## Pipeline-Integration

```
BERT Embeddings
  → Cosinus-Aehnlichkeitsmatrix
  → Hierarchisches Clustering
  → Medial Axis → Form-Segmente
  → Sinkhorn-Knopp Transport
  → Initiale Cluster-zu-Segment Zuordnung
  → Inner Loop Optimierung
```

Der O(n²)-Aufwand faellt **einmalig** an und amortisiert sich durch bessere Initialisierung und schnellere Konvergenz im Inner Loop.

## Siehe auch

- [bert-embeddings.md](bert-embeddings.md) — Embeddings als Input fuer Sinkhorn-Knopp
- [differentiable-rendering.md](differentiable-rendering.md) — OT liefert den Warm-Start fuer den Inner Loop
- [research/pitfalls.md](research/pitfalls.md) — Sinkhorn Underflow in log-space vermeiden
