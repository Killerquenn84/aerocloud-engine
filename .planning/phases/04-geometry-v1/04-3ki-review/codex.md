Reading additional input from stdin...
OpenAI Codex v0.118.0 (research preview)
--------
workdir: /var/www/wordcloud-app-v2/server/aerocloud-engine
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019d7438-9e3a-7090-add9-329fa9c7f269
--------
user
You are the adversarial reviewer for Phase 4 Geometry-v1 of the AeroCloud Engine, a Python word-cloud rendering system. This is a FINAL phase exit review — you must find any BLOCKING issues that would require fixing before Phase 4 can be closed.

## Phase Summary

Phase 4 shipped 6 waves across 10 production files:
- packages/engine/src/aerocloud/geometry/mask.py       (PNG decoder)
- packages/engine/src/aerocloud/geometry/sdf.py        (scipy EDT, sign convention)
- packages/engine/src/aerocloud/geometry/sdf_cache.py  (bytes-bounded LRU + RLock)
- packages/engine/src/aerocloud/geometry/glyph.py      (FreeType getmask, golden corpus)
- packages/engine/src/aerocloud/geometry/collision.py  (vectorized AABB)
- packages/engine/src/aerocloud/geometry/placement.py  (per-word adaptive POI spiral)
- packages/engine/src/aerocloud/geometry/debug.py      (dev debug dump, lazy matplotlib)
- packages/engine/src/aerocloud/geometry/metrics.py    (OTel instruments)
- packages/engine/src/aerocloud/geometry/errors.py     (typed error hierarchy)
- packages/engine/src/aerocloud/geometry/__init__.py   (FreeType assertion + coord adapters)
- packages/engine/src/aerocloud/models/geometry.py     (Pydantic contracts)

Test count: 595 green. mypy strict: 0 errors. ruff: 0 errors.

## Your Prior G-3/G-4/G-5 BLOCK Findings — Verify These Were Fixed

G-3 BLOCKED (SDF cache):
1. Cache must be BYTES-bounded (not entry-count maxsize=50): REQUIRES cachetools.LRUCache with getsizeof=lambda arr: arr.nbytes
2. Hash function must be blake3 (not xxhash64): xxhash64 risk = MAP-Elites reproducibility corruption
3. Cache value dtype must be float32 (not int16): int16 causes optimizer gradient stairstepping
4. Cache key must be a 6-component composite: (blake3_digest, threshold, sign, dtype, algo_version, shape)

G-4 BLOCKED (glyph rasterization):
5. hint_style parameter must be ABSENT from ImageFont.truetype() calls — it does not exist in Pillow
6. Image.resize() must be ABSENT from glyph.py — floating-point resampling breaks cross-platform byte identity
7. PIL.features.version("freetype2") must be used for runtime version check (NOT freetype.__version__)
8. Golden corpus (.npy fixtures) must be committed and CI-verified

G-5 BLOCKED (spiral placement):
9. Per-word adaptive POI origin (NOT single global origin) — single origin is concave-mask failure + O(4e7) worst case
10. MAX_STEP=16 (NOT 32 or 50) — higher values create aliasing pockets that hide valid placements
11. Integer offset generation with lex tiebreak — FP rounding must NOT define visit order
12. Per-seed budget 500 (NOT per-word max_iterations=2000) — per-word budget cannot reach outer canvas half
13. PlacementFailedError ONLY on contract violations — ordinary drops go to dropped_words list
14. Structured DropReason enum with 4 values: NO_FEASIBLE_ANCHOR, ITERATION_BUDGET_EXCEEDED, TOO_LARGE_FOR_MASK, WALL_CLOCK_EXCEEDED

## Two Deviations Requiring Your Verdict

### Deviation 1 — place_words Performance
- Budget from 04-VALIDATION.md: place_words 100 words @ 1024² < 5.0 s
- Actual on Hostinger VPS: 24.85 s mean (5× over budget)
- Root cause: per-word scipy.ndimage.minimum_filter on 1024² canvas ~0.25 s per call × 100 words
- Prediction: RESEARCH.md §12 R-6 predicted this exactly ("Per-word adaptive POI is too slow — 0.2s × 100 words = 20 s/job")
- Mitigation in place: CI ceiling raised to 60 s to catch regressions; 5 s target documented as production CI target
- Mitigation options: (a) accept VPS hardware ceiling, (b) narrow-search-to-eps-band optimization, (c) integral-occupancy pull-forward from Phase 7, (d) document as v1 known limit

YOUR VERDICT on Deviation 1: Is the 24.85 s on this VPS an acceptable v1 known limitation (APPROVED) or does it require algorithmic improvement before phase exit (BLOCKED)?

### Deviation 2 — FreeType Pin Mismatch
- ADR-0006 pins FreeType to 2.13.2 (Docker base image)
- Server reality: FreeType 2.14.3
- Code handling: AEROCLOUD_SKIP_FREETYPE_CHECK=1 env var bypass in __init__.py + conftest.py monkeypatch
- Golden corpus fixtures (.npy) were generated on this server with FreeType 2.14.3
- Risk: if CI runs on a 2.13.2 FreeType environment, golden corpus tests may fail
- Options: (a) update ADR-0006 to pin 2.14.3, (b) regenerate on 2.13.2, (c) defer to Phase 12

YOUR VERDICT on Deviation 2: Is the AEROCLOUD_SKIP_FREETYPE_CHECK bypass acceptable for v1 (APPROVED) or must ADR-0006 be updated to 2.14.3 before phase exit (APPROVED-WITH-FIXES)?

## Adversarial Focus Areas

### Area 1 — RLock Deadlock Hunt
Prove that compute_sdf() is NEVER called while _CACHE_LOCK is held.
The code pattern in sdf_cache.get_or_build() is:
  1. with _CACHE_LOCK: check cache (fast path)
  2. sdf = compute_sdf(mask)  <-- OUTSIDE lock
  3. with _CACHE_LOCK: double-check + insert (slow path)

Is there any code path where compute_sdf() could be called inside a with _CACHE_LOCK block?
Could a recursive call chain lead to the RLock being held twice (which is safe for RLock)
but compute_sdf running inside the lock?

### Area 2 — Integer Overflow in AABB Math
collision.py casts to int64 before overlap tests:
  ny0, nx0, ny1, nx1 = new.astype(np.int64, copy=False)
For a 4096×4096 canvas, coordinates are at most 4096. 4096² = 16,777,216 which fits int16.
Is the int64 cast necessary? Could it hide a bug where int32 coordinates are passed
but arithmetic overflows?
What is the actual max coordinate that can flow through the AABB system?

### Area 3 — Spiral Determinism Under FP Drift
archimedean_offsets() uses math.floor(r * math.sin(theta) + 0.5) to generate integer offsets.
math.sin() is libc-dependent. Could two different libc implementations (glibc vs musl)
produce different integer results for the same theta?
At what theta values is this risk highest? Is the EPS_BAND=0.5 in select_origin
sufficient to absorb any such drift?

### Area 4 — Placement Contract Holes
PlacementRequest.words is list[tuple[str, int, int]] — (text, aabb_h, aabb_w).
What happens if aabb_h or aabb_w is 0? Is it caught before the spiral search?
What happens if a word tuple has aabb_h > canvas_height? Does it hit the TOO_LARGE_FOR_MASK guard?
Is there a missing validation for negative dimensions?

### Area 5 — Observability Leaks
The debug dump writes to ./debug/geometry/<ts>-<tag>/placement.json which includes
the full PlacementResult.model_dump(mode="json").
Does placement.json include any sensitive data (user text content, user uploaded mask bytes)?
The raw_png_bytes field in PlacementRequest — is it serialized into placement.json?

## Output Format

Your response must be a markdown document with sections:
1. G-3/G-4/G-5 Re-Verification (table: finding, status, evidence)
2. Deviation 1 Verdict (performance) with rationale
3. Deviation 2 Verdict (FreeType pin) with rationale
4. Adversarial Findings (Critical / Major / Minor / None)
5. Final line: VERDICT: APPROVED | APPROVED-WITH-FIXES | BLOCKED

Start with a one-paragraph executive summary.
warning: Codex could not find system bubblewrap on PATH. Please install bubblewrap with your package manager. Codex will use the vendored bubblewrap in the meantime.
codex
Reviewing the Phase 4 geometry implementation against the prior blockers and the two declared deviations. I’m starting by reading the geometry modules, contracts, and tests that cover cache, glyph rasterization, placement, debug serialization, and FreeType/version handling.
2026-04-09T21:49:37.172067Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,260p' packages/engine/src/aerocloud/geometry/glyph.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.172073Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "rg -n \"_CACHE_LOCK|compute_sdf|get_or_build|blake3|LRUCache|getsizeof|nbytes|float32|algo_version|hint_style|Image\\.resize|freetype2|golden|AEROCLOUD_SKIP_FREETYPE_CHECK|MAX_STEP|archimedean_offsets|PlacementFailedError|DropReason|minimum_filter|EPS_BAND|TOO_LARGE_FOR_MASK|raw_png_bytes|placement.json|model_dump\\(|debug/geometry|int64|astype\\(np.int64|aabb_h|aabb_w\" packages/engine/src packages/engine/tests"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.175093Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,240p' packages/engine/src/aerocloud/geometry/collision.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.184441Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,260p' packages/engine/src/aerocloud/geometry/debug.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.184589Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,240p' packages/engine/src/aerocloud/geometry/__init__.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.184683Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,260p' packages/engine/src/aerocloud/models/geometry.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.184777Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,320p' packages/engine/src/aerocloud/geometry/placement.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:37.196209Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/bash -lc "sed -n '1,240p' packages/engine/src/aerocloud/geometry/sdf_cache.py"`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
codex
Shell access is blocked by the current sandbox, so I’m switching to available workspace resources to inspect the code and tests directly. I need the actual source to make a defensible exit decision rather than infer from the phase summary.
mcp: codex/list_mcp_resources started
mcp: codex/list_mcp_resource_templates started
mcp: codex/list_mcp_resources (completed)
mcp: codex/list_mcp_resource_templates (completed)
codex
No MCP resources are exposed either. I’m testing whether there’s any shell invocation shape that can still read files; if not, I’ll have to scope the review to what can be proven from the materials in this thread alone.
2026-04-09T21:49:46.543293Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/sh -c pwd`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
2026-04-09T21:49:46.544897Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/sh -c ls`: CreateProcess { message: "Codex(Sandbox(Denied { output: ExecToolCallOutput { exit_code: 1, stdout: StreamOutput { text: \"\", truncated_after_lines: None }, stderr: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, aggregated_output: StreamOutput { text: \"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\\n\", truncated_after_lines: None }, duration: 0ns, timed_out: false }, network_policy_decision: None }))" }
codex
Phase 4 is not ready for exit. On the facts provided, the declared `place_words` acceptance target is missed by 5x on the stated production-class VPS, and the miss is caused by the exact algorithmic hotspot already predicted in research rather than by incidental noise. Separately, the FreeType/runtime/fixture contract is internally inconsistent and needs alignment before this phase can be called reproducible. I also cannot independently re-verify the earlier G-3/G-4/G-5 fixes from source in this session because file inspection was blocked by the sandbox, so those items remain unproven here rather than cleared.

## 1. G-3/G-4/G-5 Re-Verification

| Finding | Status | Evidence |
|---|---|---|
| G-3.1 SDF cache is bytes-bounded via `getsizeof=lambda arr: arr.nbytes` | Unverified in this review | Source inspection was not possible in this session, so I could not confirm the actual cache constructor or eviction accounting. |
| G-3.2 Hash function is `blake3` rather than `xxhash64` | Unverified in this review | No direct code evidence available. |
| G-3.3 Cache value dtype is `float32` rather than `int16` | Unverified in this review | No direct code evidence available. |
| G-3.4 Cache key is 6-part composite `(digest, threshold, sign, dtype, algo_version, shape)` | Unverified in this review | No direct code evidence available. |
| G-4.5 `hint_style` absent from `ImageFont.truetype()` usage | Unverified in this review | No direct code evidence available. |
| G-4.6 `Image.resize()` absent from `glyph.py` | Unverified in this review | No direct code evidence available. |
| G-4.7 Runtime FreeType version check uses `PIL.features.version("freetype2")` | Partially evidenced, not fully cleared | Your summary says the version assertion lives in [`__init__.py`](/var/www/wordcloud-app-v2/server/aerocloud-engine/packages/engine/src/aerocloud/geometry/__init__.py), but I could not inspect whether it uses the correct Pillow API. |
| G-4.8 Golden corpus `.npy` fixtures committed and CI-verified | Partially evidenced, not fully cleared | Your summary states golden corpus support shipped and fixtures exist, but the FreeType pin mismatch means cross-env CI reproducibility is not yet trustworthy. |
| G-5.9 Per-word adaptive POI origin, not one global origin | Likely fixed, but unverified from code | Your summary says [`placement.py`](/var/www/wordcloud-app-v2/server/aerocloud-engine/packages/engine/src/aerocloud/geometry/placement.py) implements a per-word adaptive POI spiral. |
| G-5.10 `MAX_STEP=16` | Unverified in this review | No direct code evidence available. |
| G-5.11 Integer offset generation with lexicographic tiebreak, not FP-defined order | Not cleared on facts provided | The prompt describes `archimedean_offsets()` as using `math.floor(r * math.sin(theta) + 0.5)`, which still leaves visit order sensitive to FP/libc behavior unless a later canonical integer ordering step exists. |
| G-5.12 Per-seed budget 500, not per-word `max_iterations=2000` | Unverified in this review | No direct code evidence available. |
| G-5.13 `PlacementFailedError` only for contract violations | Unverified in this review | No direct code evidence available. |
| G-5.14 Structured `DropReason` enum with 4 values | Unverified in this review | No direct code evidence available. |

## 2. Deviation 1 Verdict

**Verdict: BLOCKED**

Rationale: the documented Phase 4 validation target is `place_words 100 words @ 1024² < 5.0 s`. Actual measured mean is `24.85 s`, and the stated root cause is a deterministic algorithmic cost in the core search loop, not an outlier host artifact. Raising CI to `60 s` only prevents regressions from getting worse; it does not satisfy the phase exit criterion. Documenting this as a v1 known limit would be reasonable only if the phase had no hard performance acceptance gate. Here it does.

The research note matters: `RESEARCH.md §12 R-6` predicted this exact failure mode. That makes this an accepted design debt that has now materialized, not a surprise. Phase exit should require one of:
- an algorithmic mitigation that materially reduces the per-word POI recomputation cost, or
- a formally revised acceptance criterion approved before close, with the old `<5 s` target explicitly retired.

Without that, this phase is exiting against its own contract.

## 3. Deviation 2 Verdict

**Verdict: APPROVED-WITH-FIXES**

Rationale: the current `AEROCLOUD_SKIP_FREETYPE_CHECK=1` bypass is not a sound steady-state exit condition, because ADR, runtime, and golden fixtures disagree:
- ADR-0006 says FreeType `2.13.2`
- server/fixture reality is `2.14.3`
- tests are being made to pass by bypass rather than by alignment

That is a reproducibility problem, but it is fixable without redesign. Before phase close, the project should pick one truth and align all three:
1. update ADR-0006 to `2.14.3` and make CI/test images use it, then keep the corpus generated there, or
2. restore CI/runtime to `2.13.2` and regenerate fixtures there.

Deferring this to Phase 12 would leave Phase 4’s golden corpus claim unstable. So the deviation is not acceptable as-is; it is acceptable only with the pin/fixture/CI alignment completed now.

## 4. Adversarial Findings

**Critical**
- **Performance acceptance miss is phase-blocking.** The current implementation misses the explicit `<5.0 s` gate by about 5x on the stated VPS, and the cause is in the algorithmic hot path rather than incidental environment variance.

**Major**
- **FreeType reproducibility contract is broken until ADR/runtime/fixtures match.** The env-var bypass is a temporary escape hatch, not a valid exit state for a golden-corpus-based geometry phase.
- **Potential re-open of G-5.11 determinism if spiral visit order is still FP/libc-derived.** If `archimedean_offsets()` truly depends on `sin/cos` rounding and does not canonicalize with a lexicographic integer ordering step afterward, then cross-libc placement order can diverge near half-integer rounding boundaries. `EPS_BAND=0.5` in origin selection does not solve that; it affects origin candidacy, not spiral visit order.
- **Prior G-3/G-4/G-5 fixes are not independently proven in this review.** Because I could not inspect the source in-session, the earlier blockers cannot be affirmatively closed here. For a final phase exit review, “not disproven” is not enough.

**Minor**
- **`int64` AABB casts are not a blocker.** For a `4096x4096` canvas, coordinates and box-edge arithmetic are nowhere near `int32` overflow. Casting to `int64` is harmless defensive normalization; it does not hide a realistic overflow bug at these scales.
- **Debug dump likely contains user text content.** If `placement.json` serializes the full placement result, placed/dropped word text is likely present. That is a privacy/observability concern for dev dumps. Whether raw mask bytes leak depends on whether the result model embeds request fields; I could not confirm that from code here.
- **Contract validation around zero/negative AABB dimensions needs explicit confirmation.** Zero or negative `aabb_h/aabb_w` should be rejected as contract violations before search, and oversize words should deterministically hit `TOO_LARGE_FOR_MASK`. I could not verify those guards from source.

VERDICT: BLOCKED
tokens used
14,471
Phase 4 is not ready for exit. On the facts provided, the declared `place_words` acceptance target is missed by 5x on the stated production-class VPS, and the miss is caused by the exact algorithmic hotspot already predicted in research rather than by incidental noise. Separately, the FreeType/runtime/fixture contract is internally inconsistent and needs alignment before this phase can be called reproducible. I also cannot independently re-verify the earlier G-3/G-4/G-5 fixes from source in this session because file inspection was blocked by the sandbox, so those items remain unproven here rather than cleared.

## 1. G-3/G-4/G-5 Re-Verification

| Finding | Status | Evidence |
|---|---|---|
| G-3.1 SDF cache is bytes-bounded via `getsizeof=lambda arr: arr.nbytes` | Unverified in this review | Source inspection was not possible in this session, so I could not confirm the actual cache constructor or eviction accounting. |
| G-3.2 Hash function is `blake3` rather than `xxhash64` | Unverified in this review | No direct code evidence available. |
| G-3.3 Cache value dtype is `float32` rather than `int16` | Unverified in this review | No direct code evidence available. |
| G-3.4 Cache key is 6-part composite `(digest, threshold, sign, dtype, algo_version, shape)` | Unverified in this review | No direct code evidence available. |
| G-4.5 `hint_style` absent from `ImageFont.truetype()` usage | Unverified in this review | No direct code evidence available. |
| G-4.6 `Image.resize()` absent from `glyph.py` | Unverified in this review | No direct code evidence available. |
| G-4.7 Runtime FreeType version check uses `PIL.features.version("freetype2")` | Partially evidenced, not fully cleared | Your summary says the version assertion lives in [`__init__.py`](/var/www/wordcloud-app-v2/server/aerocloud-engine/packages/engine/src/aerocloud/geometry/__init__.py), but I could not inspect whether it uses the correct Pillow API. |
| G-4.8 Golden corpus `.npy` fixtures committed and CI-verified | Partially evidenced, not fully cleared | Your summary states golden corpus support shipped and fixtures exist, but the FreeType pin mismatch means cross-env CI reproducibility is not yet trustworthy. |
| G-5.9 Per-word adaptive POI origin, not one global origin | Likely fixed, but unverified from code | Your summary says [`placement.py`](/var/www/wordcloud-app-v2/server/aerocloud-engine/packages/engine/src/aerocloud/geometry/placement.py) implements a per-word adaptive POI spiral. |
| G-5.10 `MAX_STEP=16` | Unverified in this review | No direct code evidence available. |
| G-5.11 Integer offset generation with lexicographic tiebreak, not FP-defined order | Not cleared on facts provided | The prompt describes `archimedean_offsets()` as using `math.floor(r * math.sin(theta) + 0.5)`, which still leaves visit order sensitive to FP/libc behavior unless a later canonical integer ordering step exists. |
| G-5.12 Per-seed budget 500, not per-word `max_iterations=2000` | Unverified in this review | No direct code evidence available. |
| G-5.13 `PlacementFailedError` only for contract violations | Unverified in this review | No direct code evidence available. |
| G-5.14 Structured `DropReason` enum with 4 values | Unverified in this review | No direct code evidence available. |

## 2. Deviation 1 Verdict

**Verdict: BLOCKED**

Rationale: the documented Phase 4 validation target is `place_words 100 words @ 1024² < 5.0 s`. Actual measured mean is `24.85 s`, and the stated root cause is a deterministic algorithmic cost in the core search loop, not an outlier host artifact. Raising CI to `60 s` only prevents regressions from getting worse; it does not satisfy the phase exit criterion. Documenting this as a v1 known limit would be reasonable only if the phase had no hard performance acceptance gate. Here it does.

The research note matters: `RESEARCH.md §12 R-6` predicted this exact failure mode. That makes this an accepted design debt that has now materialized, not a surprise. Phase exit should require one of:
- an algorithmic mitigation that materially reduces the per-word POI recomputation cost, or
- a formally revised acceptance criterion approved before close, with the old `<5 s` target explicitly retired.

Without that, this phase is exiting against its own contract.

## 3. Deviation 2 Verdict

**Verdict: APPROVED-WITH-FIXES**

Rationale: the current `AEROCLOUD_SKIP_FREETYPE_CHECK=1` bypass is not a sound steady-state exit condition, because ADR, runtime, and golden fixtures disagree:
- ADR-0006 says FreeType `2.13.2`
- server/fixture reality is `2.14.3`
- tests are being made to pass by bypass rather than by alignment

That is a reproducibility problem, but it is fixable without redesign. Before phase close, the project should pick one truth and align all three:
1. update ADR-0006 to `2.14.3` and make CI/test images use it, then keep the corpus generated there, or
2. restore CI/runtime to `2.13.2` and regenerate fixtures there.

Deferring this to Phase 12 would leave Phase 4’s golden corpus claim unstable. So the deviation is not acceptable as-is; it is acceptable only with the pin/fixture/CI alignment completed now.

## 4. Adversarial Findings

**Critical**
- **Performance acceptance miss is phase-blocking.** The current implementation misses the explicit `<5.0 s` gate by about 5x on the stated VPS, and the cause is in the algorithmic hot path rather than incidental environment variance.

**Major**
- **FreeType reproducibility contract is broken until ADR/runtime/fixtures match.** The env-var bypass is a temporary escape hatch, not a valid exit state for a golden-corpus-based geometry phase.
- **Potential re-open of G-5.11 determinism if spiral visit order is still FP/libc-derived.** If `archimedean_offsets()` truly depends on `sin/cos` rounding and does not canonicalize with a lexicographic integer ordering step afterward, then cross-libc placement order can diverge near half-integer rounding boundaries. `EPS_BAND=0.5` in origin selection does not solve that; it affects origin candidacy, not spiral visit order.
- **Prior G-3/G-4/G-5 fixes are not independently proven in this review.** Because I could not inspect the source in-session, the earlier blockers cannot be affirmatively closed here. For a final phase exit review, “not disproven” is not enough.

**Minor**
- **`int64` AABB casts are not a blocker.** For a `4096x4096` canvas, coordinates and box-edge arithmetic are nowhere near `int32` overflow. Casting to `int64` is harmless defensive normalization; it does not hide a realistic overflow bug at these scales.
- **Debug dump likely contains user text content.** If `placement.json` serializes the full placement result, placed/dropped word text is likely present. That is a privacy/observability concern for dev dumps. Whether raw mask bytes leak depends on whether the result model embeds request fields; I could not confirm that from code here.
- **Contract validation around zero/negative AABB dimensions needs explicit confirmation.** Zero or negative `aabb_h/aabb_w` should be rejected as contract violations before search, and oversize words should deterministically hit `TOO_LARGE_FOR_MASK`. I could not verify those guards from source.

VERDICT: BLOCKED
