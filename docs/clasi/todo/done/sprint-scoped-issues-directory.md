---
status: done
sprint: '015'
tickets:
- 015-015
- 015-016
- 015-017
- 015-018
- 015-019
---

# Sprint-scoped issues directory

## Context

The user is layering one more architectural decision onto the existing TODO at [docs/clasi/todo/move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md](/Users/eric/proj/ai-project/clasi/docs/clasi/todo/move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md): when a sprint takes ownership of an issue, the issue file moves *into the sprint's directory* (under a new `issues/` subdir) instead of into a top-level `.clasi/issues/in-progress/` and later `.clasi/issues/done/`.

This co-locates each sprint's work — its tickets, its architecture update, and now its issues — in a single folder, and removes the parallel top-level lifecycle dirs (`in-progress/`, `done/`). The pending pool stays at top-level `.clasi/issues/`, but the `in-progress/` and `done/` subdirs at that level disappear; a sprint's issues archive *with the sprint* when the sprint moves to `.clasi/sprints/done/`.

This is a TODO update, not an immediate code change. The work itself rolls into the existing `move-docs-clasi-to-dot-clasi` umbrella sprint (or a sibling sprint plan), since both touch the same files (`Project` properties, `Todo`/`Issue` class, hook handlers, MCP tools, tests).

## Locked-in decisions (from AskUserQuestion this turn)

1. **Pending issues** stay at top-level `.clasi/issues/` (no `inbox/` subdir).
2. **In-progress issues** live flat in `<sprint>/issues/`. No nested `in-progress/done/` split inside the sprint — sprint scope is already narrow, status is read from frontmatter.
3. **Multi-sprint issues**: the issue file is **split into two referencing files**, one per sprint. Frontmatter on each part links to the other (`split-from:` / `split-to:`). Expected to be rare.
4. **On sprint close**: the issue file travels with the sprint into `.clasi/sprints/done/<sprint>/issues/`. No top-level done archive.

## New layout

```
.clasi/
  issues/
    *.md                          # pending (unclaimed by any sprint)
  sprints/
    NNN-sprint-name/
      sprint.md
      architecture-update.md
      usecases.md
      tickets/
        *.md
      issues/                     # NEW: issues this sprint is working
        *.md
    done/
      MMM-old-sprint/
        ...
        issues/                   # archived issues, traveled with sprint
          *.md
```

The top-level `.clasi/issues/in-progress/` and `.clasi/issues/done/` directories cease to exist.

## What needs to change in the existing TODO

Open the file `docs/clasi/todo/move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md` and apply these edits.

### 1. Layout diagram (replace existing)

Replace the `.clasi/` layout block under "Subdirectory layout under `.clasi/`" with:

```
.clasi/
  AGENTS.md
  .clasi.db
  clasi-version
  issues/                # pending only
    *.md
  sprints/
    NNN-sprint/
      sprint.md
      tickets/
      issues/            # NEW: issues this sprint is working (flat, no in-progress/done split)
    done/
      MMM-sprint/
        issues/          # archived with the sprint
  architecture/
  log/
  reflections/
```

### 2. Add a new "Locked-in decisions" subsection

Add directly under the directory-layout block:

> - **Issues are sprint-scoped once claimed.** Pending issues live at `.clasi/issues/`. When a sprint claims an issue, the file moves into `<sprint>/issues/` (flat — no nested `in-progress/`). When the sprint closes, the file travels with the sprint into `.clasi/sprints/done/<sprint>/issues/`. There is no top-level `.clasi/issues/in-progress/` or `.clasi/issues/done/`.
> - **Multi-sprint issues are split, not shared.** If sprint A only partially addresses an issue, the work continued by sprint B becomes a *new* issue file with `split-from:` frontmatter pointing back to the original; the original gets `split-to:`. Expected to be rare; the planner should not optimize for it.

### 3. Surface-area updates (append to "Surface area to update" section)

Append a new bullet group:

> **Issue lifecycle (new — combines with the rename TODO)**
>
> - `clasi/todo.py` (renamed `clasi/issue.py`):
>   - `move_to_in_progress(sprint_id, ticket_id)` — destination changes from `<root>/.clasi/issues/in-progress/` to `<sprint>/issues/`. Look up the sprint dir via `Project.get_sprint(sprint_id).path / "issues"`. `mkdir(parents=True, exist_ok=True)` on first move into a sprint.
>   - `move_to_done(sprint_id, ticket_ids)` — no longer moves the file. The file stays in `<sprint>/issues/` and only the frontmatter (`status: done`, `tickets:`) is updated. Rename the method to something like `mark_done` so the name reflects reality, OR keep the name and document that "done" no longer implies a directory move.
>   - New method `split_for_followup(new_filename, sprint_a, sprint_b)` (rare path): copies the current issue body, writes `split-to:` on the original and `split-from:` on the new file, leaves the original in `<sprint-a>/issues/` and the new file in the pending pool at `.clasi/issues/`. Skip if planner judges the use case too rare to warrant a helper.
>
> - `clasi/project.py`:
>   - `Project.get_issue(filename)` (renamed from `get_todo`) must search: pending pool `.clasi/issues/`, then every sprint's `<sprint>/issues/` (active and done). Currently searches `todo_dir`, `todo_dir/in-progress`, `todo_dir/done`.
>   - `Project.list_issues()` (renamed from `list_todos`) — returns pending + every sprint's issues whose `status != done`. The "active" definition becomes "pending OR (in some sprint AND status != done)".
>   - Drop `Project.todo_dir / "in-progress"` and `... / "done"` references throughout.
>
> - `clasi/sprint.py`:
>   - Add `Sprint.issues_dir` property → `self.path / "issues"`.
>   - Add `Sprint.list_issues()` → returns `Issue` objects from `<sprint>/issues/*.md`.
>   - On sprint close, the `issues/` subdir travels with the sprint dir into `done/` (already automatic since the move is at the sprint-dir level — verify, don't add code).
>
> - `clasi/tools/artifact_tools.py`:
>   - `move_issue_to_done(filename, sprint_id, ticket_ids)` — internal logic updates frontmatter only, no file move. Validate that the issue is currently in `<sprint_id>/issues/`.
>   - `list_issues()` MCP tool — docstring and scan paths updated.
>   - `acquire_execution_lock` / sprint claim flow — when a sprint first touches an issue, it triggers the move from pending pool into `<sprint>/issues/`. This already happens via `Issue.move_to_in_progress` from the ticket-creation path; verify call sites.
>
> - `clasi/init_command.py`:
>   - Stop creating `.clasi/issues/in-progress/` and `.clasi/issues/done/`. Just create `.clasi/issues/` (pending pool).
>
> - `clasi/hook_handlers.py`:
>   - Permission paths `.clasi/issues/` (pending) and `.clasi/sprints/<id>/issues/` (sprint-scoped). Tier-1 (programmer) needs write access to its own sprint's `issues/` dir; tier-0 (team-lead) writes pending. Update path globs and tier checks.
>
> - `clasi/templates/sprint.md` (if it lists subdirs) — mention `issues/` as a sibling of `tickets/`.
>
> - Tests:
>   - All test fixtures that create `<root>/issues/in-progress/<file>` need to create `<sprint-dir>/issues/<file>` instead.
>   - `tests/unit/test_todo_lifecycle.py`, `test_todo.py`, `test_todo_tools.py` — restructure setup/assertions for new locations.

### 4. Update "Acceptance criteria"

Add:

> - `<sprint>/issues/` exists in any sprint that has claimed at least one issue; pending issues remain at `.clasi/issues/`.
> - Closing a sprint moves `<sprint>/issues/` into `.clasi/sprints/done/<sprint>/issues/` automatically (covered by the existing sprint-dir move).
> - `list_issues()` returns the union of pending and all in-progress sprint issues, deduplicated and sorted.
> - No `.clasi/issues/in-progress/` or `.clasi/issues/done/` directory is created by `clasi install` or by issue lifecycle transitions.

### 5. Cross-link with sibling TODOs

In the "Coordination with sibling TODOs" section, append:

> - This sprint-scoped issues layout depends on directory-naming decisions in [rename-clasi-todos-to-issues.md](rename-clasi-todos-to-issues.md). Land that rename first, then this layout shift, OR fold both into the umbrella `.clasi/` migration sprint so the test suite churns once.

## Files to read for the planner (reference, not edits)

- [clasi/todo.py](/Users/eric/proj/ai-project/clasi/clasi/todo.py) — current move methods.
- [clasi/project.py:215-238](/Users/eric/proj/ai-project/clasi/clasi/project.py) — current `get_todo` / `list_todos` search paths.
- [clasi/tools/artifact_tools.py:477,624-646](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py) — call sites that drive `move_to_in_progress` and the `move_to_done` cascade on ticket close.
- [clasi/init_command.py:197-205](/Users/eric/proj/ai-project/clasi/clasi/init_command.py) — directory creation at project init.

## Verification (when this work eventually runs)

- Unit: `uv run pytest tests/unit/test_todo*.py tests/unit/test_sprint.py tests/unit/test_init_command.py` — all green after fixture restructuring.
- Integration: spin up a fresh project with `clasi init`; create an issue; create a sprint that claims it; verify the file is at `<sprint>/issues/<filename>` with `status: in-progress`. Close the sprint; verify the file is at `.clasi/sprints/done/<sprint>/issues/<filename>` with `status: done`.
- Smoke: run the existing migration script (from the umbrella TODO) against a copy of this repo's `.clasi/` and confirm in-progress issues land in the right sprint dirs.
