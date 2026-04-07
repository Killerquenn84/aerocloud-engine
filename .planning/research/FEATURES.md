# Features Research — AeroCloud Blueprint State-of-the-Art Mapping

**Researched by:** Gemini CLI (April 2026)
**Scope:** Each Blueprint section mapped to maturity level, production references, and known failure modes.

## 1. TF-IDF-AP (Position-weighted)

- **Maturity:** Production-ready
- **References:** Chen et al. (2016) "Optimized TF-IDF Algorithm with Adaptive Weight". The +12.9% precision figure was demonstrated on Chinese document clustering (culture domain).
- **Failure modes:** Misleading metadata (clickbait headlines), key terms only introduced in conclusions/end of text.

## 2. BERT (`all-MiniLM-L6-v2`) for Word Similarity

- **Maturity:** Commodity (SOTA for embedding efficiency)
- **References:** Standard in HuggingFace pipelines. Used in "Concept Heterogeneity-aware Representation Steering" (2025/26) for word distribution visualization.
- **Failure modes:**
  - **OOV**: WordPiece subword handling causes semantic noise on technical acronyms
  - **Domain drift**: Without fine-tuning, weak on medical/legal niches

## 3. Sinkhorn-Knopp Optimal Transport

- **Maturity:** Production-ready (algorithmically mature)
- **References:** "Shape Cloud: Collage on Irregular Canvas" (IEEE TVCG 2023/24) uses Sinkhorn-Knopp for global layout optimization on irregular canvases.
- **Failure modes:**
  - Numerical instability with too-small ε regularization
  - O(N²) bottleneck for N > 1000 words in browser context

## 4. SDF Algorithms — Felzenszwalb vs Meijster

- **Maturity:** Commodity
- **References:** Felzenszwalb-Huttenlocher (2012) is the gold standard (used in Mapbox TinySDF). Mathematically correct via "Lower Envelope of Parabolas".
- **Failure modes:**
  - Grid dependency: sharp corners rounded at low resolution
  - Requires sub-pixel upsampling for typographic precision

## 5. MAT Skeletonization & Pruning

- **Maturity:** Research-grade (pruning is the major hurdle)
- **References:** Lee (1982) classical, Voronoi-based alternative. "Chordal Axis Transform" pruning strategies essential for clean topology.
- **Failure modes:** Tiny boundary noise generates large skeleton spikes if pruning is insufficient.

## 6. Multi-Centric Wordle (Segmentation)

- **Maturity:** Research-grade
- **References:** "Multi-Focused Word Clouds" (IEEE VIS). AeroCloud uses this for non-convex shapes (rings, "C" shapes).
- **Failure modes:** Words can "tear" at segment boundaries or leave visual gaps between centers.

## 7. 5-Stage Collision Hierarchy

- **Maturity:** Production-ready (best practice)
- **References:** Industry standard in game engines and high-end word cloud generators (Jason Davies).
- **Failure modes:**
  - Quadtree depth too large → O(N log N) overhead exceeds O(N)
  - SAT computation expensive on complex glyph polygons (>50 vertices)

## 8. Differentiable Rendering (SoftRas / DiffRast)

- **Maturity:** Bleeding edge
- **References:** SoftRas (Liu et al. 2019), DiffRast (NVIDIA 2020). Application to text glyphs enables gradient flow through the pixel layer for positioning.
- **Failure modes:** Vanishing gradients — words far outside the shape cannot find their way back as gradient vanishes at zero overlap.

## 9. MAP-Elites (`pyribs`) for Layout

- **Maturity:** Research-grade
- **References:** pyribs library (CMU). Used for evolutionary design. Behavioral descriptors: Space-Filling (SS), Symmetry.
- **Failure modes:** Archive starvation in high-dimensional descriptor spaces — many cells remain empty, restricting diversity.

## 10. BOP-Elites (Bayesian Optimization + QD)

- **Maturity:** Bleeding edge
- **References:** Gaier & Mouret (2020/2023). Replaces random mutation with Gaussian Processes (GP).
- **Failure modes:** GP scaling — covariance matrix computation O(M³) of evaluations M. Requires Sparse GPs for large runs.

## 11. CQD Metric (GECCO 2022)

- **Maturity:** Research-grade (SOTA metric)
- **References:** Kent et al. (2022): "A Discretization-free Metric". Solves grid-dependency of MAP-Elites.
- **Failure modes:** Compute time — Monte-Carlo integration over behavior space is expensive per evaluation.

## 12. Self-Play Training

- **Maturity:** Bleeding edge
- **References:** Inspired by AlphaZero, applied to archive evolution (cross-pollination between silhouettes).
- **Failure modes:** Catastrophic forgetting — system may lose "niche styles" if archive over-optimizes for global density.

## 13. Pareto-Front in QD (CQD_HV)

- **Maturity:** Research-grade
- **References:** Hypervolume indicators in multi-objective optimization.
- **Failure modes:** Finding the true Pareto-front between density and design aesthetics is NP-hard.

## 14. Seam Carving for Word Clouds

- **Maturity:** Research-grade
- **References:** UC Davis / University of Arizona papers. Uses energy fields for whitespace compression.
- **Failure modes:** Without strict constraints, letter aspect ratios get unnaturally squeezed (e.g., "O" → "0").

## 15. Bezier Export (Sub-Millimeter)

- **Maturity:** Production-ready
- **References:** Jason Davies' Word Cloud Generator (SVG export).
- **Failure modes:** Path overlap in print (plotter/laser) causes double cuts. Requires final Boolean union operation on paths.

## Maturity Summary

| Maturity | Blueprint Sections |
|----------|---------------------|
| **Commodity** | BERT (#2), Felzenszwalb SDF (#4) |
| **Production-ready** | TF-IDF-AP (#1), Sinkhorn-Knopp (#3), 5-Stage Collision (#7), Bezier Export (#15) |
| **Research-grade** | MAT Skeletonization (#5), Multi-Centric (#6), MAP-Elites (#9), CQD (#11), Pareto in QD (#13), Seam Carving (#14) |
| **Bleeding edge** | Differentiable Rendering (#8), BOP-Elites (#10), Self-Play (#12) |

**Risk concentration:** The Inner Loop (Differentiable Rendering) and Outer Loop (BOP-Elites + Self-Play) sit in the bleeding-edge tier. These three modules require the deepest validation effort and highest test coverage in the roadmap.

---
*Researched by Gemini CLI on 2026-04-07*
