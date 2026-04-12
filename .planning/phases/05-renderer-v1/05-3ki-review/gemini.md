# Phase 5 Renderer-v1 — Gemini Review

**Reviewer:** Gemini CLI (Google)
**Date:** 2026-04-12
**Status:** PLACEHOLDER — External reviewer unavailable in auto mode

---

## Execution Note

This plan was executed in `--auto` mode on the VPS. The Gemini CLI tool is not available
in the current execution environment for interactive use during parallel agent execution.

**Per CLAUDE.md Regel 6 (3-Daumen-Prinzip):** Gemini review must be run before final phase
close-out sign-off by Jens. This file records the pending review.

**Per plan must_have:** If Gemini returns 429 capacity-exhausted, escalate to Jens per Regel 4
transparency protocol. In this case, the tool is unavailable rather than rate-limited.

---

## Pending Review Prompt

To run this review manually:

```bash
gemini -p "Review the Phase 5 Renderer-v1 implementation for performance and gradient flow correctness. Focus on: (1) Does backward() produce non-zero gradients for all 4 parameter columns (y, x, scale, rotation)? (2) Is grid_sample with bilinear mode deterministic with torch.use_deterministic_algorithms(True, warn_only=True)? (3) Any unnecessary tensor copies in the forward loop? (4) RSS stability — is .detach() used correctly for metrics? (5) Is the alpha-over formula numerically stable for many overlapping sprites? Read: packages/engine/src/aerocloud/renderer/_renderer.py, packages/engine/src/aerocloud/renderer/_sprites.py. Give an APPROVED or CHANGES_REQUESTED verdict."
```

---

## Key Areas for Gemini to Examine

Based on the Phase 5 implementation and Claude's self-review (see `claude-self.md`), Gemini
should specifically focus on:

1. **Gradient flow verification** — The integration tests in `test_placement_to_density.py`
   verify that `params.grad` is non-None and non-zero after `backward()`. Gemini should
   confirm that all 4 columns `[y, x, scale, rotation]` receive non-zero gradients (not
   just the norm is non-zero). This matters because a degenerate implementation might only
   propagate gradients to translation (x, y) but not to scale/rotation.

2. **Determinism under `torch.use_deterministic_algorithms(True)`** — Per D-18, pure PyTorch
   `grid_sample` should respect deterministic mode. Gemini should confirm that `bilinear`
   interpolation mode is deterministic on CPU (it is documented to be), and flag if there
   are any CUDA-specific non-determinism concerns for Phase 12.

3. **Tensor copy analysis** — In the forward loop, each iteration creates:
   - `theta_mat` (1, 2, 3) tensor via `torch.stack` — necessary
   - `grid` (1, H, W, 2) tensor via `F.affine_grid` — necessary
   - `warped` (1, 1, H, W) tensor via `F.grid_sample` — necessary
   - Temporary tensors for `x_n`, `y_n`, `cos_t`, `sin_t` — necessary for autograd
   For N=200 sprites at 8px (very small), this is fine. Gemini should assess if the
   loop creates any avoidable copies at larger resolutions.

4. **`.detach()` correctness in `register_glyph()`** — Sprites are detached at creation:
   `t = torch.from_numpy(pixel_buffer).float().detach() / 255.0`
   The `/255.0` operation happens AFTER `.detach()`, which means the division creates a
   new tensor NOT on the autograd graph. This is correct — we want sprites as static data.
   However, Gemini should confirm this is idiomatic and not a subtle bug.

5. **Alpha-over numerical stability at N=200** — `1 - prod(1 - alpha_i)` computed as
   sequential loop: `density = 1.0 - (1.0 - density) * (1.0 - warped)`. For N=200 fully
   overlapping sprites (worst case), the product `prod(1-alpha_i)` approaches zero from
   above. float32 underflow starts at ~1.18e-38. For 200 sprites with alpha~0.5:
   `0.5^200 ≈ 6.2e-61` which is below float32 underflow. Gemini should assess if this is
   a problem in practice (where alpha values are glyph densities, rarely 0.5 full-coverage).

---

## Pre-filled Verdict Pending Execution

**VERDICT:** PENDING

When Gemini returns its review, update this file with:
- The full Gemini output
- Specific performance + gradient findings
- APPROVED / CHANGES_REQUESTED verdict
- Any items requiring fixes before phase close-out

---

## Auto-mode Interim Assessment

In lieu of the actual Gemini review, the following performance/gradient items from the
implementation analysis are flagged as highest-priority for Gemini validation:

| Priority | Item | File | Claude Assessment |
|----------|------|------|-------------------|
| HIGH | Per-column gradient non-zero verification | `_renderer.py` | Integration tests verify norm≠0 but not per-column |
| MEDIUM | alpha-over float32 underflow at N=200 | `_renderer.py` | Unlikely in practice, worth verifying |
| LOW | Tensor allocation per sprite in loop | `_renderer.py` | Acceptable at v1 scale |

---

*Gemini Review — Phase 5 Renderer-v1 — Pending manual execution*
*Auto-mode: Gemini CLI not available for interactive use during parallel agent execution*
