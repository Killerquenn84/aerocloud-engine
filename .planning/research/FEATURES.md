# Feature Landscape: Word Cloud Engine

**Domain:** Word Cloud Rendering Engine (Shopify merchant marketing tool)
**Researched:** 2026-04-06
**Overall confidence:** HIGH (features grounded in d3-cloud source, WordArt.com, Mentimeter, competitor analysis, and AeroCloud Blueprint)

---

## Context

AeroCloud Engine is a server-side word cloud rendering engine. It is NOT a live-audience tool (unlike Mentimeter/Slido) and NOT a frontend-only widget. It is a Node.js rendering service called from a Shopify app's BullMQ worker queue. Users are Shopify merchants creating marketing images (social media, product pages, print-on-demand merchandise like mugs and T-shirts).

This context matters for feature prioritization: output quality, silhouette fidelity, and export format matter more than real-time interaction or audience polling.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Text input + word frequency counting | Every word cloud engine does this; without it the product doesn't exist | Low | Must handle copy-paste text blobs; auto-count word frequencies |
| Frequency-based font sizing (Zipf-normalized) | The core visual contract of word clouds — important words are bigger | Low-Medium | Linear scaling is wrong; log-normalization required (Blueprint Part I) |
| Collision-free placement | Words overlapping = broken product; non-negotiable | High | Requires bitmap-level collision detection; d3-cloud drops words if it can't place them — AeroCloud must not |
| Silhouette / mask support | The primary differentiator of AeroCloud vs. d3-cloud; rectangular clouds feel outdated | High | SDF generation from PNG/SVG silhouette required; this is the reason the engine exists |
| Stopword removal | "the", "and", "is" dominate naively — users expect these filtered | Low | English stopword list built-in; custom stopword override as input parameter |
| PNG export | All downstream use cases (social media, Shopify product images, print) require PNG | Low | node-canvas toBuffer() |
| SVG export | Required for print quality, scalable for merchandise | Medium | Must produce clean vector paths, not just rasterized canvas dump |
| Configurable canvas dimensions | Different use cases need different aspect ratios (square for Instagram, 16:9 for banners) | Low | Width + height parameters |
| At least 3 color modes | Monochromatic, gradient, random-from-palette — users expect visual variety | Low-Medium | Color theming is table stakes per all competitor analysis |
| Font selection (built-in set) | Users expect to match their brand typeface | Medium | Minimum 5-8 bundled fonts; custom font upload is differentiator, not table stakes |
| Background color control | Transparent background and solid colors are expected for all use cases | Low | Transparent PNG is essential for merchandise overlay |

---

## Standard Features Expected

Features that sophisticated users expect. Missing hurts conversion but does not immediately break the product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Controlled rotation (0, 90 degrees only) | Users expect some vertical words for visual density; unlimited rotation hurts readability | Low | Hard limit to 0/90 or 0/45/90 angles only — see Anti-Features for why unlimited rotation is banned |
| Word weighting override | Users want to manually boost/penalize specific words beyond raw frequency | Low | Per-word weight multiplier in input payload |
| Maximum word count cap | Overcrowded clouds are illegible; capping at 100-150 words is standard practice | Low | Default cap of 100 words; configurable |
| Minimum font size floor | Very small words (< 10px) become unreadable; all competitors enforce a minimum | Low | 10-12px floor prevents rendering noise |
| Multiple languages | Shopify merchants are global; German, French, Spanish, Japanese are common markets | Medium | Tokenization + stopwords per language; CJK requires separate font stack and character segmentation |
| Padding/margin between words | Words that touch are nearly as bad as overlapping; word breathing room is expected | Low-Medium | Per-word padding as SDF expansion factor |
| Reproducible output (seed-based) | Merchants regenerate the same product image — they need deterministic output | Low | Random seed parameter; same seed + same input = same output |
| API-first design (HTTP JSON) | Engine is called from BullMQ — REST API is not a feature, it is the interface | Medium | Fastify v5 POST /render endpoint; returns PNG/SVG binary or base64 |
| High-resolution output (2x, 4x) | Print-on-demand (mugs, T-shirts) requires 300 DPI minimum | Medium | Canvas scaling factor parameter; 4x = 4x memory cost, must be managed |
| Custom stopword list per request | Merchants in different niches have domain-specific junk words | Low | Additive to default stopword list; input parameter |

---

## Differentiators

Features that set AeroCloud apart from d3-cloud, wordcloud2.js, and generic SaaS tools. Not universally expected, but create clear competitive separation.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Precise silhouette fill with SDF-gradient descent | Generic tools either ignore the silhouette boundary or leave large gaps at edges; AeroCloud fills to the pixel boundary | High | Core engine feature; SDF gradient pulls words toward unfilled regions inside shape |
| Zero dropped words guarantee | d3-cloud explicitly drops words it cannot place; AeroCloud must place every word or shrink it until it fits | High | Requires fallback sizing: shrink word font size progressively until it fits; log this as a quality metric |
| Medial Axis Transform for skeleton-aware placement | Large words placed along the skeleton of complex shapes (e.g., a horse silhouette places the title word in the body, not the leg) | High | MAT identifies the widest passages in the silhouette; large words are guided there |
| TF-IDF-AP scoring (positional weight) | Raw frequency treats "Product" in a title the same as "product" in body text; TF-IDF-AP gives semantic weight to prominent positions | Medium | Boosts words from H1/title/first-sentence; 12.9% semantic precision improvement per Blueprint |
| Semantic word size hierarchy (Zipf-correct) | Most engines use sqrt(frequency) which compresses visual hierarchy; log(frequency) preserves the natural power-law of language | Low-Medium | Blueprint section 1.2; log normalization is mathematically correct for natural language |
| Force-directed layout refinement | After initial spiral placement, force-directed micro-adjustment improves packing density and reduces wasted whitespace | High | d3-force-style physics; runs as post-pass after spiral placement |
| Multi-centric placement for non-convex shapes | Complex silhouettes (letters, animals with limbs) have multiple "centers"; single-spiral placement leaves limbs empty | High | MAT branch detection; one spiral per skeletal branch |
| Coarse-to-fine rendering pipeline | 8px -> 32px -> 128px -> full resolution prevents wasted computation; enables < 500ms for 200 words target | Medium | Blueprint section 5.4; critical for production throughput |
| Per-word semantic color assignment (v2) | Words from the same semantic cluster receive the same color; visual grouping without requiring user to categorize | Very High | Requires BERT embeddings; deferred to v2 per PROJECT.md |
| Quality-Diversity (MAP-Elites) outer loop (v2) | Instead of one output, proposes 4-9 layout variants along Pareto front (density vs. aesthetics); user picks favorite | Very High | Deferred to v2; requires thousands of evaluations |
| CQD Pareto slider (v2) | Interactive slider between "fill every pixel" and "prefer open/airy design" without re-rendering | Very High | Depends on MAP-Elites archive; v2 |

---

## Anti-Features

Features to explicitly NOT build, or to build in a constrained way that prevents the common failure mode.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Unlimited / arbitrary rotation angles | Research (Berkeley iSchool 2019, Apache Superset PR #19977) confirms random rotation makes individual words nearly unreadable and creates visual chaos. Users complain about 45-degree diagonal words in every major tool. | Hard-cap rotation choices to: 0 degrees only (horizontal) OR 0 + 90 degrees (horizontal + vertical). Never allow 30, 45, 60, or arbitrary angles. This is a product constraint, not a missing feature. |
| "Fill with noise words" to increase density | Some tools pad word clouds with very low-weight filler words to make the shape look fuller. This degrades semantic meaning — the primary value of a word cloud. | Use force-directed refinement and SDF-gradient descent to achieve density without adding noise. If the input text is sparse, expose that honestly via quality metrics. |
| Placing words outside the silhouette boundary | Some mask implementations simply clip overflow at render time — words can partially overlap the boundary. This looks sloppy on merchandise. | SDF boundary enforcement: reject any word placement where any pixel of the word's bounding box falls outside SDF <= 0. |
| Synchronous blocking render in HTTP handler | For large inputs (500+ words, complex silhouette, 4x resolution), rendering can take 2-10 seconds. Doing this synchronously blocks the Fastify worker thread. | The engine itself may be synchronous internally, but the Fastify endpoint must respond via streaming or the caller (BullMQ worker) must be async — engine is a sub-process, not a request handler. |
| Accepting SVG input for silhouettes without sanitization | SVG files can contain JavaScript, external entity references, and SSRF vectors. Blindly feeding merchant-uploaded SVGs to the renderer is a security hole. | DOMPurify sanitization before SVG processing; convert to raster mask before use in rendering pipeline. |
| Rendering directly from raw user text without NLP | Naive frequency counting produces poor results: common function words dominate, compound words split incorrectly, no semantic grouping. | Always run through NLP pipeline (tokenization, lemmatization, stopword removal, TF-IDF-AP) before sizing. |
| Deterministic placement without a seed parameter | Non-reproducible output means merchants cannot regenerate the same image for a product. Support tickets increase. | Every render call must accept a random seed; same seed + same input = byte-identical output. |
| Custom font upload without validation | Malformed font files crash the canvas renderer; OTF/TTF files can embed JavaScript in some formats. | Validate font file MIME type, size limit (max 2MB), and attempt a test render before accepting into the system. |
| Very small minimum font size (< 8px) | Words below 8px at standard resolution are invisible noise that pollutes the visual and wastes layout space. | Minimum font size of 10px at 1x resolution. Words that would be smaller are dropped — but the word count cap should prevent the long tail from being needed. |

---

## Feature Dependencies

```
TF-IDF-AP scoring
  └── requires: Tokenization + Lemmatization (NLP pipeline)
  └── requires: Stopword removal
  └── enables: Zipf-normalized font sizing

Silhouette placement
  └── requires: SDF generation from input mask
  └── requires: Medial Axis Transform (for multi-centric + skeleton guidance)
  └── requires: Bitmap collision detection (quadtree + 32-bit INT masks)
  └── enables: Zero-dropped-words guarantee
  └── enables: Precise boundary fill

Force-directed refinement
  └── requires: Initial spiral placement (silhouette placement above)
  └── requires: Quadtree spatial index
  └── enables: Higher packing density

Coarse-to-fine pipeline
  └── requires: SDF (works at any resolution)
  └── enables: < 500ms performance target

High-resolution export (4x)
  └── requires: Canvas scaling (trivial)
  └── requires: Memory budget management (non-trivial)

Reproducible output
  └── requires: Seeded PRNG throughout entire pipeline (spiral, force-directed, color assignment)

Multi-language support
  └── requires: Per-language stopword lists
  └── requires: CJK font stack + character segmentation (Japanese, Chinese, Korean)
  └── partially blocks: Lemmatization (language-specific)

SVG export
  └── requires: Canvas-to-SVG conversion or parallel SVG rendering pipeline
  └── note: SVG with embedded fonts is significantly larger than PNG — consider separate endpoint

Semantic color clustering (v2)
  └── requires: BERT embeddings (deferred to v2)
  └── requires: k-means or UMAP clustering

MAP-Elites / QD outer loop (v2)
  └── requires: CQD metric implementation
  └── requires: Semantic color clustering (v2)
  └── requires: Thousands of render evaluations (GPU or parallelized)
```

---

## MVP Recommendation

For v1 (current milestone scope per PROJECT.md), prioritize in order:

1. **NLP pipeline** (tokenization, lemmatization, TF-IDF-AP, stopword removal) — without this, sizing is meaningless
2. **SDF generation from PNG silhouette** — the core product promise
3. **Medial Axis Transform** — required for quality placement in non-trivial shapes
4. **Spiral placement with bitmap collision detection** — standard Wordle-style placement inside SDF boundary
5. **Force-directed refinement** — turns acceptable output into high-quality output
6. **Coarse-to-fine pipeline** — makes v1 fast enough (< 500ms target)
7. **PNG + SVG export** — both are needed for Shopify merchant use cases
8. **Fastify v5 HTTP API** — interface to parent Shopify app BullMQ workers
9. **Seed-based reproducibility** — prevents support tickets from day one
10. **Basic color schemes** (monochromatic, palette-based) — minimum viable visual polish

Defer to v2:
- BERT semantic clustering and semantic color assignment (heavy ML dep)
- MAP-Elites / Quality-Diversity outer loop
- Animated output (Three.js/WebGL — frontend concern)
- CJK multi-language (requires separate font stack and segmentation investment)
- Bezier-optimized SVG paths (standard canvas SVG sufficient for v1)
- Seam Carving whitespace compression

---

## Competitive Gap Analysis

| Feature | d3-cloud | wordcloud2.js | WordArt.com | Python wordcloud | AeroCloud Target |
|---------|----------|--------------|-------------|-----------------|-----------------|
| Silhouette / mask | No | Partial (buggy) | Yes (manual) | Yes (numpy mask) | Yes (SDF-precise) |
| Collision method | Spiral + bitmap | Bitmap | Unknown | Bitmap | 5-stage hierarchy |
| Words dropped when no space | Yes (explicit) | Yes | Unknown | Yes | No (shrink-to-fit) |
| Skeleton-aware placement | No | No | No | No | Yes (MAT) |
| Zipf-correct font sizing | No (sqrt) | No | Unknown | No | Yes (log) |
| TF-IDF scoring | No | No | No | No | Yes (TF-IDF-AP) |
| Force-directed refinement | No | No | No | No | Yes |
| Coarse-to-fine | No | No | Unknown | No | Yes |
| Seeded reproducibility | Yes | No | No | Yes | Yes |
| SVG export | Yes | No | Yes (paid) | No | Yes |
| API-first | No | No | REST API (SaaS) | No | Yes (Fastify) |
| Node.js native | Yes | Yes | No | No | Yes |

---

## Sources

- d3-cloud GitHub: https://github.com/jasondavies/d3-cloud (HIGH confidence — primary source code)
- wordcloud2.js mask issue: https://github.com/timdream/wordcloud2.js/issues/94 (MEDIUM confidence)
- WordArt.com feature set: https://wordart.com (MEDIUM confidence — marketing page)
- Mentimeter word cloud: https://www.mentimeter.com/features/word-cloud (HIGH confidence — product page)
- Jason Davies algorithm description: https://www.jasondavies.com/wordcloud/about/ (HIGH confidence)
- IXD@Pratt word cloud UX analysis: https://ixd.prattsi.org/2018/11/word-clouds-in-four-steps-the-good-the-bad-and-the-ugly/ (MEDIUM confidence)
- Berkeley iSchool word cloud critique: https://www.ischool.berkeley.edu/news/2019/word-clouds-we-cant-make-them-go-away-so-lets-improve-them (MEDIUM confidence)
- Apache Superset rotation fix PR: https://github.com/apache/superset/pull/19977 (HIGH confidence — engineering evidence)
- Semantic word cloud (University of Arizona): http://wordcloud.cs.arizona.edu/description.html (MEDIUM confidence)
- AeroCloud Blueprint: raw/sources/AeroCloud-Blueprint.md (HIGH confidence — primary spec)
- AeroCloud PROJECT.md: .planning/PROJECT.md (HIGH confidence — current scope definition)
- Crawlspider Shopify word cloud use cases: https://www.crawlspider.com/word-clouds-for-e-commerce-uncovering-product-reviews-and-customer-sentiment/ (MEDIUM confidence)
