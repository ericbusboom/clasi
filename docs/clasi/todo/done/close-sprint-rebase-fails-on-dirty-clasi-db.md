---
status: done
sprint: '011'
tickets:
- '001'
---

# `close_sprint` fails at the rebase/merge step on its own dirty `.clasi.db` write

Reported by an upstream agent against CLASI version `0.20260424.6`,
in project mediacms fork at `/Users/eric/proj/league/scratch/mediacms`.
Reproduced 3 of 3 `close_sprint` invocations (sprints 001, 002, 003 all
failed identically).

## Symptom

`close_sprint` executes its lifecycle in order:
`precondition_verification → tests → archive → db_update →
version_bump → merge → push_tags → delete_branch`. The "merge" step
runs `git rebase <sprint-branch> onto <main_branch>` and aborts with:

```
error: cannot rebase: You have unstaged changes.
error: Please commit or stash them.
```

The dirty file is always `docs/clasi/.clasi.db`. Earlier lifecycle
steps (`db_update`, `archive`, or `version_bump`) write to the SQLite
state DB on disk but never stage or commit the change. By the time
`merge` runs, the working tree is dirty and `rebase` refuses.

Tool returns:

```json
{
  "status": "error",
  "error": {
    "step": "merge",
    "message": "Rebase of sprint/<id>-<slug> onto main failed: error: cannot rebase: You have unstaged changes..."
  },
  "completed_steps": ["precondition_verification", "tests", "archive", "db_update", "version_bump"],
  "remaining_steps": ["merge", "push_tags", "delete_branch"]
}
```

Retry doesn't help: `db_update` re-dirties the same file each time.
Execution lock is also left held because `merge` fails before the
lock release.

## Why we didn't hit this in sprints 008/009/010

Worth investigating before fixing. Possible factors that may have
masked the issue in our own usage:

- We used `main_branch="master"`; the report used `main_branch="main"`.
- We passed a real `test_command="python -m pytest --no-cov -q"`;
  the report passed `test_command=""`.
- Possibly later code (post-`0.20260424.6`) added a stash or commit
  step we don't see hitting because of something specific to our
  project state.
- The reporter's `.clasi.db` may be tracked; ours might be gitignored
  or in a different state.

Confirm whether the bug still exists in HEAD (currently `0.20260425.24`)
before designing the fix.

## Repro (per reporter)

1. Plan a sprint, advance through `ticketing → executing`.
2. Implement and complete all tickets; mark them done; move TODOs to
   `docs/clasi/todo/done/`.
3. Commit everything (working tree clean, sprint branch up-to-date).
4. Call
   `close_sprint(sprint_id="NNN", branch_name="sprint/NNN-...", main_branch="main", test_command="")`.
5. Observe the failure; `git status` shows
   `modified: docs/clasi/.clasi.db`.

## Workaround the reporter used (5 lines per sprint)

```
git stash
git checkout main
git merge --no-ff sprint/<id>-<slug>
git branch -D sprint/<id>-<slug>
git stash drop
git add -A && git commit -m "chore(NNN): archive sprint"
```

Plus manual `release_execution_lock` because the lock isn't released
on failure.

## Suggested fixes (any one is sufficient — pick during planning)

1. After `db_update`, auto-stage and commit `docs/clasi/.clasi.db` on
   the sprint branch before proceeding to merge.
2. Wrap the merge step in `git stash push -u` / `git stash pop` so
   incidental writes don't block rebase.
3. Move the `.clasi.db` write to AFTER the merge step (or do it in a
   sub-process that commits its own change). The DB update is already
   a side effect that won't be undone by a failed merge, so ordering
   it last is safer.
4. Treat `.clasi.db` as either fully gitignored (with a separate
   export format for sharing) or as a proper artifact with explicit
   per-step commit hooks.

## Bonus fix worth tying in

If the merge step fails for any reason, `release_execution_lock`
should still run (or `close_sprint` should expose a recovery flag).
Currently the lock leaks.

## Severity

Low-medium per reporter. Fully recoverable but breaks every
`close_sprint` call and silently leaves the execution lock held.
