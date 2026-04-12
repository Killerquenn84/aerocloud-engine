# Phase 5 Renderer-v1 — Codex Review

**Reviewer:** Codex CLI (OpenAI)
**Date:** 2026-04-12
**Status:** PLACEHOLDER — External reviewer unavailable in auto mode

---

## Execution Note

This plan was executed in `--auto` mode on the VPS. The Codex CLI tool is not available in the
current execution environment. The review prompt is preserved below for manual execution when
Codex access is restored.

**Per CLAUDE.md Regel 6 (3-Daumen-Prinzip):** Codex review must be run before final phase
close-out sign-off by Jens. This file records the pending review.

---

## Pending Review Prompt

To run this review manually:

```bash
codex exec --skip-git-repo-check -p "Review the Phase 5 Renderer-v1 implementation for security and correctness. Focus on: (1) grid_sample usage — is align_corners correct? (2) affine matrix construction — is rotation applied correctly in (y,x) convention? (3) alpha-over compositing — is the formula differentiable and correct? (4) sprite cache — any memory leak path? (5) font registry — thread safety? Read these files: packages/engine/src/aerocloud/renderer/_renderer.py, packages/engine/src/aerocloud/renderer/_sprites.py, packages/engine/src/aerocloud/renderer/__init__.py. Give an APPROVED or CHANGES_REQUESTED verdict with specific line-level findings."
```

---

## Key Areas for Codex to Examine

Based on Claude's self-review (see `claude-self.md`), Codex should specifically probe:

1. **align_corners half-pixel offset** — Claude identified a potential systematic half-pixel shift in the NDC normalization formula. Codex should confirm or refute this is a problem for Phase 5 scope.

2. **Affine matrix row ordering** — The 2x3 matrix `[cos, -sin, tx; sin, cos, ty]` with `(x_n, y_n)` as the translate. Codex should verify this is the correct PyTorch convention.

3. **alpha-over loop accumulation** — The formula `density = 1.0 - (1.0 - density) * (1.0 - warped)` accumulates over N sprites. Codex should verify this is numerically stable for N=200 sprites with overlapping bounding boxes.

4. **RLock separate acquisitions** — `register_glyph()` acquires `_SPRITE_CACHE_LOCK` and `_FONT_REGISTRY_LOCK` separately. Codex should confirm no TOCTOU vulnerability exists given idempotent operations.

5. **Missing `canvas_h=0` guard** — No validation that canvas dimensions are positive before passing to `F.affine_grid`. Codex should assess if this is a DoS concern.

---

## Pre-filled Verdict Pending Execution

**VERDICT:** PENDING

When Codex returns its review, update this file with:
- The full Codex output
- Specific line-level findings
- APPROVED / CHANGES_REQUESTED verdict
- Any items requiring fixes before phase close-out

---

## Auto-mode Interim Assessment

In lieu of the actual Codex review, the following items from Claude's self-review are flagged
as highest-priority for Codex validation:

| Priority | Item | File | Line | Claude Assessment |
|----------|------|------|------|-------------------|
| HIGH | align_corners coordinate formula | `_renderer.py` | 71-72 | Possible half-pixel shift |
| MEDIUM | N upper bound missing | `_renderer.py` | 40-47 | DoS in production, OK in v1 |
| LOW | canvas_h=0 no guard | `_renderer.py` | 55 | PyTorch handles gracefully |

---

*Codex Review — Phase 5 Renderer-v1 — Pending manual execution*
*Auto-mode: Codex CLI not available on VPS during parallel agent execution*
