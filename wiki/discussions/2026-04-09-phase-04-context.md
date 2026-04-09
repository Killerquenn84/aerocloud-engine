# Phase 4: Geometry-v1 - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert a silhouette mask (PNG) into an exact Signed Distance Field, provide Stage-1
AABB collision primitives, and place words into the shape with a bounded, deterministic
spiral search. The public contract exposes everything the Phase 5 Renderer and Phase 6
Inner Loop need as a stable input: a signed float32 SDF with a documented sign convention,
pixel-scanned glyph AABBs that are byte-identical across Ubuntu/macOS/CI, and a structured
placement result that distinguishes placed words from dropped words with machine-readable
reasons.

**Explicitly out of scope (→ Phase 7 Geometry-v2):** Medial Axis Transform (MAT), Chordal
Axis pruning, Multi-Centric placement, BVH / Two-Level Box, Quadtree, Separating Axis
Theorem for rotated rects, bitmap pixel-exact collision, Bezier paths, rotation.

**Explicitly out of scope (→ Phase 12 Production-v1):** Disk-persisted SDF cache, SVG
mask decode, EPS sandbox, integral-occupancy map placement strategy (amueller-style).

</domain>

<decisions>
## Implementation Decisions

### Module Layout (locked)
- **D-01:** New package `packages/engine/src/aerocloud/geometry/` with submodules
  `mask.py`, `sdf.py`, `sdf_cache.py`, `collision.py`, `glyph.py`, `placement.py`,
  `errors.py`, plus shared types in `geometry/__init__.py`. Matches CLAUDE.md Regel 11
  Engine-Module list.
- **D-02:** Public API is **function-based** (not class-based). Pydantic v2 models wrap
  inputs (`MaskInput`, `GlyphRasterRequest`, `PlacementRequest`) and outputs
  (`SDFHandle`, `GlyphBBox`, `PlacementResult`). Pydantic is kept OUT of any hot inner
  loop; numpy arrays flow between internal functions as bare arrays.
- **D-03:** Module-level private mutable state is allowed **only** for the SDF cache
  (`sdf_cache._CACHE`) and the font registry (inherited from Phase 1 `fonts.py`).
  Everything else is pure.

### Mask Decoding (G-1, Claude's Discretion — ratified by architect)
- **D-04:** Decoder = Pillow. Accepted input formats v1: PNG greyscale (mode `L`), PNG
  RGB (mode `RGB`), PNG RGBA (mode `RGBA`). No JPEG, no WebP, no SVG in v1.
- **D-05:** Channel selection: if Alpha channel is present, use alpha as the mask
  (inside = alpha > 127). Otherwise convert RGB → luminance (`mode.convert("L")`) and
  threshold at 127. Greyscale is thresholded directly.
- **D-06:** Threshold is fixed at `127`. No adaptive threshold in v1 (adaptive is backlog
  for Phase 12 if user reports demand).
- **D-07:** Decoded mask stored as `numpy.ndarray[bool]` in **(height, width)** row-major
  order. Helper `mask_from_bytes(raw: bytes) -> BoolMask` lives in `geometry/mask.py`.
- **D-08:** `EmptyMaskError(GeometryError)` raised fast **before** SDF allocation if the
  decoded boolean mask has zero True pixels OR zero False pixels (both conditions break
  the exact-EDT pipeline). This is a hard fail, not a warning.

### SDF Semantics (G-2, Claude's Discretion — ratified)
- **D-09:** **Sign convention is canonical and UNCHANGEABLE:** `sdf > 0 inside`,
  `sdf == 0 on boundary`, `sdf < 0 outside`. This is documented in
  `geometry/sdf.py` module docstring, enforced by a runtime assertion in
  `validate_sdf()` and referenced from `geometry/errors.py` docstring.
  ADR-0004 at `.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md`
  will record this (Planner creates file in Wave 1).
- **D-10:** SDF dtype is **float32** at the public boundary (no int16, no float16). Codex
  g-3 review: int16 quantization causes staircasing in gradient flow that biases Phase 6
  Adam. Internal scipy EDT work is float64; cast to float32 on return.
- **D-11:** SDF computed as `edt(mask).astype(f32) - edt(~mask).astype(f32)` with
  `scipy.ndimage.distance_transform_edt` (exact Meijster algorithm). Two calls, subtract.
- **D-12:** Resolution = input-resolution. No downsampling in v1.
- **D-13:** `compute_sdf(mask: BoolMask) -> np.ndarray` is the sole construction entry
  point. Always goes through `sdf_cache.get_or_build(...)` for caching.

### Coordinate System Dogma (Architect constraint — locked)
- **D-14:** **(y, x) is canonical internally**, matching numpy row-major ordering. Every
  internal function takes and returns `(y, x)` tuples. Every numpy array is indexed
  `arr[y, x]`.
- **D-15:** **(x, y) is accepted only at the Pydantic boundary**, where Pillow-style
  (x, y) user input gets adapted. Boundary adapters in `geometry/__init__.py`:
  `xy_to_yx()` and `yx_to_xy()`. Mis-ordered inputs must be caught by Pydantic validator,
  not silently accepted.
- **D-16:** `AABB` Pydantic model carries `y_min`, `x_min`, `y_max`, `x_max` (not the
  Pillow `(left, top, right, bottom)` ordering) to make the numpy-native convention
  syntactically obvious.

### SDF Cache (G-3, 3-AI consensus — Codex BLOCKED default, redesigned)
- **D-17:** Cache library = `cachetools.LRUCache` with `getsizeof=lambda arr: arr.nbytes`
  — **bytes-bounded**, NOT entry-count-bounded. `cachetools >= 5.3` (verified active
  upstream per Gemini g-3). Dead lib flagged: `pylru` (avoid).
- **D-18:** Cache budget = **384 MiB per worker process** (Codex g-3 recommendation for
  concurrency > 1 on a 4 GB Celery worker). Value exposed via
  `config.sdf_cache_max_bytes` Pydantic setting so ops can tune without code changes.
- **D-19:** Cache value = **float32** SDF (no int16, no float16 in v1 — D-10).
- **D-20:** Cache key tuple is **content hash + preprocessing params + algorithm salt**
  so a change in threshold, decoder policy, or SDF version cannot return a stale entry:
  ```python
  key = (
      blake3(raw_mask_bytes).hexdigest(),  # strong content digest
      ("threshold", 127),                   # preprocessing params (D-06)
      ("sign", "positive_inside"),          # sign convention salt (D-09)
      ("dtype", "float32"),                 # output dtype (D-10)
      ("sdf_algo_version", 1),              # algorithm version salt
      mask.shape,                           # output shape
  )
  ```
  Codex g-3: keying on raw file bytes alone is a correctness bug — same bytes can
  yield different SDFs as preprocessing changes.
- **D-21:** Hash function = **`blake3`** (via `blake3` pypi package, active and fast)
  as primary choice, with `sha256` fallback if blake3 is not available in the
  environment. **`xxhash64` is BLOCKED** — 64-bit non-cryptographic collision risk
  poisons MAP-Elites archive reproducibility (Codex g-3 adversarial finding).
- **D-22:** Cache is guarded by a module-level `threading.RLock`. Celery prefork is
  single-threaded-per-child in practice today, but the RLock is non-negotiable
  insurance against any future thread/greenlet refactor (Regel 8 L-3). `cachetools` is
  explicitly documented as NOT thread-safe.
- **D-23:** Persistent disk cache is **DEFERRED to Phase 12**. In-memory only for v1.

### Glyph Rasterization (G-4, 3-AI consensus — Codex BLOCKED default with hallucination finding)
- **D-24:** Raster API = **`ImageFont.FreeTypeFont.getmask(char, mode="L", start=(0,0))`**,
  NOT `ImageDraw.text(...)`. Codex g-4 verified against Pillow docs. `getmask()` returns
  the raw L-mode pixel buffer; we scan non-zero pixels directly in numpy for a tight
  pixel-scanned AABB. This is the ONLY documented path.
- **D-25:** Per-glyph / per-codepoint rendering only. We never render the string `"fi"`
  and then worry about ligatures — each codepoint is rasterized independently, which
  sidesteps the `Layout.BASIC` vs `Layout.RAQM` question entirely (Codex g-4 correction).
- **D-26:** **HALLUCINATION KILLED:** The parameter `hint_style` does NOT exist in
  `ImageFont.truetype()` (Codex g-4 checked Pillow 12.1.1 stable docs
  https://pillow.readthedocs.io/en/stable/reference/ImageFont.html). Any previous plan
  citing `hint_style='none'` is void. Hinting control at the Pillow level is NOT
  available in v1; we control raster drift by pinning FreeType instead (D-28).
- **D-27:** `ImageFont.truetype()` is called with the documented signature only:
  `truetype(font_path, size=<int>, index=0, layout_engine=ImageFont.Layout.BASIC)`.
  `BASIC` is safe because we render single codepoints (D-25).
- **D-28:** **Runtime FreeType pinning:** Module-level assertion at geometry package
  import:
  ```python
  _EXPECTED_FREETYPE = "2.13.2"  # pinned by Docker base image (Phase 1 D-28)
  actual = PIL.features.version("freetype2")
  if actual != _EXPECTED_FREETYPE:
      raise GeometryEnvironmentError(
          f"FreeType version mismatch: expected {_EXPECTED_FREETYPE}, got {actual}. "
          f"macOS Homebrew Pillow is NOT supported for geometry generation; "
          f"use the pinned Docker image or the uv-pinned wheel."
      )
  ```
  Codex g-4: `PIL.features.version("freetype2")` is the documented check, NOT
  `freetype.__version__`.
- **D-29:** **Golden-corpus regression test** (`tests/regression/test_glyph_golden.py`):
  render a frozen corpus of representative glyphs (ASCII alphanumerics, German umlauts
  `ä ö ü ß`, common punctuation) from both Inter and IBM Plex Serif at 16/32/64 pt.
  Assert byte-for-byte equality of the mask buffer against committed `.npy` fixtures.
  ANY drift fails CI. This is the enforcement mechanism for cross-platform byte
  identity (Codex g-4 bottom line: "Build a golden corpus test over your shipped fonts
  and representative glyphs, and fail on any byte drift").
- **D-30:** Homebrew Pillow is **explicitly unsupported** for geometry generation runs.
  The uv workspace must install the Pillow wheel that matches the pinned FreeType
  (Phase 1 D-28 Docker base); developer machines that want to run geometry locally
  must use the Docker dev stack. CI verifies with `PIL.features.version("freetype2")`.
- **D-31:** `Image.resize()` / 4x-supersample-then-downsample trick is **BLOCKED**. Codex
  g-4: Pillow's `src/libImaging/Resample.c` uses `double`/`sin`/`cos` floating-point
  math with no byte-identity guarantee across libc/libm. We do not add a second
  FP raster stage on top of FreeType.
- **D-32:** `GlyphBBox` Pydantic model carries the pixel-scanned AABB in (y, x)
  ordering (D-16) plus the glyph's advance width (for downstream layout), the
  glyph-local pixel buffer as `numpy.ndarray[uint8]`, and the `(font_family, size_pt,
  codepoint)` identity tuple for cache keying.
- **D-33:** Glyph raster cache is a separate `cachetools.LRUCache(maxsize=2048,
  getsizeof=...)` in `geometry/glyph.py` with the same RLock pattern as SDF cache.
  Maxsize = 2048 codepoints × ~4 KiB each ≈ 8 MiB. No bytes budget needed; glyphs are
  small.
- **D-34:** If golden-corpus tests fail cross-platform in the future, escalation path
  is `freetype-py` with a statically-linked FreeType. Deferred to backlog.

### AABB Collision (GEO-05, Claude's Discretion)
- **D-35:** Stage-1 AABB collision only. Data structure: plain list of `AABB` pydantic
  models at the boundary; hot-loop collision uses `numpy.ndarray[int32]` of shape
  `(N, 4)` (columns: `y_min, x_min, y_max, x_max`) for vectorized overlap tests.
- **D-36:** Vectorized `aabb_overlap(new: ndarray[4], existing: ndarray[N, 4]) ->
  ndarray[bool, N]` in `geometry/collision.py`. Integer-only arithmetic, no FP.
- **D-37:** AABB axis-aligned only. No rotation in v1 (→ Phase 7).

### Spiral Placement (G-5, 3-AI consensus — Codex BLOCKED default, full redesign)
- **D-38:** **Per-word adaptive origin** (NOT single global POI). Each word recomputes
  its origin based on the remaining free space after previously placed words. Codex
  g-5: single-origin is a correctness failure on concave masks AND a pathological CPU
  failure on dense clouds (~4×10⁷ probes for 200 words on 2048² with single origin).
- **D-39:** Origin selection per word: compute `feasible_sdf = sdf - convolve(occupied,
  word_aabb)` (feasibility field after dilation by current word's AABB). Take the
  eps-band of the global max:
  ```python
  max_val = feasible_sdf.max()
  if max_val <= 0:
      return DroppedWord(word, reason="NO_FEASIBLE_ANCHOR")
  eps = 0.5  # half-pixel band
  candidates = np.argwhere(feasible_sdf >= max_val - eps)
  # deterministic tiebreak: closest to mask centroid, then (y, x) lex
  ```
  Codex g-5 blocked raw argmax because it biases toward top-left corner on flat maxima.
- **D-40:** Spiral math: Archimedean `r = b * theta`, `b = step / (2*pi)`. Candidate
  positions are **generated as integer offsets** in a fully specified order, deduped
  by `(dy, dx)` integer keys, and tie-broken lexicographically by
  `(radius_bin, theta_bin, y, x)`. Codex g-5: floating-point rounding must NOT define
  visit order.
- **D-41:** Step-size formula:
  `step = clamp(min(aabb_w, aabb_h, max(0, sdf_at_pos)) * 0.5, MIN_STEP, MAX_STEP)`
  with `MIN_STEP = 1`, `MAX_STEP = 16`. Note: Gemini g-5 suggested MAX_STEP=50, Codex
  g-5 warned MAX_STEP=32 creates aliasing pockets on dense clouds; we pick the safer
  MAX_STEP=16 for v1 (prefer correctness over speed; Phase 7 revisits).
- **D-42:** Per-word budget (hard):
  - `max_iterations_per_seed = 500`
  - `max_seeds_per_word = 3` (if first POI fails, retry with next-best local maxima
    from D-39's eps-band)
  - `max_wall_clock_per_word = 1.0` second (walltime guard against pathological inputs)
  Exceeding any of these terminates the word with `DroppedWord(reason=
  "ITERATION_BUDGET_EXCEEDED")`. The Codex g-5 math showed `max_iterations = 2000`
  single-origin was both too low (cannot reach outer half of 2048²) and wrong
  strategy (should be per-seed, not per-word).
- **D-43:** **Fail-fast contract:**
  ```python
  class PlacementResult(AeroCloudBase):
      placements: list[PlacedWord]
      dropped_words: list[DroppedWord]
      stats: PlacementStats

  class DropReason(StrEnum):
      NO_FEASIBLE_ANCHOR = "no_feasible_anchor"
      ITERATION_BUDGET_EXCEEDED = "iteration_budget_exceeded"
      TOO_LARGE_FOR_MASK = "too_large_for_mask"
      WALL_CLOCK_EXCEEDED = "wall_clock_exceeded"
  ```
  `PlacementFailedError(GeometryError)` is raised ONLY for contract violations: NaN
  in SDF, non-finite SDF values, dimension mismatch between mask and glyph buffer,
  negative budgets, internal invariant failure. An ordinary unplaceable word is
  **never** an exception — it goes into `dropped_words`. (Codex g-5 structured
  contract.)
- **D-44:** Reference note: `amueller/word_cloud` does **not** use a spiral — it uses
  an integral-occupancy map + `query_integral_image` with font-shrink retries (Codex
  g-5 cited). We stay with spiral for v1 because it is simpler to reason about for the
  Phase 6 differentiable renderer seed; integral-occupancy strategy is noted for
  Phase 7 Geometry-v2 backlog.

### Determinism (Project-level carry-forward)
- **D-45:** All geometry functions consume the project-wide `set_seed()` from
  `utils/determinism.py` (Phase 1). Two runs on the same input must produce
  byte-identical `PlacementResult` (verified by a dedicated test per Regel 8 Test-10
  Determinism Tests).
- **D-46:** Integer arithmetic everywhere it is possible. Where FP is unavoidable
  (SDF float32, spiral theta), the result is immediately discretized to integer pixel
  coordinates before collision tests. No FP comparisons in the hot loop.

### Observability (Architect constraint — locked)
- **D-47:** `AEROCLOUD_DEBUG_GEO=1` environment flag enables a debug dump on placement
  failures (and on every run in local dev if also `AEROCLOUD_DEBUG_GEO_ALWAYS=1`).
  Dump contents written to `./debug/geometry/<timestamp>-<repro_id>/`:
  - `mask.png` — the decoded boolean mask
  - `sdf_heatmap.png` — SDF rendered as a colormap (matplotlib, dev-only import)
  - `spiral_trace.png` — the path walked by the last failed word, overlaid on sdf
  - `placement.json` — full `PlacementResult` serialized
  - `env.json` — Pillow, FreeType, numpy, scipy versions and process info
- **D-48:** Observability uses `structlog` (Phase 1) with bound context
  `geometry.phase="placement"`, `geometry.word=...`, `geometry.budget_left=...`.
  Log levels: INFO on phase entry/exit, WARN on dropped word, ERROR on
  `PlacementFailedError`.
- **D-49:** Metrics (OpenTelemetry, Phase 1) — counters:
  `aerocloud_geometry_sdf_cache_hits_total`, `aerocloud_geometry_sdf_cache_misses_total`,
  `aerocloud_geometry_dropped_words_total{reason=...}`, histograms:
  `aerocloud_geometry_sdf_build_seconds`, `aerocloud_geometry_placement_seconds`.

### Testing (Phase Exit Gate Requirement)
- **D-50:** Test pyramid for Phase 4:
  - **Unit tests**: mask decoding (all formats, threshold, empty mask), sdf (signed
    correctness on circle/square, cache hit/miss, bytes budget eviction), collision
    (vectorized overlap, edge cases), glyph (getmask, golden fixtures), placement
    (deterministic tie-break, fail-fast contract, dropped word reasons).
  - **Property tests** (hypothesis): random masks produce non-NaN float32 SDF with
    `sign(sdf) == (2*mask-1)`; SDF is symmetric under mask inversion up to sign;
    cache never returns wrong value for any key.
  - **Integration tests**: end-to-end mask-to-PlacementResult for circle, square,
    rectangle, C-shape (concave — should produce valid placements), empty mask
    (should raise `EmptyMaskError`).
  - **Determinism tests**: same input byte-identical output over 10 repeated runs.
  - **Golden regression**: the glyph corpus from D-29. FAIL on any byte drift.
  - Target: ≥ 50 new tests, total codebase crosses 160 tests.
- **D-51:** NO mocking of Pillow, scipy, numpy in any test. Regel 8 — tests use real
  dependencies. Hermetic fixtures (circle, square, crescent, C) committed as `.npy`.

### Claude's Discretion
- G-1 Mask decoding (ratified)
- G-2 SDF semantics (ratified, with sign convention hard-locked in D-09)
- G-6 Public API shape (ratified)
- Concrete MIN_STEP / MAX_STEP tuning within the locked bounds (D-41)
- Exact `GeometryError` subclass hierarchy, as long as `EmptyMaskError`,
  `GeometryEnvironmentError`, and `PlacementFailedError` exist as D-08 / D-28 / D-43
  specify
- Exact file splits inside `geometry/` as long as D-01 module list is preserved

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level (Phase 1 + 2 + 3 carryover)
- `.planning/ROADMAP.md` §"Phase 4: Geometry-v1" — phase goal, success criteria,
  GEO-01..07 mapping
- `.planning/REQUIREMENTS.md` §"Geometry-v1 (Phase 4)" — GEO-01..07 acceptance criteria
- `.planning/research/PITFALLS.md` §"Meijster EDT correctness", §"measureText avoidance"
- `.planning/phases/01-foundation/01-CONTEXT.md` §D-11..D-13 Determinism, §D-28 Fonts
- `.planning/phases/02-datenmodell-wiki/02-CONTEXT.md` §"Pydantic v2 models", §"Repro ID"
- `.planning/phases/03-nlp-v1/03-CONTEXT.md` §"Hermetic tests pattern"

### Phase 4 new ADRs (Planner to create in Wave 1)
- `.planning/phases/04-geometry-v1/adr-0004-sdf-sign-convention.md` — documents D-09
  sign convention as UNCHANGEABLE (see D-09)
- `.planning/phases/04-geometry-v1/adr-0005-coordinate-system-yx.md` — documents D-14
  (y, x) canonical ordering
- `.planning/phases/04-geometry-v1/adr-0006-freetype-pinning.md` — documents D-28
  FreeType runtime assertion and Homebrew block

### 3-KI Review Artifacts (Codex adversarial BLOCKED all 3, Gemini research)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md` — SDF cache BLOCKED,
  int16 quantization BLOCKED, maxsize=50 BLOCKED, xxhash BLOCKED
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md` — Glyph raster BLOCKED,
  `hint_style` halluci-check, Homebrew Pillow drift, `Image.resize` BLOCKED,
  `getmask()` + pinned FreeType recommendation
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g5.md` — Spiral single-origin
  BLOCKED, MAX_STEP aliasing math, per-word adaptive origin required,
  structured `dropped_words` contract
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g3.md` — `cachetools` +
  `xxhash` + `uint16` code patterns (Gemini research; int16/xxhash **NOT
  adopted**, superseded by Codex g-3 BLOCK findings)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g5.md` — POI algorithm + step
  clamp code snippets (adapted: MIN_STEP=1, MAX_STEP=16 instead of Gemini's
  MAX_STEP=50 per Codex g-5 aliasing warning)
- `.planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g4.md` — Gemini UNAVAILABLE
  (gemini-3-flash-preview + 2.5-pro + 2.5-flash all returned 429 capacity-exhausted).
  Codex g-4 + architect input serve as sole external verification.

### External documentation (verified by Codex against live sources)
- https://pillow.readthedocs.io/en/stable/reference/ImageFont.html —
  `ImageFont.truetype` signature (NO `hint_style`), `FreeTypeFont.getmask()` API
- https://pillow.readthedocs.io/en/stable/reference/features.html —
  `PIL.features.version("freetype2")` for runtime pinning (D-28)
- https://pillow.readthedocs.io/en/latest/installation/basic-installation.html —
  Pillow wheel vs Homebrew packaging difference (D-30)
- https://formulae.brew.sh/formula/pillow — Homebrew Pillow freetype dependency
- https://formulae.brew.sh/formula/freetype — Homebrew freetype 2.14.2 (drift risk)
- https://numpy.org/doc/1.25/reference/generated/numpy.argmax.html — `np.argmax`
  first-occurrence determinism (D-39)
- https://amueller.github.io/word_cloud/_modules/wordcloud/wordcloud.html —
  `query_integral_image` reference implementation (noted for Phase 7, NOT v1)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html
  — exact Meijster EDT

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/engine/src/aerocloud/utils/determinism.py` — `set_seed()` for reproducibility
  (D-45)
- `packages/engine/src/aerocloud/fonts.py` — `font_path(family)` returns TrueType file path
  for Inter + IBM Plex Serif (Phase 1 D-28, resource loading via `importlib.resources`)
- `packages/engine/src/aerocloud/models/base.py` — `AeroCloudBase(frozen=True,
  strict=True, extra="forbid")` — base class for all Pydantic models in geometry
- `packages/engine/src/aerocloud/observability.py` — structlog + OpenTelemetry
  initialization, bound context pattern (D-48)
- `packages/engine/src/aerocloud/config.py` — Pydantic Settings loader (D-18
  `sdf_cache_max_bytes`)
- `packages/engine/src/aerocloud/repro.py` — `ReproducibilityID` for debug dumps (D-47)

### Established Patterns
- **Hermetic tests**: Phase 3 Wave 2 showed `spacy.load` can be patched for tests; same
  pattern can be used for heavy geometry fixtures. But for glyph golden tests we use
  REAL Pillow + REAL FreeType (D-29) to exercise the cross-platform raster stack.
- **Module-level caches with RLock**: Phase 3 `tokenize.py` spaCy registry pattern
  (`_NLP_REGISTRY` dict guarded by `threading.RLock`) is the template for D-22 SDF
  cache and D-33 glyph cache.
- **Pydantic-on-boundary, numpy-in-hot-loop**: Phase 2 data models + Phase 3 NLP
  pipeline both use this split. D-02 continues it.
- **Fail-fast errors at the top of the function**: Phase 3 Wave 4 `N-6` lesson —
  validate font range bounds BEFORE any expensive work. D-08 applies to `compute_sdf`.
- **Canonical refs accumulator**: This CONTEXT already includes docs the user will
  need. Planner will expand ADR-0004/0005/0006 into their own files in Wave 1.

### Integration Points
- Phase 5 Renderer-v1 consumes `SDFHandle` + `PlacementResult` from Phase 4. The
  contract is: signed float32 SDF (D-09, D-10) + `list[PlacedWord]` with deterministic
  integer `(y, x, w, h)` AABBs.
- Phase 6 Inner Loop consumes the same SDF as its loss fidelity signal. Float32
  gradient flow (D-10) is the hard constraint that killed int16 quantization.
- Phase 9 MAP-Elites consumes glyph AABBs as part of the behavioral descriptor. Byte
  drift in glyph raster = different archive cell. D-29 golden corpus is the firewall.

</code_context>

<specifics>
## Specific Ideas

- Architect quote (locked as the phase mantra): *"Absolutes Scope-Creep-Verbot. Unser
  alleiniges Ziel ist der Vertikale Durchstich zum PyTorch Inner Loop. Wenn wir eine
  primitive, aber extrem robuste AABB-Kollision haben, reicht das als Start-State fuer
  den Adam Optimizer in Phase 5."*
- Architect's four leitplanken (D-08, D-09, D-14, D-47) are sacrosanct. Phase 4 Wave 1
  creates ADR files for each before any production code.
- The `dropped_words` contract (D-43) is non-negotiable — Phase 5 Inner Loop needs
  structured failure reasons, not log-parsing.
- Cross-platform byte identity (D-29) is worth a whole CI matrix job: macOS +
  Ubuntu 22.04 + CUDA-base Docker must all produce identical `.npy` golden files.

</specifics>

<deferred>
## Deferred Ideas

### → Phase 7 Geometry-v2
- Medial Axis Transform (MAT) via `scikit-fmm`
- Chordal Axis pruning
- Multi-Centric placement (one spiral origin per MAT branch)
- Stage 2-5 collision (Two-Level Box, Quadtree, SAT, Bitmap)
- Rotation support
- amueller-style integral-occupancy map as an alternative placement engine (Codex g-5
  flagged this as the "real" approach used in production word clouds; evaluate as an
  optional Phase 7 strategy alongside MAT-based multi-centric spiral)
- Font-shrink retry pattern from amueller (shrink current word by ~10% and retry when
  all seeds fail)

### → Phase 12 Production-v1
- Disk-persisted SDF cache (`.cache/aerocloud/sdf/`) with content-addressed storage
- Adaptive threshold for mask decoding (non-Otsu input)
- SVG silhouette rasterization (via `cairosvg` in isolated sandbox)
- EPS silhouette ingest via sandboxed Ghostscript

### → Phase 4 backlog (only if golden-corpus CI fails cross-platform)
- Switch glyph raster stack from Pillow+pinned-FreeType to `freetype-py` with
  statically-linked FreeType (Codex g-4 escalation path, D-34)
- Custom Rust extension for glyph rasterization via `ab_glyph` or `fontdue`

### Reviewed Todos (not folded)
No pending todos matched Phase 4 at discussion time (`gsd-tools todo match-phase 4` = 0).

</deferred>

---

*Phase: 04-geometry-v1*
*Context gathered: 2026-04-09*
*3-KI review: Codex BLOCKED-then-redesigned all 3 risk areas (G-3/G-4/G-5), Gemini
partial (g-3 + g-5 only — g-4 capacity-exhausted, Codex + architect served as sole
external verification for G-4).*
