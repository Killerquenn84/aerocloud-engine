---
phase: 04-geometry-v1
plan: 07
plan_id: 04-07-3ki-review
type: execute
wave: 5
depends_on: [04-06-observability-gates]
autonomous: false
requirements: [GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07]
files_modified:
  - wiki/discussions/2026-04-10-phase-4-wave5-codereview.md
  - wiki/discussions/2026-04-10-phase-4-summary.md
  - .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md
  - .planning/phases/04-geometry-v1/04-3ki-review/codex.md
  - .planning/phases/04-geometry-v1/04-3ki-review/gemini.md
  - .planning/phases/04-geometry-v1/04-3ki-review/consensus.md

must_haves:
  truths:
    - "Claude Code self-review covers S-1..S-8 + L-1..L-8 + A-1..A-5 checklists (CLAUDE.md Regel 7)"
    - "Codex review executed via `codex exec --skip-git-repo-check` focused on security + correctness of hot loops"
    - "Gemini review executed via `gemini -p` focused on performance + determinism"
    - "All findings consolidated in consensus.md with explicit APPROVED / CHANGES_REQUESTED verdict per reviewer"
    - "Every CHANGES_REQUESTED item is either fixed in-place with a new commit OR documented as a deferred backlog item with Jens escalation"
    - "All 3 reviewers must have APPROVED status before phase exit"
    - "If Gemini returns 429 capacity-exhausted (observed in G-4), escalate to Jens per Regel 4 transparency protocol"
    - "wiki/discussions/2026-04-10-phase-4-wave5-codereview.md captures the full round-table transcript"
    - "wiki/discussions/2026-04-10-phase-4-summary.md is the phase close-out document"
  artifacts:
    - path: ".planning/phases/04-geometry-v1/04-3ki-review/claude-self.md"
      provides: "Claude self-review per Regel 7 checklists"
    - path: ".planning/phases/04-geometry-v1/04-3ki-review/codex.md"
      provides: "Codex adversarial review output"
    - path: ".planning/phases/04-geometry-v1/04-3ki-review/gemini.md"
      provides: "Gemini performance review output"
    - path: ".planning/phases/04-geometry-v1/04-3ki-review/consensus.md"
      provides: "3-thumb verdict + fix tracking"
    - path: "wiki/discussions/2026-04-10-phase-4-wave5-codereview.md"
      provides: "Wiki-visible code review transcript (Regel 11)"
    - path: "wiki/discussions/2026-04-10-phase-4-summary.md"
      provides: "Phase 4 close-out summary"
  key_links:
    - from: "wiki/discussions/2026-04-10-phase-4-wave5-codereview.md"
      to: ".planning/phases/04-geometry-v1/04-3ki-review/consensus.md"
      via: "round-table transcript"
      pattern: "consensus|APPROVED"
    - from: "wiki/log.md"
      to: "Phase 4 exit entry"
      via: "dated log"
      pattern: "Phase 4.*complete"
---

<objective>
Wave 5: Phase exit gate. Trigger a fresh 3-KI code review per CLAUDE.md
Regel 6 (3-Daumen-Prinzip). All 3 reviewers (Claude self, Codex, Gemini)
must return APPROVED before Phase 4 is closed. This wave is intentionally
NON-autonomous — it spawns external reviewers and requires Jens's final
sign-off after the round-table transcript lands in the wiki.

Purpose: Phase exit gate. Delivers the Regel 6 review artifact, the phase
close-out summary, and marks Phase 4 complete in ROADMAP.md + STATE.md.
</objective>

<execution_context>
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/workflows/execute-plan.md
@/var/www/wordcloud-app-v2/server/aerocloud-engine/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@packages/engine/src/aerocloud/CLAUDE.md
@.planning/phases/04-geometry-v1/04-CONTEXT.md
@.planning/phases/04-geometry-v1/04-RESEARCH.md
@.planning/phases/04-geometry-v1/04-VALIDATION.md
@.planning/phases/04-geometry-v1/04-01-SUMMARY.md
@.planning/phases/04-geometry-v1/04-02-SUMMARY.md
@.planning/phases/04-geometry-v1/04-03-SUMMARY.md
@.planning/phases/04-geometry-v1/04-04-SUMMARY.md
@.planning/phases/04-geometry-v1/04-05-SUMMARY.md
@.planning/phases/04-geometry-v1/04-06-SUMMARY.md
</context>

<tasks>

<task type="auto" id="04-07-T1">
  <name>Task 1: Claude Code self-review (Regel 7 full checklist)</name>
  <files>
    .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md
  </files>
  <read_first>
    - CLAUDE.md §7 Anti-Sycophancy + S/L/A checklists
    - All 6 wave SUMMARY files
    - packages/engine/src/aerocloud/geometry/*.py (9 files)
    - packages/engine/src/aerocloud/models/geometry.py
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/ (prior adversarial findings to re-verify were addressed)
  </read_first>
  <action>
Perform a thorough self-review per CLAUDE.md Regel 7. Walk the complete
checklist:

**Security (S-1..S-8):**
- S-1 Injection — any `eval`, `exec`, `subprocess`, dynamic imports in geometry?
- S-2 XSS — N/A (no HTML rendering)
- S-3 CSRF — N/A
- S-4 Auth — N/A
- S-5 Secrets — any hardcoded credentials or tokens?
- S-6 SSRF — N/A (no network calls)
- S-7 Path traversal — `debug/geometry/` write path, golden fixture load path
- S-8 DoS — placement budget, cache bytes budget, mask size guard

**Stability (L-1..L-8):**
- L-1 Error handling — every `try` catches the narrowest exception?
- L-2 Resource leaks — cache eviction works; no unbounded growth
- L-3 Race conditions — RLock on sdf_cache + glyph cache; compute_sdf outside lock
- L-4 Timeouts — per-word walltime 1.0 s; benchmark budget enforcement
- L-5 Memory — R-2 EDT spike mitigation via `gc.collect()` between EDT calls
- L-6 Retry logic — N/A (no network)
- L-7 Graceful degradation — blake3 → sha256 fallback; matplotlib → missing-marker fallback
- L-8 Logging — structlog wired; no `print()` in production code

**Architecture (A-1..A-5):**
- A-1 SRP — each module has one responsibility (mask, sdf, cache, collision, glyph, placement)
- A-2 DRY — any duplication between `_glyph_to_array` in glyph.py and the generator script?
- A-3 Coupling — placement.py imports sdf_cache, mask, collision, models — acceptable
- A-4 API contract — PlacementResult + DropReason stable for Phase 5 Renderer consumption
- A-5 Backwards compat — N/A (new package)

**Anti-sycophancy self-check (Regel 7):**
> "Stimme ich zu weil ich ueberzeugt bin — oder weil es einfacher ist?"
Actively look for weaknesses. For each CONTEXT decision, ask: does the code
actually implement it or merely look like it?

**Specific re-verification of prior Codex BLOCK findings:**
- G-3: cache maxsize is bytes-bounded 384 MiB (NOT entry-count 50)
- G-3: hash function is blake3 (NOT xxhash)
- G-3: cache value dtype is float32 (NOT int16)
- G-3: composite key has 6 components (NOT just raw bytes digest)
- G-4: `hint_style` absent from all source files
- G-4: `Image.resize` absent from glyph.py
- G-4: `PIL.features.version("freetype2")` used (NOT `freetype.__version__`)
- G-4: golden corpus committed and CI-verified
- G-5: per-word adaptive POI (NOT single global origin)
- G-5: MAX_STEP=16 (NOT 32 or 50)
- G-5: integer offset generation with lex tiebreak
- G-5: per-seed budget 500 (NOT per-word only)
- G-5: PlacementFailedError only on contract violations
- G-5: structured DropReason enum with 4 values

Write findings to `.planning/phases/04-geometry-v1/04-3ki-review/claude-self.md`
with explicit verdict: `APPROVED` or `CHANGES_REQUESTED: <list>`.
  </action>
  <verify>
    <automated>test -f .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md && grep -E "APPROVED|CHANGES_REQUESTED" .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md && grep -q "S-1" .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md && grep -q "L-3" .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md && grep -q "A-4" .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md</automated>
  </verify>
  <acceptance_criteria>
    - `claude-self.md` exists
    - All S-1..S-8, L-1..L-8, A-1..A-5 checkboxes addressed
    - All Codex G-3/G-4/G-5 prior BLOCK findings re-verified
    - Explicit APPROVED or CHANGES_REQUESTED verdict present
  </acceptance_criteria>
  <done>Claude self-review committed to review dir</done>
</task>

<task type="auto" id="04-07-T2">
  <name>Task 2: Codex adversarial review (security + correctness focus)</name>
  <files>
    .planning/phases/04-geometry-v1/04-3ki-review/codex.md
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g3.md (prior findings — reviewer should re-check)
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g4.md
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/codex-g5.md
  </read_first>
  <action>
Invoke Codex for a full-phase adversarial review using the documented CLI:

```bash
codex exec --skip-git-repo-check <<'EOF'
Review all code in packages/engine/src/aerocloud/geometry/ and
packages/engine/src/aerocloud/models/geometry.py against
.planning/phases/04-geometry-v1/04-CONTEXT.md (51 locked decisions) and
.planning/phases/04-geometry-v1/04-RESEARCH.md.

Focus areas:
1. Security (S-1..S-8 from CLAUDE.md Regel 7)
2. Correctness of the SDF sign convention (ADR-0004, D-09)
3. Correctness of the SDF cache composite key (D-20)
4. Correctness of the per-word adaptive POI + integer spiral (D-38..D-44)
5. Re-verify that your prior G-3/G-4/G-5 BLOCK findings in
   .planning/phases/04-geometry-v1/3ki-g3-g4-g5/ have been addressed in code.
6. RLock deadlock hunt: prove that compute_sdf is NEVER called inside the
   with _CACHE_LOCK block.
7. hint_style hallucination recheck: prove the string 'hint_style' is
   absent from the entire packages/engine/src/aerocloud/geometry/ tree.

Output a markdown report with sections Findings / Critical / Major / Minor /
APPROVED-or-CHANGES_REQUESTED verdict.
EOF
```

Pipe the output to `.planning/phases/04-geometry-v1/04-3ki-review/codex.md`.

If Codex finds critical issues, STOP this task and escalate to Jens via
Telegram. Do NOT auto-fix — Regel 6 requires a human-in-the-loop on
CHANGES_REQUESTED before proceeding.
  </action>
  <verify>
    <automated>test -f .planning/phases/04-geometry-v1/04-3ki-review/codex.md && test -s .planning/phases/04-geometry-v1/04-3ki-review/codex.md && grep -E "APPROVED|CHANGES_REQUESTED" .planning/phases/04-geometry-v1/04-3ki-review/codex.md</automated>
  </verify>
  <acceptance_criteria>
    - `codex.md` exists and is non-empty
    - Contains explicit APPROVED or CHANGES_REQUESTED verdict
    - Re-verifies prior G-3/G-4/G-5 BLOCK findings
    - If CHANGES_REQUESTED, a Telegram escalation message was sent to Jens
  </acceptance_criteria>
  <done>Codex verdict recorded</done>
</task>

<task type="auto" id="04-07-T3">
  <name>Task 3: Gemini performance + determinism review</name>
  <files>
    .planning/phases/04-geometry-v1/04-3ki-review/gemini.md
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g3.md
    - .planning/phases/04-geometry-v1/3ki-g3-g4-g5/gemini-g5.md
    - .planning/phases/04-geometry-v1/04-RESEARCH.md §Open Questions 5 (Gemini fallback policy)
  </read_first>
  <action>
Invoke Gemini with a performance + determinism-focused prompt:

```bash
gemini -p "Review packages/engine/src/aerocloud/geometry/ as a performance
and determinism auditor.

Context: .planning/phases/04-geometry-v1/04-CONTEXT.md (51 locked decisions),
.planning/phases/04-geometry-v1/04-RESEARCH.md §12 risks (R-2 memory, R-5
libc sin/cos drift, R-6 placement speed).

Focus:
1. Performance: are there any O(N*M) loops where O(N+M) is possible?
2. Determinism: identify any remaining FP operations that could differ
   across libc. The spiral uses floor(x + 0.5) collapse — is this sufficient
   for 2026 libm implementations?
3. numpy dtype discipline — any implicit float64 promotion in hot loops?
4. Memory: the two-EDT pattern in compute_sdf — does gc.collect() actually
   release the first EDT's float64 temporary before the second call?
5. Benchmark budget: given the 2048² < 1 s target, is the current
   scipy.ndimage.distance_transform_edt adequate or should we consider
   scipy.spatial.distance alternatives?

Output markdown with Findings / verdict APPROVED or CHANGES_REQUESTED."
```

Pipe output to `.planning/phases/04-geometry-v1/04-3ki-review/gemini.md`.

**Gemini fallback policy (RESEARCH Open Question 5):** If Gemini returns
429 capacity-exhausted (as observed during G-4 discovery), escalate to Jens
immediately via Telegram with the full transparency note:
"Gemini unavailable (429). Per CLAUDE.md Regel 4 transparency, I am reporting
this before proceeding. Options: (a) retry in 10 min, (b) accept Codex+Claude
as sufficient per Jens's discretion, (c) defer Wave 5 until Gemini quota
resets." Wait for Jens's decision before marking the task done.
  </action>
  <verify>
    <automated>test -f .planning/phases/04-geometry-v1/04-3ki-review/gemini.md && test -s .planning/phases/04-geometry-v1/04-3ki-review/gemini.md</automated>
  </verify>
  <acceptance_criteria>
    - `gemini.md` exists with either a real Gemini response OR a documented
      Jens-approved fallback note (capacity exhausted scenario)
    - If real response: explicit APPROVED or CHANGES_REQUESTED verdict
    - If fallback: Jens's decision quoted verbatim
  </acceptance_criteria>
  <done>Gemini verdict (or approved fallback) recorded</done>
</task>

<task type="checkpoint:human-verify" id="04-07-T4" gate="blocking">
  <name>Task 4: Consensus round-table + 3-thumb verdict</name>
  <action>Human sign-off checkpoint: verify all 3 reviewer verdicts are APPROVED, fix any CHANGES_REQUESTED items in new commits before proceeding, and ratify the consensus in consensus.md. See what-built and how-to-verify below.</action>
  <what-built>
3-KI code review artifacts: claude-self.md, codex.md, gemini.md in
`.planning/phases/04-geometry-v1/04-3ki-review/`. All three reviewers have
issued verdicts. This checkpoint is the human sign-off that the consensus
is valid and Phase 4 may close.
  </what-built>
  <how-to-verify>
1. Read `.planning/phases/04-geometry-v1/04-3ki-review/claude-self.md` — verdict?
2. Read `.planning/phases/04-geometry-v1/04-3ki-review/codex.md` — verdict?
3. Read `.planning/phases/04-geometry-v1/04-3ki-review/gemini.md` — verdict?
4. Confirm all 3 are APPROVED.
5. If any reviewer returned CHANGES_REQUESTED, verify the fixes were applied
   in new commits AND the reviewer was re-queried for a second-round verdict.
6. Author `consensus.md` summarizing the round-table: one row per reviewer
   with verdict + any open findings + "ratified" timestamp.
7. Run full test suite one last time:
   `cd packages/engine && uv run pytest tests/geometry tests/regression/test_glyph_golden.py -q`
8. Confirm all green.
9. Type "approved" in chat to proceed, or describe issues.
  </how-to-verify>
  <resume-signal>Type "approved" once all 3 reviewers APPROVED and full test suite is green, or describe blocking issues.</resume-signal>
</task>

<task type="auto" id="04-07-T5">
  <name>Task 5: Phase close-out — wiki discussions + log + index + ROADMAP + STATE</name>
  <files>
    wiki/discussions/2026-04-10-phase-4-wave5-codereview.md
    wiki/discussions/2026-04-10-phase-4-summary.md
    wiki/log.md
    wiki/index.md
    .planning/ROADMAP.md
    .planning/STATE.md
    .planning/phases/04-geometry-v1/04-3ki-review/consensus.md
  </files>
  <read_first>
    - .planning/phases/04-geometry-v1/04-3ki-review/claude-self.md
    - .planning/phases/04-geometry-v1/04-3ki-review/codex.md
    - .planning/phases/04-geometry-v1/04-3ki-review/gemini.md
    - .planning/ROADMAP.md (existing Phase 4 entry)
    - .planning/STATE.md (active phase / next action)
    - wiki/log.md (append; do not overwrite)
    - wiki/index.md (append; do not overwrite)
  </read_first>
  <action>
**Step 1 — Create `wiki/discussions/2026-04-10-phase-4-wave5-codereview.md`:**
Full transcript of the 3-KI round-table. Include each reviewer's verdict,
any CHANGES_REQUESTED items, how they were resolved, and the final
"ratified" timestamp. Reference `.planning/phases/04-geometry-v1/04-3ki-review/`
for the raw artifacts.

**Step 2 — Create `wiki/discussions/2026-04-10-phase-4-summary.md`:** Phase
close-out document covering:
- Goal achieved: PNG → signed float32 SDF → PlacementResult
- All 7 GEO-XX requirements satisfied
- Test count shipped (~50+ new tests)
- Files created (9 production + 12+ test files)
- 3-KI verdicts
- Known limitations carried into v2 (from any CHANGES_REQUESTED items not
  fully fixed but explicitly deferred with Jens's approval)
- Hand-off to Phase 5 Renderer-v1: stable interfaces (`PlacementResult`,
  `SDFHandle`, `GlyphBBox`, signed float32 SDF contract).

**Step 3 — Update `wiki/log.md`** with a dated entry:
```
## 2026-04-10 — Phase 4 Geometry-v1 COMPLETE
- 3-KI review: Claude APPROVED, Codex APPROVED, Gemini APPROVED
- GEO-01..07 requirements satisfied
- X new tests, all green (pytest + hypothesis)
- Phase exit gate cleared per ROADMAP.md
- Next phase: Phase 5 Renderer-v1
```

**Step 4 — Update `wiki/index.md`** to reference the two new discussion
files.

**Step 5 — Update `.planning/ROADMAP.md`** Phase 4 entry status from
`🟡 Context locked` to `✅ Complete` with commit hash placeholder.

**Step 6 — Update `.planning/STATE.md`**:
- `Active phase: Phase 5 — Renderer-v1 (awaiting /gsd-discuss-phase 5)`
- Add Phase 4 to the completed table with its summary line
- Next action: `/gsd-discuss-phase 5`

**Step 7 — Create `consensus.md` summary:** one-page ratification doc in
`.planning/phases/04-geometry-v1/04-3ki-review/consensus.md`.
  </action>
  <verify>
    <automated>test -f wiki/discussions/2026-04-10-phase-4-wave5-codereview.md && test -f wiki/discussions/2026-04-10-phase-4-summary.md && test -f .planning/phases/04-geometry-v1/04-3ki-review/consensus.md && grep -q "Phase 4.*COMPLETE\|Phase 4 Geometry-v1 COMPLETE" wiki/log.md && grep -qE "(Complete|✅)" .planning/ROADMAP.md && grep -q "Phase 5" .planning/STATE.md</automated>
  </verify>
  <acceptance_criteria>
    - Two wiki/discussions/ files exist with close-out content
    - consensus.md ratifies all three reviewer verdicts
    - wiki/log.md has Phase 4 COMPLETE entry
    - wiki/index.md references the new discussion pages
    - ROADMAP.md marks Phase 4 ✅ Complete
    - STATE.md points next action at Phase 5
  </acceptance_criteria>
  <done>Phase 4 closed, Phase 5 unblocked</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| External AI reviewers → review artifacts | Codex/Gemini output quoted verbatim |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-4-R1 | Repudiation | 3-KI review results | mitigate | All reviewer outputs committed verbatim to `.planning/phases/04-geometry-v1/04-3ki-review/`; consensus.md cross-references them with timestamps |
| T-4-R2 | Sycophancy bias | Claude self-review | mitigate | Regel 7 Anti-Sycophancy protocol enforced: actively hunt weaknesses, never just agree |
| T-4-R3 | Availability (Gemini 429) | Gemini review path | accept | Fallback policy documented per RESEARCH Open Question 5; Jens escalation required |
</threat_model>

<verification>
- All 3 review files exist and contain explicit verdicts
- consensus.md lists all 3 reviewers with their verdicts
- Full test suite green one final time
- wiki/log.md + wiki/index.md + ROADMAP.md + STATE.md updated
- Phase 4 marked Complete in ROADMAP.md
</verification>

<success_criteria>
1. Claude self-review walks the full S/L/A checklist and re-verifies Codex BLOCK findings
2. Codex adversarial review returns APPROVED (or issues were fixed and re-reviewed)
3. Gemini review returns APPROVED (or Jens-approved fallback documented)
4. consensus.md ratifies the 3-thumb verdict
5. Wiki discussions + summary + log + index updated
6. ROADMAP.md Phase 4 marked ✅ Complete
7. STATE.md points next action at Phase 5
8. Full Phase 4 test suite green
</success_criteria>

<output>
Create `.planning/phases/04-geometry-v1/04-07-SUMMARY.md` (and the overall
Phase 4 SUMMARY if your workflow keeps one) with:
- 3-KI verdicts table
- Any CHANGES_REQUESTED items and their resolution
- Phase 4 final test count
- Link to Phase 5 next-step
- Telegram notification template for Jens ("Phase 4 Geometry-v1 complete,
  starte Session-Reset" per Regel 5)
</output>
