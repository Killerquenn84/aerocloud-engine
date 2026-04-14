# Phase 6 Inner Loop-v1: Claude Self-Review

> **Anti-Sycophancy Protocol Applied** (CLAUDE.md Regel 7)
> "Das sieht gut aus" VERBOTEN ohne Begruendung.
> Aktiv nach Schwachstellen gesucht. Einigung nur nach Gegenfall-Check.

**Reviewer:** Claude Code (Sonnet 4.6)
**Date:** 2026-04-14
**Scope:** packages/engine/src/aerocloud/optimizer/ + packages/engine/tests/optimizer/
**Files reviewed:**
- `optimizer/loss.py` (230 lines)
- `optimizer/convergence.py` (41 lines)
- `optimizer/inner_loop.py` (249 lines)
- `optimizer/__init__.py` (31 lines)
- `models/optimizer.py` (101 lines)
- All 11 test files (unit/integration/property/determinism/memory)

---

## Security Checks (S-1..S-8)

### S-1: Injection
**Verdict: PASS**

No SQL, shell command, or eval usage anywhere in the optimizer module. All inputs are `torch.Tensor`, `np.ndarray`, or Pydantic models. The renderer is an internal object — no external input reaches it. No serialization of user data.

**Anti-sycophancy check:** Could `params` from external source reach optimizer? Not in current codebase — `InnerLoop` is called from tests only in v1. Phase 12 production wiring is explicitly deferred. No injection surface today.

### S-2: XSS
**Verdict: N/A**

No HTML generation, no web output, no Jinja templates. Optimizer module is pure compute. No XSS surface.

### S-3: CSRF
**Verdict: N/A**

No HTTP endpoints in this module. No state-modifying operations that could be cross-site triggered. Deferred to Phase 12 (Celery/Fastify wrapper).

### S-4: Authentication / Authorization
**Verdict: N/A (Phase 12)**

Optimizer has no auth layer — correctly deferred. The Celery task wrapper in Phase 12 will need to validate shop ownership before dispatching. This is a **known gap**, correctly documented in CONTEXT.md deferred section.

**Finding (informational, not blocking):** When Phase 12 wires this via Celery, the optimizer receives `renderer.params` without any validation that the params correspond to the authenticated shop's data. Phase 12 must ensure the trust chain from Shopify session → PlacementResult → InnerLoop constructor.

### S-5: Secrets
**Verdict: PASS**

No API keys, tokens, or credentials in the optimizer code. No `os.environ` reads. No file I/O. No `.env` usage. The `structlog` logger only emits structured metrics (stage index, resolution, epoch count, loss value) — no sensitive data logged.

**Anti-sycophancy check:** Does `final_loss` in the structlog output leak anything? No — it is a scalar float representing convergence quality, not user content.

### S-6: SSRF
**Verdict: N/A**

No HTTP client usage, no URL construction, no network access in the optimizer module.

### S-7: Path Traversal
**Verdict: N/A**

No file reading or writing in the optimizer module. The only I/O is `structlog` output (goes to stdout by default). No user-controlled paths.

### S-8: DoS
**Verdict: PARTIAL PASS — 1 Finding**

**Finding S-8-01: No upper bound guard on `N` (number of sprites)**

`compute_additive_density` iterates over `renderer._sprites` with `O(N)` passes. Each pass materializes a `(1, 1, canvas_h, canvas_w)` grid + warped sprite. For N=10,000 words at 1024x1024 resolution, this would OOM.

**However:** This is the same finding as `D-DEFER-01` from Phase 5 review (deferred to Phase 12). The `N` upper bound is enforced at the NLP layer (Phase 3 `max_words=200`). Today, N <= 200 is guaranteed by the calling convention.

**Risk level:** LOW in v1 (caller enforces N <= 200). MEDIUM in Phase 12 (production must re-enforce the limit at the Celery task boundary).

**Verdict: ACCEPTABLE for v1 — document as Phase 12 requirement.**

**Finding S-8-02: `max_epochs` has no upper cap**

`InnerLoopConfig(max_epochs=...)` accepts any int >= 1. A misconfigured max_epochs=1,000,000 with 4 stages would run 4M forward passes. No timeout guard.

**Risk:** In Phase 12, if InnerLoop config comes from user-supplied JSON, this could be a DoS vector.

**Verdict: ACCEPTABLE for v1 — Phase 12 must add `le=1000` constraint on max_epochs in the production config layer.**

---

## Stability Checks (L-1..L-8)

### L-1: Error Handling
**Verdict: PARTIAL PASS — 1 Finding**

`compute_additive_density` in `loss.py` accesses `renderer._sprites`, `renderer.params`, `renderer._device`. If `_sprites` is an empty list, the function returns a zero tensor (the `for i, sprite in enumerate(renderer._sprites)` loop never executes). That is **correct behavior** — no error needed.

**Finding L-1-01: No guard on `len(renderer._sprites) == 0` in `InnerLoop.optimize()`**

If someone calls `InnerLoop` with a renderer that has no sprites, `density = renderer.forward(stage_h, stage_w)` will return a zero tensor (correct), `compute_additive_density` returns zeros (correct), `l_wmse` and `l_overlap` will be finite (correct), but `l_fidelity = compute_l_fidelity(self._ref_weights, renderer.params)` will be called with `renderer.params` of shape `(0, 4)` — and `params[:, 2]` would be shape `(0,)`. `F.cosine_similarity` on two `(1, 0)` tensors produces NaN (cosine of zero vectors).

**Test coverage:** `test_l_fidelity_in_range` uses `n = st.integers(min_value=1, max_value=20)` — minimum n=1. The N=0 edge case is untested.

**Risk:** LOW — NLP pipeline always produces N >= 1. But a constructor-level guard `if renderer.params.shape[0] == 0: raise ValueError(...)` would be cleaner.

**Verdict: ACCEPTABLE for v1, but recommend adding an explicit guard.**

**Finding L-1-02: `sdf` shape handling in `__init__`**

The `elif sdf_tensor.ndim == 3: sdf_tensor = sdf_tensor.unsqueeze(0)` path assumes the 3D tensor is `(C, H, W)` — e.g., `(1, H, W)`. If the user passes a `(H, W, C)` tensor (PyTorch channel-last), the shape would be wrong. No validation.

**Risk:** LOW — tests use `(1, 1, H, W)` or `(H, W)` numpy arrays consistently. No channel-last tensors in practice.

**Verdict: Document expected shape in docstring (already partially done). Low risk.**

### L-2: Resource Leaks
**Verdict: PASS**

Memory hygiene verified by tests:
- `test_rss_stable_over_100_optimize_steps`: RSS delta < 50 MiB over 100 calls.
- `test_no_tensor_accumulation`: tensor count stable over 50 calls (tolerance 10).
- `test_detach_item_in_loss_history`: all entries are Python float, not tensor.

Key points confirmed in code:
- `optimizer.zero_grad(set_to_none=True)` per epoch (avoids zero-tensor accumulation, D-18)
- `loss_val = l_total.detach().item()` — breaks graph before appending (D-16)
- `torch.cuda.empty_cache()` after each stage transition (D-17)
- `params_initial = renderer.params.detach().clone()` — detached snapshot, no grad accumulation

**Anti-sycophancy check:** Does `params_initial` retain the graph? No — `.detach()` is explicit. Confirmed by `test_detach_item_in_loss_history`.

### L-3: Race Conditions
**Verdict: PASS (Single-threaded design)**

`InnerLoop` is not thread-safe by design (correct for v1). The optimizer operates on a single `DifferentiableRenderer` instance. The renderer's `params` is an `nn.Parameter` mutated in-place by `optimizer.step()`. Concurrent calls on the same InnerLoop instance would be racy, but this is not a supported usage.

**Anti-sycophancy check:** Does `compute_additive_density` create any race? No — it reads `renderer._sprites` (immutable after construction) and `renderer.params` (but only reads, doesn't write). The write happens in `optimizer.step()` which is sequential.

**Phase 12 note:** The Celery worker must not share InnerLoop instances across tasks (obvious, but worth documenting).

### L-4: Timeouts
**Verdict: PASS (Bounded by config)**

`max_epochs` provides an upper bound per stage. With default `max_epochs=100` and 4 stages, wall clock is bounded. Convergence detection (`check_convergence`) provides early termination.

**Finding L-4-01:** No absolute wall-clock timeout on the full optimization. A pathological case (e.g., loss oscillating but never converging) could run all 4 * 100 = 400 epochs. At ~1s/epoch on CPU at 128px, this is ~400s — over the 30s Celery task default.

**Risk:** LOW for v1 (8/32/128px stages are fast on CPU). MEDIUM for Phase 12 (512px target stage on CPU could be slow).

**Verdict: Phase 12 must add wall-clock timeout to InnerLoop.optimize().**

### L-5: Memory
**Verdict: PASS**

See L-2. Memory tests explicitly cover the ROADMAP success criterion 4 (RSS < 50 MiB over 100 calls).

**One nuance:** The `_sdf_full` tensor is stored on `renderer._device`. If target resolution is 4096x4096, this is 4096*4096*4 bytes = 64 MiB per InnerLoop instance. The memory test uses 8px SDF. In production, the memory budget for large SDFs should be explicitly documented.

### L-6: Retry Logic
**Verdict: N/A**

Optimizer has no external calls that need retry. Convergence detection handles plateau avoidance. No network I/O.

### L-7: Graceful Degradation
**Verdict: PASS**

`_build_stage_schedule` correctly handles `target <= base_resolutions[0]` — returns `[target]` (single stage). This is tested in `test_stage_schedule_filters_large_resolutions`.

`check_convergence` returns `False` (safe default) for empty/short histories — never raises.

`_downsample_sdf` returns input unchanged if already matching — no-op for same-size SDF.

### L-8: Logging
**Verdict: PASS**

`structlog.get_logger(__name__)` used in `inner_loop.py`. Logs per-stage metrics: `stage`, `resolution`, `epochs`, `converged`, `final_loss`. This provides observability for Phase 12 monitoring.

**Anti-sycophancy check:** Are there missing log points? 
- No per-epoch logging (intentional — would be too noisy for 100 epochs/stage)
- No log on `InnerLoop.__init__` (minor gap — would help debug misconfiguration)
- No log when stage schedule is empty (edge case)

**Finding L-8-01:** Initialization not logged. If Phase 12 misconfigures `stage_resolutions`, there's no startup log to diagnose.

**Risk:** LOW. Not a correctness issue, just observability gap.

---

## Architecture Checks (A-1..A-5)

### A-1: Single Responsibility Principle (SRP)
**Verdict: PASS**

Each file has clear responsibility:
- `loss.py`: 5 pure functions for loss computation + 1 helper for additive compositing
- `convergence.py`: 1 function for plateau detection
- `inner_loop.py`: 1 class orchestrating the optimization loop
- `models/optimizer.py`: 3 Pydantic data models
- `__init__.py`: public API re-export

No file does too much. The additive density helper is in `loss.py` (correct — it serves L_overlap). Could argue it belongs in a separate `helpers.py`, but the current colocation is fine.

### A-2: DRY (Don't Repeat Yourself)
**Verdict: PASS — with 1 Finding**

**Finding A-2-01: `compute_additive_density` replicates renderer logic (intentional duplication)**

The affine warp math in `compute_additive_density` (lines 193-226 of loss.py) is a near-copy of `DifferentiableRenderer.forward()`. This is **intentional** (D-03 specifies "replicate exactly") but represents architectural coupling risk.

**Why this is acceptable:** The renderer uses alpha-over compositing (caps at 1.0). We need additive compositing (allows > 1.0). A shared `_warp_sprite()` helper would break the separation between alpha-over and additive modes. The duplication is load-bearing.

**Risk:** If `DifferentiableRenderer.forward()` changes its warp math (e.g., different NDC convention), `compute_additive_density` must be updated in sync. There is no automated check for this.

**Recommendation:** Add a comment in `DifferentiableRenderer.forward()` pointing to `compute_additive_density` as a dependent mirror. Add a contract test that verifies both produce the same warped output for a single sprite (currently no such cross-check test exists).

### A-3: Coupling
**Verdict: PARTIAL PASS — 1 Finding**

**Finding A-3-01: `compute_additive_density` accesses renderer private attributes**

The function accesses `renderer._sprites`, `renderer.params`, `renderer._device` — all private (underscore-prefixed). This is documented in the docstring ("Accesses renderer private state:"), which is good transparency.

**Risk:** If the renderer's internal layout changes (e.g., renaming `_sprites` to `_sprite_list`), `compute_additive_density` breaks with an AttributeError at runtime, not a type error at import time.

**Mitigation present:** Phase 5 CONTEXT.md D-03 explicitly documents this as the intended access pattern. The renderer's public API does not expose individual sprite warping. This is a deliberate design tradeoff.

**What would be better:** A `renderer.warp_sprites_additive(h, w) -> Tensor` public method. But this would push SUM compositing logic into the renderer, mixing concerns.

**Verdict: ACCEPTABLE. Document in wiki as architectural constraint.**

**Finding A-3-02: Direct import of `DifferentiableRenderer` in `inner_loop.py`**

`inner_loop.py` has a direct (non-TYPE_CHECKING) import of `DifferentiableRenderer`. This means importing `aerocloud.optimizer.inner_loop` always triggers the full renderer import chain (Phase 5). This is correct and intentional — `InnerLoop.__init__` takes a real `DifferentiableRenderer` instance, so the runtime import is necessary.

Compare with `loss.py` which uses `TYPE_CHECKING` guard — because `compute_additive_density` only needs the type for annotation, not for runtime instantiation.

**Verdict: CORRECT as implemented.**

### A-4: API Contract
**Verdict: PASS**

`InnerLoop.optimize() -> OptimizationResult` is the sole public API. `OptimizationResult` is a frozen Pydantic model with all fields documented. `LossWeights` and `InnerLoopConfig` are fully typed with `ge=0.0` / `gt=0.0` constraints.

The `__init__.py` explicitly exports all public symbols in `__all__`. Phase 9 MAP-Elites can safely consume `InnerLoop` and `OptimizationResult` without depending on internal modules.

**Anti-sycophancy check:** Is there anything in `__init__.py` that shouldn't be public? `compute_additive_density` is exported — is this intentional? It's used in tests directly (property test `test_random_params_produce_finite_loss_through_renderer`). It may become Phase 9 utility for quality metrics. Acceptable to keep public.

### A-5: Backwards Compatibility
**Verdict: N/A (v1 — no prior API users)**

Phase 6 is the first implementation of the optimizer module. No backwards compatibility constraints exist yet. Phase 9 will be the first consumer of `optimize() -> OptimizationResult`. Any breaking changes before Phase 9 are free.

**Note:** Once Phase 9 is implemented, the `OptimizationResult` model (especially `stage_loss_histories: list[list[float]]` and `convergence_flags: list[bool]`) becomes a contract that cannot change without a migration.

---

## Blueprint Math Verification

### compute_additive_density — Exact Match Verification

The Blueprint (Teil V) specifies that L_overlap requires additive compositing. The implementation was verified against `DifferentiableRenderer.forward()`:

| Property | Renderer forward() | compute_additive_density |
|----------|--------------------|--------------------------|
| Rotation clamping | `torch.remainder(theta + pi, 2*pi) - pi` | Same (line 195) |
| Scale softplus | `F.softplus(s - 0.01) + 0.01` | Same (line 198) |
| NDC convention | `((2*x + 1) / W) - 1` | Same (lines 201-202) |
| affine_grid align_corners | `False` | Same (line 218) |
| grid_sample padding_mode | `zeros` | Same (line 222) |
| Compositing | `alpha_over` (alpha-over) | **SUM** (additive, intentional) |

**Verdict: Mathematical parity confirmed. Only compositing differs, as required.**

### LossWeights Defaults Verification

| Weight | Blueprint D-06 | Implementation |
|--------|---------------|----------------|
| alpha | 1.0 | 1.0 (line 29) |
| beta | 10.0 | 10.0 (line 32) |
| gamma | 0.1 | 0.1 (line 35) |
| lambda_ | 0.0 | 0.0 (line 38) |

**Verdict: All defaults match Blueprint D-06 exactly.**

### InnerLoop Stage Schedule — Edge Case Verification

`_build_stage_schedule([8, 32, 128], target=8)` → `[8]` (all base resolutions >= 8 filtered, only target appended)
`_build_stage_schedule([8, 32, 128], target=16)` → `[8, 16]` (32, 128 filtered)
`_build_stage_schedule([], target=any)` → `[any]` (single stage)

**Verdict: All edge cases handled correctly. Tested in integration tests.**

### Convergence Detection — Edge Cases

`check_convergence([], window=10)` → `False` (empty, correct)
`check_convergence([0.5]*9, window=10)` → `False` (< window, correct)
`check_convergence([0.5]*10, window=10)` → `True` (flat, correct)

**Verified against:** `max_val = max_val` in divisor: `scale = max(abs(max_val), 1e-8)` correctly handles the case where all values are 0.0 (scale = 1e-8, range_val = 0, ratio = 0 < epsilon → True). This is the right behavior for a perfectly optimized (zero-loss) plateau.

---

## Summary: Findings and Verdict

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| S-8-01 | LOW | No N upper bound in compute_additive_density | Phase 12 guard |
| S-8-02 | LOW | max_epochs has no upper cap in config | Phase 12 le= constraint |
| L-1-01 | LOW | N=0 edge case not guarded in InnerLoop | Recommend guard |
| L-1-02 | LOW | sdf shape validation incomplete | Document expected shapes |
| L-4-01 | LOW | No wall-clock timeout on optimize() | Phase 12 timeout |
| L-5-01 | INFO | Large SDF memory budget not documented | Document in wiki |
| L-8-01 | INFO | No initialization log | Nice to have |
| A-2-01 | LOW | compute_additive_density mirrors renderer warp | Intentional, document |
| A-3-01 | LOW | Accesses renderer private attributes | Intentional, documented |

**Overall Verdict: APPROVED for Phase 6 v1**

All findings are LOW severity or INFO. None block correctness, security, or basic operation in v1. Phase 12 must address S-8-01, S-8-02, and L-4-01 before production deployment.

**Anti-Sycophancy Self-Check:** "Stimme ich zu weil ich ueberzeugt bin — oder weil es einfacher ist?"

The implementation correctly follows the Blueprint math (verified above). The test pyramid is comprehensive (56 tests: unit/integration/property/determinism/memory). All ROADMAP success criteria are met (tests confirm it). The findings listed are genuine issues I actively searched for, not invented to look thorough. I approve because the evidence supports approval, not to be agreeable.

---

*Claude Self-Review | Phase 06-inner-loop-v1 | 2026-04-14*
