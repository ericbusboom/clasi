---
id: '006'
title: 'Sprint lifecycle integration: hook overlay steps into create/acquire/pre-execution/close'
status: done
use-cases:
- SUC-005
- SUC-006
depends-on:
- '005'
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint lifecycle integration: hook overlay steps into create/acquire/pre-execution/close

## Description

Wire `clasi.design.overlay`'s four steps into the existing sprint
lifecycle tools, gated on the opt-in flag from ticket 001. Per the
research done during planning, the exact hook points are:

- **Seed + commit pristine copies**: at `create_sprint`
  (`src/clasi/tools/artifact_tools.py:230` / `Project.create_sprint`),
  on `main`, when the opt-in flag is set. Note: at plain `create_sprint`
  time the sprint is still roadmap-phase and the affected docs aren't
  known yet — the seed step's *which docs* input is determined once the
  sprint-planner identifies them during Phase 2 planning (ticket 008's
  skill rework specifies exactly when the sprint-planner calls this).
  This ticket implements the callable seed step and wires it to fire at
  the point the sprint-planner determines the affected doc list, not
  necessarily at the literal `create_sprint` call if that's before the
  docs are known — resolve this sequencing precisely against ticket 008's
  skill text and update this ticket's plan if the two disagree.
- **Commit edited copies**: at `review_sprint_pre_execution`
  (`artifact_tools.py:2544`) — this function currently only validates;
  add the commit-edits call as a new step, still gated on opt-in, run
  only after existing validation passes.
- **Apply to canonical docs**: inside `_close_sprint_full`
  (`artifact_tools.py:1300`), immediately after the `sprint.archive()`
  step and before the version-bump/tag step — per sprint.md's Migration
  Concerns, a failed apply must block the tag/merge steps exactly like a
  failed test run does today.

All three hooks must be no-ops (unchanged existing behavior) when the
opt-in flag is unset or explicitly off.

## Acceptance Criteria

- [x] With opt-in **off** (default/unset), `create_sprint`,
      `acquire_execution_lock`, `review_sprint_pre_execution`, and
      `close_sprint` behave byte-for-byte identically to their current
      behavior — no `design/` directory is created, no extra git
      commits appear. Cover with a regression test that runs the full
      existing lifecycle test suite (or the relevant subset) with opt-in
      unset and diffs behavior/output against pre-sprint-021 baseline
      expectations.
- [x] With opt-in **on**: pristine copies are seeded and committed before
      any sprint-planner edit lands (verify via git log ordering in a
      fixture, matching SUC-005's acceptance criteria).
- [x] With opt-in **on**: `review_sprint_pre_execution` commits the
      edited `design/` copies as its new final step, only after existing
      validation checks pass — a sprint that fails existing
      pre-execution checks (wrong branch, tickets not ready, etc.) must
      not get a design commit either.
- [x] With opt-in **on**: `acquire_execution_lock`'s branch creation
      happens from a tree that already includes the edited-copies commit
      (per Open Question 3's resolution — both commits happen on `main`
      before the branch is cut), so the sprint branch starts clean with
      respect to `design/`.
- [x] With opt-in **on**: `_close_sprint_full`'s apply step runs after
      `sprint.archive()` and before the version-bump/tag step; if apply
      fails, the function returns/raises before reaching the tag step,
      and `completed_steps` (or equivalent) reflects that the process
      stopped at apply, not tag.
- [x] Validator (ticket 004) is invoked at the end of the apply step (or
      immediately after) to confirm canonical `docs/design/` still passes
      validation post-apply — a broken apply must be caught here, not
      discovered later.

## Implementation Plan

**Approach**: Minimal-surface-area edits to existing functions in
`artifact_tools.py` and `sprint.py` — add a conditional call to the
relevant `clasi.design.overlay` function at each hook point, gated by
`project.design_docs_opt_in` (ticket 001). Do not restructure the
existing functions' control flow beyond what's needed to insert these
calls; this ticket's job is integration, not a lifecycle rewrite.

**Files to create/modify**:
- `src/clasi/tools/artifact_tools.py` — `create_sprint` (or wherever the
  sprint-planner's "affected docs known" moment is determined — resolve
  against ticket 008), `review_sprint_pre_execution` (line ~2544),
  `_close_sprint_full` (line ~1300).
- `src/clasi/sprint.py` — `Sprint.archive()` region, if the apply hook is
  cleaner to place there than in `artifact_tools.py` directly (match
  whichever existing convention keeps orchestration logic in
  `artifact_tools.py` and lower-level operations in `sprint.py`).

**Testing plan**:
- Full lifecycle integration test with opt-in on: create sprint, verify
  seed commit; simulate sprint-planner edit; verify dirty tree; run
  pre-execution review; verify commit and clean tree; acquire lock;
  verify branch state; run close; verify canonical docs updated and
  validator passes.
- Full lifecycle regression test with opt-in off: existing behavior
  unchanged.
- Failure-path test: apply failure during close blocks tag/merge steps.

**Documentation updates**:
- None beyond code comments at each hook point explaining why the call is
  there and what it's gated on — skill-level documentation of this
  behavior is ticket 008's responsibility.

## Implementation Notes (as built)

Sequencing resolution: the seed step is **not** hardcoded into the
`create_sprint` MCP tool. Since the affected-doc list is only known once
the sprint-planner reaches Phase 2 planning (a fact `create_sprint` itself
predates), this ticket adds a new MCP tool,
`seed_sprint_design_overlay(sprint_id, doc_names)`, that the
sprint-planner calls once it has identified the affected canonical docs.
It is a no-op (`{"opted_in": ..., "seeded": []}`) when opt-in is off or
`doc_names` is empty, and otherwise seeds + commits pristine copies via
`clasi.design.overlay.seed_and_commit` — satisfying SUC-005's "committed
before any edit lands" requirement regardless of which MCP call site
triggers it. Ticket 008 documents exactly when in Phase 2 the
sprint-planner is expected to call this tool.

Hook points implemented:
- `seed_sprint_design_overlay` (new tool, `artifact_tools.py`) — Step 1.
- `review_sprint_pre_execution` (`artifact_tools.py`) — after all existing
  checks, if `passed` and opt-in and `sprint.design_dir` exists: runs
  `generate_diffs` then `commit_edits`; a git failure during either flips
  `passed` back to `False` and is reported via `issues`. Response gains a
  `design_overlay` key.
- `_close_sprint_full` (`artifact_tools.py`) — new `design_overlay_apply`
  step inserted between `db_update` and `version_bump` in both
  `completed_steps`/`all_steps`: applies the overlay via
  `clasi.design.overlay.apply`, then runs `clasi.design.validate`; either
  raising blocks the response before `version_bump`/tag/merge, matching
  the failed-test-run error shape (`status: error`, `completed_steps`
  truncated at the failing step).
- `Sprint.design_dir` (`sprint.py`) — new property, `self._path / "design"`
  (moves correctly with `sprint.archive()` since it's derived from
  `self._path`).
- `acquire_execution_lock` was **not** modified — it already creates the
  branch from whatever `main` currently is, so once
  `review_sprint_pre_execution` commits the edited overlay on `main`,
  the subsequent branch cut already includes it. No code change was
  needed there, only the ordering guaranteed by the other two hooks.
