---
id: '001'
title: Closed sprint-machine state is reachable
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: closed-state-still-unsatisfiable-after-branch-deletion.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Closed sprint-machine state is reachable

## Description

`close_sprint` merges, archives, and deletes the sprint branch as one
atomic sequence — but the sprint machine's `closed` state invariants are
`[is_sprint_archived, is_branch_merged]` (`schemas/state-machines/
sprint.yaml`), and `is_branch_merged` (`state_machine/predicates/
sprint.py:95-98`, backed by `ClasiStateReader.branch_merged()`,
`status/reader.py:427`) checks `git branch --merged <default>` — which
lists only branches that still exist. Since `close_sprint` deletes the
branch by default (`delete_branch=True`), a correctly closed sprint's
`closed` invariant can never be satisfied by evaluation; `evaluate_state`
falls back to the most-advanced matching state, reporting `pre-flight`
instead of `closed`. Found live by the final E2E validation run of the
028-030 campaign (2026-08-20): sprint 001 closed correctly (archived,
`status: done`, real merge commit) and `clasi status` still reported
`state: pre-flight`.

This is the third and last reason `closed` could never hold — sprint 030
already fixed the first two (an unrecordable `sprint_review` gate;
`is_close_report_present`/`is_review_satisfied`'s writer-less flags).
The fix (the issue's own Option 1, adopted after weighing all three
options it lists): drop `is_branch_merged` from `closed`'s invariants
entirely. `close_sprint` performs merge, archive, and branch deletion
atomically, so `is_sprint_archived` alone already implies the merge
happened — it is the single honest, git-free signal.

## Acceptance Criteria

- [x] `is_branch_merged` is removed from `sprint.yaml`'s `closed` state
      invariants — `closed`'s invariants become `[is_sprint_archived]`
      alone.
- [x] `is_branch_merged`'s predicate registration
      (`state_machine/predicates/sprint.py`) and `ClasiStateReader.
      branch_merged()` (`status/reader.py`) are deleted, not left as
      dead code — confirm no remaining caller with a repo-wide grep
      before removing.
- [x] A sprint driven through a real `close_sprint` call (via
      `tests/system/test_sprint_lifecycle_integration.py`, the natural
      home per the issue — it currently asserts DB/frontmatter
      agreement through close but not the *computed machine state*
      afterward, which is exactly the gap that let this through) asserts
      `evaluate_state`/`clasi status` reports `state: closed` for that
      sprint afterward.
- [x] **Non-negotiable: the three `TestGitSpawnCollapseInRealRepo` tests
      (`tests/unit/test_status/test_hook_injection.py`) stay green.**
      This ticket removes a predicate from the exact hot path sprint 030
      (ticket 002's regression fix) just finished restoring to zero git
      subprocess spawns. Run them explicitly before and after your
      change — not just as part of a full-file pytest run — and if
      either count changes, stop and investigate before proceeding; do
      not "fix" the test to accept a new spawn.
- [x] A repo-wide grep for `branch_merged` and `is_branch_merged` returns
      no hits outside test files this ticket updates.

## Implementation Plan

**Approach**: this is a deletion, not a redesign — remove the invariant,
remove its backing predicate and reader method, confirm the git-spawn
budget is unaffected (it already isn't reached on the hot path today —
verified during planning: `is_sprint_archived` is checked first and
short-circuits `all()` before `branch_merged()` ever runs, for every
active sprint the status-inject path evaluates), then add the
close-then-assert-`closed` integration test.

**Files to modify**:
- `src/clasi/schemas/state-machines/sprint.yaml` — remove
  `is_branch_merged` from `closed`'s `invariants`
- `src/clasi/state_machine/predicates/sprint.py` — delete the
  `is_branch_merged` predicate function and its `@predicate(...)`
  registration
- `src/clasi/status/reader.py` — delete `ClasiStateReader.branch_merged()`
- `tests/system/test_sprint_lifecycle_integration.py` — add the
  post-close `state: closed` assertion

**Do not modify**: `is_sprint_archived`'s own implementation or its
position in the invariants list (the 030/002 cheap-first-predicate
ordering this ticket relies on and simplifies, not reopens).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_status/test_hook_injection.py tests/unit/test_state_machine/test_predicates.py tests/system/test_sprint_lifecycle_integration.py -v`
- **New tests to write**: the close-then-assert-`state:closed` case in
  `test_sprint_lifecycle_integration.py`; a `test_predicates.py` case
  confirming `is_branch_merged` is no longer registered (or removed
  from any parametrized predicate list there).
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — not the full suite (that is `close_sprint`'s
  own gate, owned by ticket 008, run once at this sprint's close).
