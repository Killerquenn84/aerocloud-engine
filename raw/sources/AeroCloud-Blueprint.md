# Project AeroCloud – Ultimativer Gesamt-Blueprint
## Mathematik, Algorithmen & Implementierung einer selbstlernenden Word-Cloud-Engine

---

## Executive Summary

Die Erstellung einer visuell perfekten und semantisch sinnvollen Word Cloud ist kein simples typografisches Skript. Aus Sicht der Informatik und Mathematik handelt es sich um ein hochkomplexes **2D Irregular Bin Packing Problem** – ein zweidimensionales, unregelmaessiges Packungsproblem, das mit Graphentheorie und stochastischer Optimierung gekoppelt ist. Da unregelmaessige Polygone (Wortumrisse) ueberschneidungsfrei angeordnet werden muessen, gehoert dieses Problem zur Klasse der **NP-schweren Probleme**.

"Perfektion" beim Design ist subjektiv: Ein Nutzer will maximale Packungsdichte, ein anderer exakt 40% rotierte Woerter. Das Paper von Kent, Branke, Gaier und Mouret (GECCO 2022) zu **Quality-Diversity (QD) Algorithmen** liefert den theoretischen Durchbruch: Die Engine sucht nicht ein einzelnes Optimum, sondern leuchtet den gesamten kontinuierlichen Loesungsraum aus.

Die Architektur basiert auf einem **Dual-Loop-Paradigma**:
- **Inner Loop (Exploitation):** PyTorch-basierte GPU-Physik-Engine mit Differentiable Rendering
- **Outer Loop (Exploration):** Asynchrone Meta-KI via CQD-Metrik + MAP-Elites Self-Play

---

## Teil I: Mathematische Grundlagen

### 1.1 Das Problem: NP-Schwere und Loesungsraum

Das Word-Cloud-Layout ist formal ein **Irregular Bin Packing Problem**: Unregelmaessige konvexe und nicht-konvexe Polygone (Wortumrisse) muessen ueberlappungsfrei in einen nicht-konvexen Container (Ziel-Silhouette) gepackt werden.

Drei mathematische Disziplinen definieren den Loesungsraum:
1. **Geometrie und Topologie:** Signed Distance Fields, Medial Axis Transform, Voronoi-Tessellation
2. **Kombinatorische Optimierung:** Bin Packing, Cutting Stock Problem, Force-Directed Graphs
3. **Stochastische Optimierung:** Quality-Diversity-Algorithmen, Monte-Carlo-Methoden, Differentiable Rendering

### 1.2 Zipf-Gesetz und Potenzverteilung von Sprache

Wortfrequenzen in natuerlicher Sprache folgen einem Potenzgesetz (Zipf-Gesetz): f(r) proportional r^(-alpha), alpha ca. 1

Korrekte Normalisierung:
- Linear: FALSCH fuer Power-Law-Daten
- Logarithmisch: OPTIMAL fuer Zipf-verteilte Texte
- Wurzel: Kompromiss

Die logarithmische Variante ist die einzig korrekte Wahl. Die berechneten Skalierungsfaktoren werden als reference_weights-Tensor eingefroren.

### 1.3 TF-IDF-AP: Adaptives Relevanz-Scoring

w(t,d) = TF * IDF * P_weight

- TF: Normalisierte Worthaeufigkeit im Dokument
- IDF: log(N / |{d' : t in d'}|) – bestraft haeufige Stopwoerter
- P_weight: Positions-Multiplikator fuer H1-Tags, Titel, Satzanfaenge (+12.9% semantische Praezision)

NLP-Pipeline: Tokenisierung/Lemmatisierung (spaCy) → Stopword-Entfernung → TF-IDF-AP → Log Font-Size → reference_weights einfrieren

---

## Teil II: Semantischer Vektorraum (The Brain)

### 2.1 BERT-Embeddings und Dimensionsreduktion

Transformer-Modell (all-MiniLM-L6-v2) generiert hochdimensionale Vektoren.
Cosinus-Aehnlichkeit: sim(w_i, w_j) = v_i · v_j / (||v_i|| * ||v_j||)
t-SNE oder UMAP projiziert auf 2D-Leinwand → Warm-Start-Initialisierung.

### 2.2 Optimal Transport via Sinkhorn-Knopp

Ersetzt Force-Directed Layouts. Wasserstein-Distanz W_p(mu, nu).
- Deterministisch (vs. iterativ/stochastisch bei Force-Directed)
- Konvergenzgarantie
- O(n²) einmalig (vs. O(n²) pro Iteration)
- Mathematisch optimal

---

## Teil III: Shape-Analyse (The Skeleton)

### 3.1 Signed Distance Field (SDF)

SDF(x) = d(x, Grenze) wenn innen (negativ), -d wenn aussen (positiv)
Gradient zeigt stets zur naechsten Shape-Kontur.

### 3.2 Medial Axis Transform (MAT)

Topologisches Skelett des SDF. Identifiziert Hauptachsen, lokale Breiten, Verbindungsknoten.

### 3.3 Multi-Centric Wordle

Fuer nicht-konvexe Shapes: Segmentierung mit eigener Spiralmitte pro Teilbereich.

### 3.4 WASM-Echtzeit-Engine

Rust/WASM: Archimedische Spirale r(theta) = a + b*theta
- 1-Bit-Maske in 32-Bit-Integers
- Quadtree: O(n log n)
- Ergebnis: <100ms Latenz im Browser

---

## Teil IV: Kollisionserkennung

5-stufige Hierarchie:
1. AABB Bounding Boxes – O(1) pro Paar
2. Two-Level Box (EdWordle) – O(n) mit BVH
3. Quadtree Spatial Index – O(n log n)
4. SAT (Separating Axis Theorem) – O(n*k)
5. Bitmap + 32-bit INT – O(n*m/32), Pixel-exakt

Plus: BVH-Baum + LRU-Cache

---

## Teil V: Inner Loop – Differentiable Rendering (The Muscles)

### 5.1 Tensor-Architektur

Position (x,y), Skalierung (s), Rotation (theta) als lernbare Tensoren (requires_grad=True).
Soft-Rasterization: I(x,y) = Integral k(u,v) * f(x-u, y-v; Theta) du dv

### 5.2 Viergliedrige Loss-Funktion

L_total = alpha*L_wmse + beta*L_overlap + gamma*L_fidelity + lambda*L_temporal

1. L_wmse (Boundary Fitness): Shape "saugt" Woerter hinein
2. L_overlap (Primitive Overlap): ReLU(Dichte - 1.0)²
3. L_fidelity (Data Fidelity): 1 - cos_sim(S_ref, S_upd) – verhindert kuenstliches Aufblaehen
4. L_temporal (Temporal Coherence): Fuer Live-Feeds, bestraft Positionsaenderungen

### 5.3 Adam-Optimizer

alpha=0.001, beta1=0.9, beta2=0.999, epsilon=10^-8

### 5.4 Coarse-to-Fine

8px → 32px → 128px → Zielaufloesung. ~10x Speedup, ~100 Epochen Konvergenz.

---

## Teil VI: Seam Carving

Energie: E(x,y) = sum w_i * Gauss(Distanz)
Optimale Naht via DP: O(w*h)

---

## Teil VII: Qualitaetsmetriken

Geometrisch: LC, LU, SS, Compactness, Aspect Ratio (→ 1.618)
Semantisch: Realized Adjacencies (Cycle Cover), Distortion
Meta: CQD-Score, CQD_beta, CQD_HV

---

## Teil VIII: Outer Loop – Quality-Diversity (The Evolution)

### CQD-Gleichung

omega(x, G, theta) = f(x)/|f_max - f_min| - theta * delta(g(x), G)/delta_max

theta in [0,1]: 0 = nur Dichte, →1 = exakter Stil zwingend

### CQD-Score via Monte-Carlo

CQD = (1/N*M) * sum_n sum_m omega(x^r, G_n, theta_m)

### MAP-Elites

Grid-Achsen: Formtreue, Rotation, Symmetrie, Semantik
BOP-Elites: 700 Evaluierungen = MAP-Elites 90.000

### Self-Play Training (naechtlich)

Monte-Carlo Sampling → Mutation → Evaluation → Archiv-Update

---

## Teil IX: Pareto-Front und CQD_HV

CQD_HV = sum_G HV(S_HV(G))
Pareto-Slider: Links (Designtreue) ↔ Rechts (Packungsdichte)

---

## Teil X: Export

Seam Carving + Bezier-Schnittpunkt-Optimierung → Sub-Millimeter SVG/PDF/PNG

---

## Teil XI: IT-Infrastruktur

Frontend: Next.js/React/Tailwind
Preview: Rust/WASM
Animation: Three.js/WebGL
API: FastAPI (Python)
GPU Worker: PyTorch/CUDA + Celery/Redis
Training: PostgreSQL Vektordatenbank + MAP-Elites Archiv
