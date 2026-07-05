---
id: '007'
title: Implement reconcile_worktrees reaper and tests
status: done
use-cases:
- SUC-003
depends-on:
- '006'
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement reconcile_worktrees reaper and tests

## Description

Issue A — the core of the whole plan. Depends on ticket 006 (the audit
pair and `cleanup_worktree` it composes must already be implemented and
real, not stubs). This is the standing cleanup engine that prevents the
worktree-directory accumulation that killed this feature previously —
treat it as the highest-value, highest-scrutiny function in the sprint.

Add a new function to `src/clasi/worktree.py` (not a stub — net new,
not in the original 8):

```python
def reconcile_worktrees(repo_root: Path, sprint_dir: Path) -> dict:
```

Implementation: read `.worktree-audit.json` via `read_audit_record
(sprint_dir)`. Run `git worktree list --porcelain` from `cwd=repo_root`
and parse it (reuse the parsing technique from
`artifact_tools._prune_sprint_worktrees` as a reference — it already
parses this exact porcelain format, though this function must match
`ticket/<sprint_id>-*` branches, not the sprint branch itself). For every
live worktree whose branch matches `refs/heads/ticket/<sprint_id>-*`,
classify it using audit state + live git state, per this table (verbatim
from the issue's Cleanup Discipline):

| Classification | Signal | Action |
|---|---|---|
| merged-not-cleaned | audit state `merged`, branch is merged into the sprint branch (`git merge-base --is-ancestor <ticket-branch> <sprint-branch>`) | `cleanup_worktree(..., keep_branch=False)`, update audit to `cleaned_up` |
| clean-but-abandoned | `git status --porcelain` in the worktree is empty, no uncommitted work, audit state is not `in_progress` | `cleanup_worktree(..., keep_branch=True)`, update audit to `cleaned_up` |
| ambiguous | uncommitted/dirty tree, OR audit state is `failed`/`conflict`/`in_progress` | leave untouched, add to `escalated` |

Also detect and report two edge cases, neither of which triggers a
cleanup action: an audit entry whose worktree path no longer appears in
`git worktree list` (already gone — reconcile the audit record, e.g. mark
`cleaned_up` if not already, and note it); a live `ticket/<sprint_id>-*`
worktree with NO matching audit entry (a "rogue" worktree — someone or
something created it outside the tracked lifecycle). Both cases are
reported in the return value's `rogue` list per the function's contract.

Return `{"cleaned": [...], "escalated": [...], "rogue": [...]}` where
each list element is a dict describing the ticket_id/path/branch/reason
sufficient for a human or the controller to act on. The function is
**pure of any prompting or interactive decision-making** — it classifies
and safely auto-cleans, and returns the rest for the caller to decide.
It must be idempotent: calling it twice in a row with no state change in
between must return `{"cleaned": [], "escalated": [...], "rogue": []}`
on the second call (nothing new to clean).

## Acceptance Criteria

- [x] `reconcile_worktrees(repo_root, sprint_dir)` exists in
      `worktree.py` and returns a dict with `cleaned`, `escalated`, and
      `rogue` keys.
- [x] A worktree in `merged-not-cleaned` state is auto-cleaned: worktree
      directory AND branch removed, audit updated to `cleaned_up`.
- [x] A worktree in `clean-but-abandoned` state is auto-cleaned: worktree
      directory removed, branch RETAINED, audit updated to `cleaned_up`.
- [x] A worktree with uncommitted changes, or audit state `failed`/
      `conflict`/`in_progress`, is NEVER removed — it appears in
      `escalated` untouched.
- [x] An audit entry with no corresponding live worktree, and a live
      worktree with no audit entry, are both reported (in `rogue` or
      reconciled appropriately) without raising.
- [x] Calling `reconcile_worktrees` twice in a row (no state change
      between calls) is idempotent — the second call cleans nothing new.
- [x] No `ticket/<sprint_id>-*` worktree survives a single
      `reconcile_worktrees` call unless it was returned in `escalated`.
- [x] The function never prompts, blocks, or raises for a normal
      ambiguous case — only genuine unexpected errors (e.g. corrupt audit
      JSON, which `read_audit_record` already lets propagate) surface as
      exceptions.

## Files to create or modify

- `src/clasi/worktree.py` — add `reconcile_worktrees`.
- `tests/clasi/test_worktree.py` — add reaper tests (same file created
  in ticket 006; this ticket extends it).

## Testing

- **Existing tests to run**: `tests/clasi/test_worktree.py` (from ticket
  006, must still pass), full `uv run pytest`.
- **New tests to write** (in `tests/clasi/test_worktree.py`): real-git
  fixture with a worktree in each of the three classes present
  simultaneously in one `reconcile_worktrees` call — assert
  merged-not-cleaned is fully removed (dir + branch), clean-but-abandoned
  has its dir removed but branch retained, ambiguous (dirty tree or
  `failed` audit state) is untouched and appears in `escalated`; an audit
  entry with no live worktree is handled without raising; a live
  worktree with no audit entry appears in `rogue`; a second consecutive
  call with no intervening state change returns empty `cleaned`
  (idempotency); assert no `ticket/*` worktree directory remains on disk
  after the call except those in `escalated`. This is called out in the
  issue as the single highest-value test in the whole plan — do not
  under-scope it.
- **Verification command**: `uv run pytest`
