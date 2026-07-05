---
id: '010'
title: Wire reconcile_worktrees into controller trigger points
status: done
use-cases:
- SUC-003
depends-on:
- '007'
- 009
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire reconcile_worktrees into controller trigger points

## Description

Issue A Chunk 5 — what actually prevents accumulation; on the critical
path per the issue (after Chunk 4 / ticket 009). Depends on ticket 007
(`reconcile_worktrees` must be real) and ticket 009 (the mode-selection
and per-group-loop prose it layers onto must already exist in
`execution.md`).

Edit `src/clasi/schemas/se-process/instructions/execution.md` again (a
second, later ticket touching the same file as ticket 009 — deliberately
sequenced, not parallel, so this ticket's diff lands on top of ticket
009's already-merged mode-selection/grouping/per-group-loop sections
rather than conflicting with them) to add the three reaper trigger
points described in the issue's Cleanup Discipline:

1. **Preflight sweep (session/execution start)**: before any ticket work
   begins (parallel or serial — actually, only relevant to the parallel
   path, since the serial path has no worktrees to sweep), call
   `reconcile_worktrees(repo_root, sprint_dir)`. Report a one-line
   summary of what it cleaned. If it returns any `escalated` entries,
   the controller must resolve them — per the recovery prose from the
   spec (§12): prompt for one of resume / abandon / inspect, and
   **never auto-resume ambiguous work without explicit confirmation** —
   before starting any new ticket work in this sprint.

2. **Per-creation gate (before creating each group's worktrees)**:
   immediately before the per-group loop (from ticket 009) creates
   worktrees for a new group, call `reconcile_worktrees` again. If it
   returns any unresolved (`escalated`) entries, the controller STOPS —
   it must not create new worktrees while unresolved ones exist.
   Accumulation is explicitly framed as a **blocking condition**, not a
   background annoyance: state this in the prose in those exact terms so
   future editors don't soften it into a warning.

3. **Escalation prose for ambiguous cases**: a dedicated subsection
   describing what "resolve" means for an escalated worktree — options
   are recover (re-dispatch the programmer agent into the existing
   worktree to finish/fix the work), abandon (remove the worktree via
   `cleanup_worktree(keep_branch=True)`, keep the branch for inspection),
   or inspect (take no automated action, just acknowledge and move it
   into a explicitly-tracked "known, deferred" state so it doesn't
   silently reappear as a fresh escalation every sweep). This subsection
   also covers the orphaned-worktree and abandoned-branch recovery paths
   from spec §10/§12 (controller crash mid-lifecycle; a `ticket/<sprint-
   id>-*` branch with no live worktree and a `failed`/`cleaned_up`/missing
   audit entry).

Also confirm (read, do not necessarily edit unless a gap is found) that
the close-time safety net from ticket 008 is referenced from this file's
"Close" section (from ticket 009) as "the final reconcile pass" — the
issue frames Chunk 7 (ticket 008) as the third trigger point, and the
prose here should make the three-trigger-point story complete and
explicit in one place (even though the third trigger's actual
implementation lives in `artifact_tools.py`, not `execution.md`).

## Acceptance Criteria

- [x] `execution.md`'s parallel path calls `reconcile_worktrees` at
      execution/session start (preflight sweep) before any new ticket
      work begins, and reports what it cleaned.
- [x] `execution.md`'s parallel path calls `reconcile_worktrees` again
      immediately before creating each group's worktrees (the
      per-creation gate), and explicitly STOPS (does not proceed to
      worktree creation) if any `escalated` entries remain unresolved.
- [x] The prose states, in unambiguous language, that accumulation is a
      **blocking condition** at the per-creation gate, not merely logged.
- [x] A dedicated escalation-handling subsection describes recover /
      abandon / inspect options and states that ambiguous work is never
      auto-resumed without explicit confirmation.
- [x] The three trigger points (session start, per-creation gate, sprint
      close) are each identifiable in the document as the same
      `reconcile_worktrees` mechanism applied at different times.
- [x] Ticket 009's mode-selection, grouping, and per-group-loop prose is
      unmodified by this ticket except for the insertion points needed to
      call out the two new trigger points (i.e. this ticket does not
      rewrite unrelated sections).

## Files to create or modify

- `src/clasi/schemas/se-process/instructions/execution.md`

## Testing

- **Existing tests to run**: any test asserting on `execution.md`
  content (grep `tests/` first), full `uv run pytest`.
- **New tests to write**: if the repo has a convention for testing
  instruction-file content (per ticket 009's note), extend it to cover
  the new preflight-sweep and per-creation-gate sections. If no such
  convention exists, do not invent one speculatively — rely on the
  behavioral tests already covering `reconcile_worktrees` itself
  (ticket 007) as the source of truth for correctness, and treat this
  ticket's own correctness as a documentation-review concern.
- **Verification command**: `uv run pytest`

## Completion notes

- Grepped `tests/` for any test asserting on `execution.md` content:
  `tests/unit/test_skill_stub_loader.py` and
  `tests/clasi/schemas/test_solo_schema.py` both reference an
  `execution.md` filename, but only assert file existence / frontmatter
  shape (and against the unrelated `solo-process` stub tree, not
  `se-process/instructions/execution.md`). No convention exists for
  testing instruction-file prose content. Per the ticket's own testing
  guidance, no new test was invented; `reconcile_worktrees` behavioral
  correctness remains covered by ticket 007's tests
  (`tests/clasi/test_worktree.py`).
- Full suite: `uv run pytest` → `2423 passed in 239.29s`, coverage
  87.89% (threshold 84%).
