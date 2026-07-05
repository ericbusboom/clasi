---
id: '006'
title: Implement worktree.py lifecycle functions and behavioral tests
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement worktree.py lifecycle functions and behavioral tests

## Description

Issue A Chunks 1 + 3 (atomic pair — the issue's own critical path
requires these to land together since the stub `NotImplementedError`
tests break the instant real implementations land). This ticket has NO
dependency on any Issue B ticket and no dependency on ticket 001 (it does
not touch `sprint.py`) — it can start immediately and run in parallel
with tickets 001-005.

Implement 7 of the 8 stub functions in `src/clasi/worktree.py` to their
existing docstring contracts (the docstrings ARE the implementation
contract — read them in full before writing code). **`reconcile_worktrees`
is NOT part of this ticket** — it is a new function (not a stub) with
higher composition risk and is split into ticket 007, which depends on
this ticket.

Implement in this order (per the issue's guidance: audit pair → independence
→ git functions):

1. **`write_audit_record(sprint_dir, event)`**: path
   `sprint_dir/.worktree-audit.json`. Read-modify-write: load existing or
   seed `{"sprint_id": None, "worktrees": []}`. Validate `event` has
   `ticket_id` and `state` keys, else raise `ValueError`. Merge `event`
   into the matching entry (by `ticket_id`) or append. Atomic write:
   write to `.worktree-audit.json.tmp`, then `os.replace(tmp, final)`.

2. **`read_audit_record(sprint_dir)`**: absent file → return the default
   dict (no raise). Existing file → `json.loads` (let
   `json.JSONDecodeError` propagate on malformed content).

3. **`check_independence(tickets)`**: the highest-risk function.
   File-set extraction priority: (a) `files_to_create`/`files_to_modify`
   frontmatter keys if present on the ticket dict; (b) parse the ticket's
   plan-file body for a `## Files to create or modify` heading (accept
   both `##` and `###`, and accept "Files to create"/"Files to modify" as
   separate or combined headings) — collect list items until the next
   heading of equal or higher level; (c) if neither source yields a file
   set, treat the ticket as dependent on all others via an "unknown"
   sentinel. Normalize every path to repo-relative POSIX form and strip a
   leading `src/` (so `src/clasi/foo.py` == `clasi/foo.py` — write a
   dedicated regression test for this, it is called out explicitly as a
   footgun in the issue). Two tickets are dependent if their normalized
   source-file sets overlap, OR their derived `test_<stem>.py` basenames
   overlap, OR either ticket's set is the "unknown" sentinel. Group by
   connected components of the dependence graph; order groups by
   topological sort of aggregated `depends-on`, tie-break by ticket id
   ascending. Return `list[list[str]]` of ticket-id groups.

4. **`create_worktree(repo_root, sprint_id, ticket_id)`**: path
   `(repo_root/".."/f"worktree-{sprint_id}-{ticket_id}").resolve()`. Run
   `git worktree add --detach <path> HEAD` via `subprocess.run([...],
   cwd=repo_root, capture_output=True, text=True)` (matching the
   `sprint.py` git-op style), check returncode. Detached HEAD is
   required because the sprint branch is already checked out in the main
   tree (git refuses the same branch in two worktrees). Return the
   resolved absolute `Path`.

5. **`create_ticket_branch(worktree_path, sprint_id, ticket_id, slug)`**:
   `git checkout -b ticket/<sprint_id>-<ticket_id>-<slug>` with
   `cwd=worktree_path`. Return the full branch name string. The caller
   (controller, ticket 009/010) derives `slug` via
   `templates.slugify(title)[:40]` — this function does not transform
   the slug it's given.

6. **`validate_worktree(worktree_path, ticket_path)` → bool**: three
   checks, all must pass, function never raises: (1) run a test command
   — accept a `test_command` parameter (default `["uv", "run",
   "pytest"]`, matching `close_sprint`'s `test_command` pattern so tests
   can inject a fast stub) from `cwd=worktree_path`, check returncode 0;
   (2) `git status --porcelain` from `cwd=worktree_path` returns empty
   stdout; (3) read `ticket_path` frontmatter (reuse
   `clasi.frontmatter.read_frontmatter` or `clasi.artifact.Artifact`) and
   check `status == "done"`. Return `True` only if all three pass, else
   `False` — never raise for a failed check; only raise on truly
   unexpected errors if the docstring contract implies it (it does not —
   keep it a pure bool-returning function).

7. **`merge_ticket_branch(repo_root, sprint_branch, ticket_branch)`**:
   2nd-highest risk. Checkout `sprint_branch` in `repo_root`. Try `git
   merge --ff-only <ticket_branch>` first; if that fails because the
   branch isn't a fast-forward candidate (not a conflict — an ordinary
   non-ff rejection), fall back to `git merge --no-ff <ticket_branch> -m
   "Merge <ticket_branch>"`. Detect an actual conflict via `git diff
   --name-only --diff-filter=U` returning non-empty output (same
   technique as `sprint.py` lines ~359-368) → run `git merge --abort`,
   then raise `MergeConflictError` (reuse the class already defined at
   `sprint.py` lines 10-19 — import it, do not redefine) carrying the
   conflicted files list. **No rebase, ever.** Note the docstring
   reconciliation: the current docstring says this function "writes a
   `conflict` state to the audit record" — it does not have a
   `sprint_dir` parameter to do so. This function stays pure git-and-raise;
   the *controller* (ticket 010) is responsible for catching
   `MergeConflictError` and writing the audit `conflict` state. Update
   the docstring in this ticket to remove the inaccurate claim.

8. **`cleanup_worktree(repo_root, worktree_path, ticket_branch,
   keep_branch=False)`**: `git worktree remove --force <worktree_path>`
   from `cwd=repo_root`. If `keep_branch` is `False`, also run `git
   branch -d <ticket_branch>` (safe delete — never `-D`, never force
   delete an unmerged branch). If `keep_branch` is `True`, skip the
   branch deletion. Must be idempotent — calling it again on an
   already-removed worktree should not raise (check `worktree_path`
   existence or treat a "not a working tree" git error as success).

Delete `tests/clasi/test_worktree_stubs.py` (the `NotImplementedError`
smoke tests) and create `tests/clasi/test_worktree.py` with real
behavioral tests, per the Testing section below. This deletion+creation
must land in the SAME commit/ticket as the implementation (this is the
"atomic pair" from Chunks 1+3) — do not leave the stub tests in a broken
state even transiently within this ticket's own work.

## Acceptance Criteria

- [x] All 7 functions listed above (excluding `reconcile_worktrees`) have
      real implementations matching their existing docstrings; none
      raises `NotImplementedError` anymore.
- [x] `tests/clasi/test_worktree_stubs.py` is deleted;
      `tests/clasi/test_worktree.py` exists with real behavioral
      coverage (see Testing).
- [x] `check_independence` correctly groups two tickets with disjoint
      file sets as independent, and two tickets with overlapping file
      sets (including the `src/` vs no-`src/` normalization case) as
      dependent.
- [x] `check_independence` treats a ticket with no discoverable file
      information as dependent on all others.
- [x] `merge_ticket_branch` on a genuine conflict aborts the merge
      (working tree is clean afterward — verified via `git status
      --porcelain`), raises `MergeConflictError` with the conflicted
      files populated, and does NOT write any audit state itself.
      `merge_ticket_branch`'s docstring is corrected to remove the
      inaccurate "writes audit state" claim.
- [x] `validate_worktree` accepts an injectable `test_command` parameter
      and never raises — always returns `bool`.
- [x] `cleanup_worktree` is idempotent: calling it twice on the same
      already-removed worktree does not raise.
- [x] `create_worktree` places the worktree as a sibling of `repo_root`
      (outside the main working tree), using `--detach`.
- [x] Full `uv run pytest` passes, including the new test module.

## Files to create or modify

- `src/clasi/worktree.py` — implement 7 functions (all except
  `reconcile_worktrees`).
- `tests/clasi/test_worktree_stubs.py` — delete.
- `tests/clasi/test_worktree.py` — create (new behavioral test module).

## Testing

- **Existing tests to run**: full `uv run pytest` (confirms the deletion
  of the stub test file doesn't leave collection errors).
- **New tests to write** (`tests/clasi/test_worktree.py`):
  - Audit pair: create new record; merge/append by `ticket_id`; atomic
    write leaves no `.tmp` file behind; `ValueError` on `event` missing
    `ticket_id`/`state`; `read_audit_record` on absent file returns the
    default dict (no raise); `read_audit_record` on malformed JSON
    propagates `json.JSONDecodeError`.
  - `check_independence`: overlapping file sets → dependent; disjoint →
    independent; shared derived test module → dependent even with
    disjoint source files; missing file info → dependent on all; each
    heading spelling variant (`##`/`###`, "Files to create"/"Files to
    modify") parses correctly; `src/` normalization regression
    (`src/clasi/foo.py` vs `clasi/foo.py` treated as the same file);
    `depends-on` group ordering with a tie-break case.
  - Real-git fixture (a `tmp_path` git repo with an initial commit,
    matching the style of existing git-fixture tests in this repo if any
    exist — check `tests/` for a reusable fixture pattern first) driving:
    `create_worktree` (assert path is a sibling of repo root, worktree is
    detached); `create_ticket_branch` (assert branch name matches the
    pattern); `validate_worktree` with an injected fast `test_command`
    (e.g. `["true"]` or `["python", "-c", "pass"]`) covering all-pass,
    test-failure, dirty-tree, and status-not-done cases; `merge_ticket_branch`
    covering fast-forward, `--no-ff` fallback (sprint branch advanced),
    and conflict-abort-leaves-clean-tree; `cleanup_worktree` with
    `keep_branch=True` and `keep_branch=False`, and a call on an
    already-removed worktree (idempotency).
- **Verification command**: `uv run pytest`
