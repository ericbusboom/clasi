---
status: done
sprint: '001'
tickets:
- 001-001
- 001-002
- 001-003
- 001-004
---

# Plan: Sprint-Scoped Issue Lifecycle (`<sprint>/issues/done/` + Split + Close Gate)

## Context

Most of the desired behavior already exists but is incomplete and inconsistent:

- **Already works:** When `create_ticket(sprint_id, ..., todo=<issue_filename>)` is called, `Issue.move_to_in_progress()` physically moves the issue file from `.clasi/issues/` into `<sprint>/issues/` and sets `status: in-progress` ([clasi/issue.py:67-84](/Users/eric/proj/ai-project/clasi/clasi/issue.py#L67-L84), called from [clasi/tools/artifact_tools.py:493-501](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L493-L501)).
- **Already works:** When `move_ticket_to_done` runs and all tickets referencing an issue are done (and none have `completes_issue: false`), it auto-calls `Issue.move_to_done()` ([clasi/tools/artifact_tools.py:719-742](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L719-L742)).
- **Already works:** `close_sprint`'s precondition pass hard-fails when an in-sprint issue is still `in-progress` and not deferred ([clasi/tools/artifact_tools.py:971-1010](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L971-L1010)).
- **Broken / missing:**
  1. `Issue.move_to_done()` only flips frontmatter; it does **not** move the file into a `done/` subdirectory ([clasi/issue.py:86-105](/Users/eric/proj/ai-project/clasi/clasi/issue.py#L86-L105)). The close-sprint self-repair log message even claims `"moved TODO ... to done/"` ([artifact_tools.py:983](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L983)), which is a lie — nothing moves.
  2. There is no way to split an issue when only part of it will be tackled in a sprint.
  3. Sprint, Issue, and skill docs don't describe the sprint-scoped issue lifecycle; users can't tell whether `.clasi/issues/` or `<sprint>/issues/` is canonical.

This change finishes the symmetry with tickets: issues physically relocate into `<sprint>/issues/` on activation and into `<sprint>/issues/done/` on completion, splitting is a first-class operation, and the close gate enforces that every in-sprint issue is in `done/`.

## Changes

### 1. Add `issues_done_dir` property and update lookups — [clasi/sprint.py](/Users/eric/proj/ai-project/clasi/clasi/sprint.py)

- Add a property `issues_done_dir` returning `self._path / "issues" / "done"` (mirrors `tickets_done_dir` at [sprint.py:138-141](/Users/eric/proj/ai-project/clasi/clasi/sprint.py#L138-L141)).
- Update `list_issues` ([sprint.py:168-182](/Users/eric/proj/ai-project/clasi/clasi/sprint.py#L168-L182)) to scan both `issues_dir` and `issues_done_dir`, mirroring `list_tickets` ([sprint.py:157-166](/Users/eric/proj/ai-project/clasi/clasi/sprint.py#L157-L166)).
- No need to change `Project.get_issue` — it already iterates sprints and resolves `<sprint>/issues/<filename>`. Update it to also try `<sprint>/issues/done/<filename>` ([project.py:211-231](/Users/eric/proj/ai-project/clasi/clasi/project.py#L211-L231)).

### 2. Make `Issue.move_to_done()` actually relocate the file — [clasi/issue.py](/Users/eric/proj/ai-project/clasi/clasi/issue.py)

Rewrite `Issue.move_to_done` ([issue.py:86-105](/Users/eric/proj/ai-project/clasi/clasi/issue.py#L86-L105)) modeled on `Ticket.move_to_done` ([ticket.py:127-141](/Users/eric/proj/ai-project/clasi/clasi/ticket.py#L127-L141)):

- If the issue's parent dir name is `done`, treat as already-done (idempotent).
- Otherwise compute `done_dir = self.path.parent / "done"`, `mkdir(parents=True, exist_ok=True)`, rename the file in, and reattach `self._artifact = Artifact(new_path)`.
- Continue updating frontmatter (`status="done"`, optionally `sprint`, optionally `tickets`).
- Update the docstring to drop the line about staying in place until sprint archive.

This makes the existing auto-complete inside `move_ticket_to_done` ([artifact_tools.py:739](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L739)) and the explicit `move_issue_to_done` MCP tool ([artifact_tools.py:1488-1533](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L1488-L1533)) do the right thing without any change to their bodies.

### 3. Update close-sprint precondition self-repair — [clasi/tools/artifact_tools.py](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py)

In `_close_sprint_full` (precondition step 1b, [artifact_tools.py:971-1020](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L971-L1020)) and `_close_sprint_legacy` ([artifact_tools.py:820-...](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L820)):

- The existing `todo.move_to_done()` call at line 982 now becomes the self-repair migration step automatically (since `move_to_done` will now physically move). No code change required there, but verify the `repairs.append(...)` message at line 983 is now accurate.
- Extend the scan to also walk `<sprint>/issues/done/` — issues already in `done/` should pass cleanly without warning.
- Pending-pool issues with `sprint == sprint_id` and `status == "done"` ([artifact_tools.py:1011-1020](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L1011-L1020)): these were never moved into the sprint (legacy). Self-repair by relocating into `<sprint>/issues/done/` directly. Today the code just calls `move_to_done()` on an issue still in the pending pool, which produces a misleading repair message.

### 4. Add `split_issue` MCP tool — [clasi/tools/artifact_tools.py](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py)

New tool exposed by the MCP server:

```
split_issue(
    filename: str,                  # original issue
    new_filename: str,              # filename for the split-off issue
    new_title: str,
    new_body: str,                  # body content for the split-off issue
    updated_body: str | None = None # optional rewrite of the original body
) -> JSON {original_path, new_path}
```

Behavior:
- Resolve `filename` via `project.get_issue` (works in pending pool, sprint-scoped, or sprint-scoped-done).
- Create the new file as a sibling **in the same directory as the original** (so splitting a sprint-scoped issue produces another sprint-scoped issue under the same sprint; splitting a pending-pool issue stays in the pool).
- Copy frontmatter `source`, inherit any `sprint`/`status`/`tickets` from the original only if the original is sprint-scoped and `in-progress` — otherwise the new issue starts `status: pending` in the pool.
- Add cross-link frontmatter: `split_from: <original-filename>` on the new, append `split_into: [<new-filename>, ...]` on the original.
- If `updated_body` is provided, rewrite the original's body content.
- Do not touch tickets; the planner re-runs `create_ticket(todo=<new-filename>)` if they want the new piece in the sprint.

Place it near `move_issue_to_done` in [artifact_tools.py](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py). Register via the standard `@server.tool()` decorator pattern already used in that file.

Reuse:
- `project.get_issue` for resolution.
- `Artifact` class (already imported) for frontmatter+body writes — same pattern used inside `Issue.move_to_in_progress` ([issue.py:74-77](/Users/eric/proj/ai-project/clasi/clasi/issue.py#L74-L77)).

### 5. Update the `issue` skill — [clasi/plugin/skills/issue/](/Users/eric/proj/ai-project/clasi/clasi/plugin/skills/issue/)

Add a short section on splitting that points at the new MCP tool and explains when it's needed (planner discovers only part of an issue is in scope for this sprint).

### 6. Update sprint-planning instructions

- [.claude/skills/plan-sprint/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/plan-sprint/SKILL.md) Phase 2 / detail step: after the planner selects which issues are in scope, instruct them to call `split_issue` for partial-scope issues before tickets are created.
- [.claude/skills/create-tickets/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/create-tickets/SKILL.md): note that `create_ticket(todo=...)` is what moves issues into `<sprint>/issues/`, and that issues land in `<sprint>/issues/done/` automatically when their tickets complete. No manual move call needed in the happy path.
- [.claude/skills/close-sprint/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/close-sprint/SKILL.md): note that close will hard-fail if any `<sprint>/issues/*.md` (top-level) remains, and describe the split/done options for resolving such cases.

### 7. Tests — [tests/unit/](/Users/eric/proj/ai-project/clasi/tests/unit/)

- [test_issue.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_issue.py) — extend `TestIssueMoveToOneDone` (per Explore agent's report at lines 115-160+): assert `move_to_done` now relocates to `<sprint>/issues/done/<filename>` and is idempotent if already in `done/`.
- [test_issue_lifecycle.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_issue_lifecycle.py) — extend the create_ticket → move_ticket_to_done flow: after the last ticket is done, the issue file lives under `<sprint>/issues/done/`.
- New `test_split_issue` (or section in test_issue_tools.py): cover splitting from the pending pool, from `<sprint>/issues/`, frontmatter cross-links, and that the new file appears in the right dir.
- Extend close-sprint precondition tests: (a) legacy in-sprint top-level done file is migrated by self-repair; (b) close fails if a sprint-scoped issue is still `in-progress` at top level; (c) issues already in `done/` pass cleanly.

## Critical files to modify

- [clasi/issue.py](/Users/eric/proj/ai-project/clasi/clasi/issue.py) — rewrite `move_to_done`.
- [clasi/sprint.py](/Users/eric/proj/ai-project/clasi/clasi/sprint.py) — add `issues_done_dir`, extend `list_issues`.
- [clasi/project.py](/Users/eric/proj/ai-project/clasi/clasi/project.py) — extend `get_issue` to look in `<sprint>/issues/done/`.
- [clasi/tools/artifact_tools.py](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py) — add `split_issue`; update close-sprint precondition pass for `done/` awareness and pending-pool relocation.
- [clasi/plugin/skills/issue/SKILL.md](/Users/eric/proj/ai-project/clasi/clasi/plugin/skills/issue/SKILL.md) — split-issue guidance.
- [.claude/skills/plan-sprint/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/plan-sprint/SKILL.md), [.claude/skills/create-tickets/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/create-tickets/SKILL.md), [.claude/skills/close-sprint/SKILL.md](/Users/eric/proj/ai-project/clasi/.claude/skills/close-sprint/SKILL.md) — workflow updates.
- [tests/unit/test_issue.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_issue.py), [tests/unit/test_issue_lifecycle.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_issue_lifecycle.py), [tests/unit/test_issue_tools.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_issue_tools.py), [tests/unit/test_artifact_tools.py](/Users/eric/proj/ai-project/clasi/tests/unit/test_artifact_tools.py).

## Existing functions / patterns to reuse

- [Ticket.move_to_done](/Users/eric/proj/ai-project/clasi/clasi/ticket.py#L127-L141) — exact template for `Issue.move_to_done` (parent-dir check → mkdir → rename → reattach Artifact).
- [Sprint.tickets_done_dir](/Users/eric/proj/ai-project/clasi/clasi/sprint.py#L138-L141) and [Sprint.list_tickets](/Users/eric/proj/ai-project/clasi/clasi/sprint.py#L150-L166) — template for the new `issues_done_dir` property and the updated `list_issues`.
- [Issue.move_to_in_progress](/Users/eric/proj/ai-project/clasi/clasi/issue.py#L67-L84) — pattern for frontmatter write + file rename for `split_issue`.
- [_todo_is_deferred](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L123-L153) — already implements the "issue spans sprints" escape hatch; do not change.

## Recovery / phase-DB

No changes required. The precondition pass already records recovery state when it hard-fails on an in-progress issue ([artifact_tools.py:992-996](/Users/eric/proj/ai-project/clasi/clasi/tools/artifact_tools.py#L992-L996)); that path still fires correctly when the file is at the top level of `<sprint>/issues/`.

## Verification

1. Unit tests: `pytest tests/unit/test_issue.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_artifact_tools.py -x`.
2. Full suite: `pytest -x`.
3. Manual: create a fresh sprint with `create_sprint`, drop two issues in `.clasi/issues/`, call `create_ticket` for each, complete tickets via `move_ticket_to_done`, then call `close_sprint`. Expected: both issues end up in `<sprint>/issues/done/`, close succeeds.
4. Manual split: create an issue, call `split_issue` MCP tool to break off a piece, verify the new file appears alongside the original and frontmatter cross-links point both ways.
5. Manual legacy-migration: simulate the pre-change state by writing a `status: done` issue at the top of `<sprint>/issues/`, then call `close_sprint`; verify self-repair moves it into `done/` and close succeeds.
6. `clasi version bump` after substantive commits per [.claude/rules/git-commits.md](/Users/eric/proj/ai-project/clasi/.claude/rules/git-commits.md).
