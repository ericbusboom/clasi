---
id: 008
title: Extend _prune_sprint_worktrees for orphaned ticket worktrees
status: done
use-cases:
- SUC-003
depends-on:
- '005'
- '007'
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extend _prune_sprint_worktrees for orphaned ticket worktrees

## Description

Issue A Chunk 7 — the close-time safety net. This is the SECOND of the
two `artifact_tools.py` tickets in this sprint (depends on ticket 005 so
it starts from the already-Issue-B-rewritten file, per
architecture-update.md "Shared-File Sequencing" — ticket 005 does not
touch `_prune_sprint_worktrees` and this ticket does not touch
`insert_sprint`/`_renumber_sprint_dir`/`review_sprint_pre_close`, so the
two tickets' diffs do not overlap). Also depends on ticket 007
(`reconcile_worktrees` must exist to reuse its classification logic, or
this ticket reimplements equivalent conservative logic inline — reuse is
preferred to avoid classification drift between the two call sites).

Extend `_prune_sprint_worktrees` (`src/clasi/tools/artifact_tools.py`,
currently ~lines 1155-1207) — which today only matches
`refs/heads/<branch_name>` (the sprint branch's own worktree) — to also
match `refs/heads/ticket/<sprint-id>-*` worktrees. Two implementation
options, either acceptable, but the second is preferred if the interfaces
line up cleanly:

- **Option A**: extend the existing porcelain-parsing loop in
  `_prune_sprint_worktrees` to also match the ticket-branch pattern
  (regex or prefix match on `refs/heads/ticket/{sprint_id}-`), applying
  the confirmed decision inline: always remove the worktree *directory*;
  delete the branch only if the audit record (read via
  `worktree.read_audit_record`) marks it `merged`/`cleaned_up`; retain
  (do not delete) branches marked `failed`/`conflict`, and report them.
- **Option B (preferred)**: have `_prune_sprint_worktrees` call
  `worktree.reconcile_worktrees(repo_root, sprint_dir)` for the
  ticket-worktree sweep, and keep its own existing porcelain-parsing loop
  only for the sprint branch's own worktree (unchanged). This gives one
  code path for ticket-worktree classification instead of two
  independently-maintained ones.

Whichever option is chosen, `_prune_sprint_worktrees`'s return shape
(`worktrees_pruned`, `worktrees_failed` — consumed by `_close_sprint_full`
at ~lines 1632-1642) must gain a way to report retained
`failed`/`conflict` branches distinctly from successfully pruned ones, so
`close_sprint`'s final JSON result (~lines 1651-1675) can surface them
(e.g. a new `worktrees_retained` key alongside the existing
`worktrees_pruned`/`worktrees_failed`). Update the `_close_sprint_full`
step-9 block to thread this new information through to the returned
result.

Update the mocked `side_effect` sequences in
`tests/system/test_artifact_tools.py` (e.g. around
`test_full_lifecycle_success`, ~lines 739-753, which already mocks `git
worktree list --porcelain`) to include a scenario with an orphaned
`ticket/<sprint>-*` worktree in the porcelain output, so the existing
close-sprint lifecycle tests exercise the new match path.

## Acceptance Criteria

- [x] `_prune_sprint_worktrees` (or `close_sprint`'s orchestration around
      it) removes orphaned `ticket/<sprint-id>-*` worktree directories at
      sprint close, not just the sprint branch's own worktree.
- [x] A `ticket/<sprint-id>-*` branch whose audit state is
      `merged`/`cleaned_up` has both its directory and branch removed.
- [x] A `ticket/<sprint-id>-*` branch whose audit state is
      `failed`/`conflict` has its directory removed but its BRANCH
      RETAINED, and is reported in the close result (new field, e.g.
      `worktrees_retained`).
- [x] `close_sprint`'s final JSON result surfaces retained
      failed/conflict branches distinctly from pruned ones.
- [x] `tests/system/test_artifact_tools.py`'s existing close-sprint mock
      sequences are updated to include an orphaned ticket worktree
      scenario and pass.
- [x] Existing sprint-branch-only pruning behavior (the pre-existing
      case) is unchanged — no regression for sprints that never used
      worktrees.

## Files to create or modify

- `src/clasi/tools/artifact_tools.py` — `_prune_sprint_worktrees` (and/or
  `_close_sprint_full`'s step 9 threading of the new retained-branches
  info).
- `tests/system/test_artifact_tools.py` — update mock `side_effect`
  sequences for the close-sprint lifecycle tests.

## Testing

- **Existing tests to run**: `tests/system/test_artifact_tools.py`
  (all close_sprint / `_prune_sprint_worktrees` tests), full
  `uv run pytest`.
- **New tests to write**: a `_prune_sprint_worktrees` (or
  `close_sprint`) test with a mocked `git worktree list --porcelain`
  output containing one merged-not-cleaned ticket worktree (expect
  removed + branch deleted) and one failed/conflict ticket worktree
  (expect directory removed, branch retained, reported in the result);
  a regression test confirming the pre-existing sprint-branch-only
  pruning path is unaffected.
- **Verification command**: `uv run pytest`
