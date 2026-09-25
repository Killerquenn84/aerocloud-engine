Loaded cached credentials.
# AeroCloud Engine Performance & Determinism Audit (Phase 4 Geometry-v1)

This document presents the audit findings for the `packages/engine/src/aerocloud/geometry/` module, focusing on performance, determinism, and correctness against Phase 4 requirements.

### 1. Performance Analysis

The `O(W * P)` complexity, where `W` is the number of words and `P` is the number of canvas pixels, is the root cause of the performance deviation. The primary contributor is the per-word re-computation of `feasibility_field`, which executes two `O(P)` operations (`minimum_filter` and `binary_dilation`) for each word.

- **Incremental Updates:** An incremental update to `minimum_filter`'s output is non-trivial. The effect of placing a new word is non-local, making it difficult to patch the previous feasibility field cheaply.
- **Optimization Path Evaluation:**
    - **(a) Integral Occupancy Map:** This is a powerful technique for `O(1)` collision checks. However, the current bottleneck is the `minimum_filter` operation used for *finding* the best placement candidate, not the collision check in the spiral search. While valuable, this would not address the primary 24.85s cost.
    - **(b) Narrow-band Filter:** Restricting `minimum_filter` to a band around the global SDF maximum is a false optimization. The purpose of the filter is to discover the best region for a word of a specific size `(h, w)`, which may not be near the SDF's global maximum for a single pixel.
    - **(c) Caching:** Caching `feasibility_field` is not viable as it's a function of word dimensions `(h, w)`, which are unique for almost every word.
    - **(d) Coarse-to-Fine Search:** This is the most effective and theoretically sound optimization. By performing the expensive `minimum_filter` on a downsampled (e.g., 2x or 4x) SDF, a promising candidate region can be identified in a fraction of the time (`1/4` or `1/16` of the cost). A refined, full-resolution search can then be performed in a small neighborhood around the best coarse candidate. This directly attacks the `P` term in the complexity and is a standard approach for such problems.

**Conclusion:** The most effective single optimization is a **coarse-to-fine search strategy (d)**. It preserves the quality of the SDF-guided placement while drastically reducing the computational cost of the `minimum_filter` stage.

### 2. Determinism Analysis

The use of `math.floor(r * math.sin(theta) + 0.5)` for generating spiral offsets introduces a genuine, albeit low-probability, risk of cross-platform non-determinism.

- **Risk:** Different `libc` math library implementations (e.g., glibc, musl, Apple libm) can produce `sin`/`cos` results that differ by 1-2 ULPs (Units in the Last Place). When the input to `floor(x + 0.5)` is extremely close to a half-integer (e.g., `3.5`), these minute differences can alter the integer result, producing a different `(dy, dx)` offset.
- **Impact:** The `archimedean_offsets` function deduplicates offsets. If platforms produce different offsets, the search paths diverge. Even if they produce the same set of unique offsets but in a different order, the first valid placement found could differ, leading to a different final layout.
- **Mitigation:** For typical inputs, this risk is low. However, for a system requiring strict determinism, it cannot be ignored. A robust solution would involve using a cross-platform-consistent math library, a pre-computed lookup table for the spiral's `sin`/`cos` values, or a fixed-point arithmetic implementation. For v1, this can be accepted as a known, low-probability risk.

### 3. numpy dtype discipline findings

Minor, unnecessary type promotions from `float32` to `float64` (Python `float`) were found in hot paths.

1.  In `select_origin`, the comparison `candidates[:, 2] >= (max_val - 0.5)` promotes the `float32` array data to `float64` because `0.5` is a `float64` literal. This should be `np.float32(0.5)`.
2.  In `_spiral_search`, `sdf_at: float = float(sdf[oy, ox])` explicitly casts a `numpy.float32` to a `float` (float64). This is unnecessary as `numpy.float32` scalars can be used in comparisons directly.

While not the primary performance bottleneck, eliminating these promotions is good practice for memory and performance hygiene, especially in loops that run thousands of times per placement.

### 4. gc.collect() memory effectiveness assessment

The analysis provided is correct. The call to `gc.collect()` between the two `distance_transform_edt` calls is **ineffective** at releasing the memory used by `edt_in`.

- **Reason:** `edt_in` is a local variable whose reference count is still positive. The garbage collector only reclaims objects with zero references or those in unreachable reference cycles. Numpy arrays are typically not involved in cycles and are managed by reference counting.
- **Impact:** The peak memory usage during `compute_sdf` is indeed the sum of two `float64` EDT arrays and one `float32` SDF array. The `gc.collect()` call is misleading and provides a false sense of security. The correct way to free the memory, if absolutely necessary, would be to use `del edt_in` before the `gc.collect()` call.

### 5. Benchmark re-evaluation

Relying on faster CI hardware to meet the performance budget is not a sufficient or robust solution.

- **Analysis:** A 2-4x speedup on a GitHub Actions runner versus the shared VPS is a reasonable estimate. This would reduce the 24.85s time to between 6.2s and 12.4s. This is still over the 5.0s budget. Achieving the required 5x speedup from hardware alone is unlikely and not guaranteed.
- **Recommendation:** The performance issue is fundamentally algorithmic. It will not scale with more words or larger canvases. An algorithmic change, as recommended in the Performance Analysis, is **required** to meet the target budget reliably.

### 6. Deviation 1 Verdict: Performance

**VERDICT: BLOCKED**

**Rationale:** A 5x deviation from a key performance budget is too significant to approve. The root cause is an `O(W * P)` algorithm whose cost was correctly predicted by research (R-6) but proves unacceptable in practice. Relying on faster production hardware is a risky, non-scalable strategy. A clear, achievable algorithmic optimization path (coarse-to-fine search) exists and should be implemented to address the underlying complexity before this phase is exited.

### 7. Deviation 2 Verdict: FreeType Pin

**VERDICT: APPROVED-WITH-FIXES**

**Rationale:** Using an environment variable to bypass a check defined in an ADR is a development hack, not a release-worthy solution. It introduces process debt and invalidates the ADR. The correct action is not to block the release but to mandate the fix: the team must validate behavior with FreeType 2.14.3 and update ADR-0006 to reflect the new, verified version. This is a process and documentation fix.

### 8. Summary Table

| Finding | Severity | Recommendation |
| :--- | :--- | :--- |
| Performance target missed by 5x | **Critical** | **BLOCKED**. Implement a coarse-to-fine search algorithm before phase exit. |
| FreeType version bypass | **High** | **APPROVED-WITH-FIXES**. Remove bypass, test with 2.14.3, and update ADR-0006. |
| Ineffective `gc.collect()` call | **Medium** | Recommend removing the call and adding a code comment explaining the peak memory usage. |
| FP non-determinism risk | **Low** | Acknowledge as an accepted risk for v1. Consider a deterministic math solution for future versions. |
| Minor `float64` promotions in hot path | **Low** | Fix by using `np.float32` literals and avoiding explicit casts to `float` in loops. |

VERDICT: BLOCKED
