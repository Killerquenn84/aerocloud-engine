---
title: "Adam Optimizer"
tags: [adam, optimizer, pytorch, konvergenz, speedup]
sources: [AeroCloud-Blueprint.md]
updated: 2026-04-06
slug: adam-optimizer
created: 2026-04-07

---

# Adam Optimizer

## Hyperparameter

| Parameter | Wert | Beschreibung |
|-----------|------|-------------|
| α (Learning Rate) | 0.001 | Schrittweite |
| β₁ | 0.9 | Exponentieller Decay fuer 1. Moment (Mittelwert) |
| β₂ | 0.999 | Exponentieller Decay fuer 2. Moment (Varianz) |
| ε | 1e-8 | Numerische Stabilitaet |

## Algorithmus

```python
# Adam Update-Regel (vereinfacht)
m_t = β₁ * m_{t-1} + (1 - β₁) * g_t          # 1. Moment
v_t = β₂ * v_{t-1} + (1 - β₂) * g_t²          # 2. Moment
m̂_t = m_t / (1 - β₁^t)                        # Bias-Korrektur
v̂_t = v_t / (1 - β₂^t)                        # Bias-Korrektur
θ_t = θ_{t-1} - α * m̂_t / (√v̂_t + ε)        # Parameter-Update
```

## Konvergenz

- Typischerweise **~100 Epochen** bis zur Konvergenz pro Layout-Kandidat
- Fruehe Epochen: Grosse Positionsaenderungen (grobe Platzierung)
- Mittlere Epochen: Feinabstimmung der Positionen und Rotationen
- Spaete Epochen: Minimale Anpassungen, Loss-Plateau

## Speedup gegenueber Object-Space

Der differenzierbare Ansatz mit Adam bietet **~10x Speedup** gegenueber klassischen Object-Space-Methoden:

| Methode | Ansatz | Typische Zeit |
|---------|--------|--------------|
| Object-Space (Wordle) | Iterative Spiral-Suche | ~10s pro Layout |
| **Image-Space (Adam)** | **Gradient Descent** | **~1s pro Layout** |

### Gruende fuer den Speedup
- **Parallele GPU-Berechnung**: Alle Woerter gleichzeitig optimiert
- **Gradient-Information**: Gerichtete Optimierung statt blinder Suche
- **Soft-Rasterization**: Vermeidet diskrete Kollisionspruefungen
- **Batch-Verarbeitung**: Effiziente Tensor-Operationen auf der GPU

## Integration

```python
optimizer = torch.optim.Adam(
    [params['x'], params['y'], params['scale'], params['rot']],
    lr=0.001,
    betas=(0.9, 0.999)
)

for epoch in range(100):
    optimizer.zero_grad()
    rendered = soft_rasterize(params)
    loss = compute_total_loss(rendered, target)
    loss.backward()
    optimizer.step()
```

## Siehe auch

- [differentiable-rendering.md](differentiable-rendering.md) — Adam betreibt den Inner Loop Rasterizer
- [research/pitfalls.md](research/pitfalls.md) — Vanishing Gradients und CUDA OOM vermeiden
- [knowledge/stack-versions.md](knowledge/stack-versions.md) — torch 2.7.1 + nvdiffrast 0.3.3.1
