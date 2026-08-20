---
status: pending
type: bug
tags:
- reliability-campaign
- state-machine
- follow-up
---

# The `closed` sprint state is still unsatisfiable: close_sprint deletes the branch `is_branch_merged` needs

## Description

Found by the final end-to-end validation run of the 028-030 reliability
campaign (2026-08-20), driving a real subject agent through a complete
sprint lifecycle inside the E2E container.

The subject planned, executed, and closed sprint `001` correctly:

```
clasi/sprints/done/001-menu-and-number-game-minimal-playable/   # archived
status: done                                                    # frontmatter
cc4257b Merge branch 'sprint/001-menu-and-number-game-minimal-playable'
```

`clasi status` nonetheless reported that sprint as **`state: pre-flight`**,
not `closed`.

## Cause

The `closed` state's invariants are `[is_sprint_archived,
is_branch_merged]`. The archive half is satisfied. The merged half is not,
and cannot be:

- `ClasiStateReader.branch_merged` (`src/clasi/status/reader.py:427`)
  resolves the sprint's branch name from frontmatter, then tests
  membership in `git branch --merged <default>`.
- `git branch --merged` lists **branches that still exist**.
- `close_sprint` deletes the sprint branch after merging it
  (`delete_branch=True` is the default, and is what the whole process
  does — "never leave a sprint branch dangling" is an explicit rule in
  the team-lead agent definition).

So the branch is gone by the time anyone asks, `branch_merged` returns
False, `closed` never matches, and `evaluate_state` falls back to the
most-advanced state that does match — `pre-flight`.

Verified in the container: `git branch --merged master` lists only
`master`; the sprint branch is absent.

## This is a survivor, not a regression

Before sprint 030, `closed` was unsatisfiable for a *different* reason —
it required an `is_review_satisfied` gate that `record_gate` rejected
outright. Ticket 030-002 removed that unrecordable gate, and the 030-002
regression fix added `is_sprint_archived`. Both were correct. But the
state is still unsatisfiable, now because of the branch-deletion
interaction rather than the gate. The campaign fixed two of three reasons
`closed` could never hold; this is the third.

It is the same pattern the campaign exists to eliminate: **an invariant
that references something the toolchain itself destroys.**

## Options

1. **Drop `is_branch_merged` from `closed`.** `close_sprint` performs
   merge, archive, and branch deletion atomically, so the archive
   location already implies the merge happened. This makes
   `is_sprint_archived` the single honest signal and keeps the check
   git-free (preserving the zero-git-spawn property on the status-inject
   hot path that the 030-002 regression fix restored). Simplest and most
   truthful.
2. **Make `branch_merged` treat "branch absent + sprint archived" as
   merged.** Preserves the invariant's wording but adds a special case
   that is really option 1 wearing a disguise.
3. **Look for merge evidence instead of the branch** (e.g. a merge commit
   naming the branch). Most literal, but spawns git on a hot path — the
   thing 030-002 just removed. Not recommended.

Recommendation: option 1.

## Acceptance criteria

- [ ] A sprint that has been closed through the normal `close_sprint`
      flow reports `state: closed` from `clasi status`.
- [ ] The status-inject path still spawns **zero** git subprocesses —
      the three `TestGitSpawnCollapseInRealRepo` tests must stay green.
- [ ] A test drives a real sprint through close and asserts the reported
      state, so this cannot silently regress again. The lifecycle test
      added by ticket 030-006
      (`tests/system/test_sprint_lifecycle_integration.py`) is the
      natural home — note it currently asserts DB/frontmatter agreement
      through close but does not assert the *computed machine state*
      afterward, which is exactly the gap that let this through.
