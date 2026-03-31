---
status: in-progress
source: https://github.com/ericbusboom/clasi/issues/11
sprint: '001'
tickets:
- 001-003
---

# Absorb Git Close Operations into the `close_sprint` MCP Tool

## Problem

Sprint closure is split across two actors: the `close_sprint` MCP tool
handles the CLASI state (archive directory, state DB, execution lock,
version bump), while the agent handles the git operations (merge, push,
tag, branch delete). These are separate steps with no enforcement coupling
between them.

This split is the documented cause of a recurring failure mode: multiple
reflections record sprints that were merged and tagged by the agent but
never had `close_sprint` called. The git state and CLASI state diverge.
The sprint appears closed in git (branch merged, tag created) but still
appears active in CLASI (execution lock held, sprint directory in
`sprints/`, state DB phase not `done`).

The inverse also occurs: the agent calls `close_sprint` but then fails
or gets distracted before completing the git steps, leaving the CLASI
state closed but the branch unmerged.

The current `close_sprint` skill has 15 steps. Steps 8–14 are all git
operations that the agent performs manually after calling the MCP tool
at step 10. The skill is long enough that agents skip or reorder steps
under time pressure.

## Desired Behavior

`close_sprint` becomes the single entry point for all sprint closure
operations. One call handles: ticket and TODO verification, test run,
merge, archive, state DB update, version bump, tag, push, and branch
delete. The skill shrinks to: confirm with stakeholder, call
`close_sprint`, report result.

If `close_sprint` fails partway through (merge conflict, test failure,
git error, inconsistent state), it first attempts self-repair. If
self-repair succeeds it continues. If it cannot self-repair, it writes
a recovery record to the state DB and returns a structured error that
identifies exactly which step failed, what state was left, and — for
cases requiring agent intervention — which specific files the agent is
permitted to edit during recovery.

The `PreToolUse` hook checks the state DB for an active recovery record
before blocking file writes. If a recovery record exists for the current
sprint, the hook allows writes to the specific paths listed in the record
and blocks everything else. Once the agent calls `close_sprint` again
successfully (or calls `clear_recovery_state`), the record is removed
and the hook returns to normal restrictive behavior.

This keeps the agent from taking liberties while still allowing targeted
repair of genuinely broken state.

## Proposed Changes

### 1. Extend `close_sprint` to accept git parameters

Add parameters for the information the tool needs to run git operations:

```python
def close_sprint(
    sprint_id: str,
    branch_name: str,           # e.g. "sprint/024-my-feature"
    main_branch: str = "main",  # target branch for merge
    push_tags: bool = True,     # whether to push after tagging
    delete_branch: bool = True, # whether to delete sprint branch after merge
) -> str:
```

`branch_name` is already stored in the sprint frontmatter and the state
DB — the tool can read it from there if not passed explicitly, so it can
remain optional with a fallback.

### 2. Add pre-condition verification to `close_sprint`

Before any git or archive operations, the tool verifies:

1. **Ticket verification**: All tickets in `tickets/` are in `tickets/done/`
   and have `status: done` in frontmatter. Self-repair: if a ticket has
   `status: done` in frontmatter but is still in `tickets/` (not `done/`),
   move it automatically. If frontmatter says not done but the file is in
   `done/`, fix the frontmatter. If genuinely incomplete, return a structured
   error with the list of incomplete tickets — do not proceed.
2. **TODO verification**: All TODOs referencing this sprint are in
   `todo/done/`. Self-repair: move any that are still in `todo/` with
   matching sprint frontmatter. If a TODO is referenced by a ticket but
   has no sprint tag, flag it for agent review.
3. **State DB sync**: DB phase matches filesystem state. Self-repair: if
   DB is behind, advance it to match.
4. **Execution lock**: Lock is held by this sprint. Self-repair: if lock is
   held by a sprint that no longer exists on disk, release and re-acquire.

Self-repairs are recorded in the result JSON under `"repairs": [...]` so
the agent can report what was fixed.

### 3. Add git operations to `close_sprint`

After verification and archive, add:

1. **Pre-merge test run**: `subprocess.run(["uv", "run", "pytest"])`.
   Fails before touching git state if tests fail.
2. **Merge**: `git merge <branch_name>` onto `main_branch`. On conflict,
   write a recovery record and return a structured error — see below.
3. **Push tags**: `git push --tags` if `push_tags=True` and a version tag
   was created.
4. **Delete branch**: `git branch -d <branch_name>` if `delete_branch=True`.

Use `subprocess.run` with `check=False` and inspect return codes explicitly.
Each git step is individually reported in the result JSON.

### 4. Add recovery state to the DB schema

Add a `recovery_state` table:

```sql
CREATE TABLE IF NOT EXISTS recovery_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sprint_id TEXT NOT NULL,
    step TEXT NOT NULL,           -- which step failed
    allowed_paths TEXT NOT NULL,  -- JSON array of paths agent may edit
    reason TEXT NOT NULL,         -- human-readable description
    recorded_at TEXT NOT NULL
);
```

When `close_sprint` encounters an unrecoverable error (e.g., merge
conflict, genuinely incomplete ticket that can't be auto-repaired), it
writes a recovery record with the specific file paths the agent needs to
touch to resolve the issue. It then returns:

```json
{
  "error": {
    "step": "merge",
    "message": "Merge conflict in src/auth.py",
    "recovery": {
      "recorded": true,
      "allowed_paths": ["src/auth.py"],
      "instruction": "Resolve the merge conflict in src/auth.py, then call close_sprint again."
    }
  }
}
```

The `PreToolUse` hook reads `recovery_state` before blocking. If a record
exists and the file being written is in `allowed_paths`, the hook permits
the write. All other paths remain blocked.

Recovery records are cleared by: a successful `close_sprint` call, or an
explicit `clear_recovery_state(sprint_id)` tool call. Add a TTL check: if
the record is older than 24 hours, `close_sprint` logs a warning and clears
it before retrying — stale recovery records from crashed sessions should not
permanently loosen the hook.

### 5. Return structured result

```json
{
  "old_path": "docs/clasi/sprints/024-my-feature",
  "new_path": "docs/clasi/sprints/done/024-my-feature",
  "moved_todos": ["my-todo.md"],
  "repairs": ["moved ticket 003 to done/", "fixed frontmatter on ticket 005"],
  "version": "1.4.0",
  "tag": "v1.4.0",
  "git": {
    "merged": true,
    "merge_target": "main",
    "tags_pushed": true,
    "branch_deleted": true
  }
}
```

### 6. Shorten the `close-sprint` skill

The skill becomes three steps:

1. Confirm with stakeholder (present ticket summary, ask to proceed)
2. Call `close_sprint(sprint_id, branch_name)`
3. Report result — or if error returned, report the specific blocker and
   the recovery instruction from the error payload

The agent never diagnoses state itself. All diagnosis is in the tool return.

### 5. Update team-lead agent definition

The team-lead's sprint lifecycle section currently lists merge, tag, push,
and branch delete as separate steps after `close_sprint`. Replace those with
a single line: "Call `close_sprint` with the sprint ID and branch name. It
handles all git and archiving operations atomically."

## What Does Not Change

- `close_sprint` remains callable without the new git parameters for
  backward compatibility — when `branch_name` is omitted, it falls back
  to the current behavior (archive and state only, no git operations).
  This allows gradual adoption and avoids breaking existing tests.
- The state DB, archive directory move, execution lock release, and version
  bump logic are unchanged.
- The pre-merge stakeholder confirmation remains in the skill, not the tool
  — the tool should not block on user input.

## Open Questions

- **Working directory for git**: `subprocess.run` needs to run git from
  the project root. Confirm that `Path.cwd()` inside the MCP server process
  is always the project root (it is when invoked via `.mcp.json`, but verify
  for edge cases).
- **Merge strategy**: Default `git merge` uses fast-forward when possible.
  Should the tool force `--no-ff` to always create a merge commit? A merge
  commit makes the sprint boundary visible in git log. Worth deciding as a
  project convention.
- **Partial failure recovery**: If the archive succeeds but the merge fails,
  the sprint directory is in `done/` but the branch is unmerged. The recovery
  record mechanism handles this — `close_sprint` writes the allowed paths and
  the agent resolves the conflict. On retry, `close_sprint` detects the sprint
  is already archived and skips that step. Each step should be idempotent.
- **Recovery record and hook dependency**: The recovery state DB check in the
  `PreToolUse` hook means the hook and DB must both be in place for recovery
  to work. If the hook is not installed (older project, pre-init), recovery
  still works but without file-scope restriction. Document this as a reason
  to keep `clasi init` up to date.
- **`clear_recovery_state` authorization**: Only `close_sprint` success or
  an explicit tool call should clear recovery state. The agent cannot clear
  it by any other means — the clear must go through the MCP tool.
