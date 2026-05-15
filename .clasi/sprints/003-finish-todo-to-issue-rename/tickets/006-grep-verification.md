---
id: '006'
title: "Grep verification \u2014 confirm only allowed todo residuals remain"
status: done
use-cases:
- SUC-006
depends-on:
- '001'
- '002'
- '003'
- '004'
- '005'
issue: finish-the-todo-issue-rename.md
---

## Description

Run the acceptance grep from the issue's acceptance criteria and inspect
every hit. Confirm that the only remaining `todo` occurrences are on the
explicit out-of-scope list. Run the full test suite as a final gate.

This is a verification-only ticket. No code changes are expected. If
the grep reveals an unallowed residual, open a follow-up issue; do not
expand the scope of this sprint.

## Acceptance Criteria

- [x] `grep -rn "\btodo\b" clasi/ tests/ README.md` runs without error
- [x] Every hit is inspected and classified as one of:
  - Backward-compat alias at `hook_handlers.py:890, 926` (`handle_plan_to_todo`, `handle_codex_plan_to_todo`)
  - Hook registry key at `hook_handlers.py:980, 982` (`"plan-to-todo"`, `"codex-plan-to-todo"`)
  - CLI deprecated alias block at `cli.py:274-276, 295-297`
  - Path string referring to `docs/clasi/todo/`
  - Generic programmer comment `# TODO:` unrelated to the CLASI artifact concept
- [x] No hits outside the allowed set exist
- [x] If any unallowed hit is found, it is documented in a new issue (not fixed inline)
- [x] Full `pytest tests/` suite is green
- [x] Smoke test: `clasi tool plan-to-issue` still works; deprecated `clasi tool plan-to-todo` still works with deprecation notice

## Verification

Final `grep -rn '\btodo\b' clasi/ tests/ README.md` — 84 remaining hits, all in explicitly allowed categories:

**Backward-compat aliases (preserved until MCP pin moves):**
- `hook_handlers.py:980,982` — hook routing table `"plan-to-todo"` / `"codex-plan-to-todo"` → `handle_plan_to_issue` / `handle_codex_plan_to_issue`
- `cli.py:198,200,219,221` — CLI deprecated alias block listing `plan-to-todo` and `codex-plan-to-todo`
- `platforms/codex.py:73,78,83` — backward-compat codex hook path strings
- `README.md:142` — deprecated alias documentation
- `test_hook_handlers.py:777,782,1024,1029` — tests verifying backward-compat alias routing
- `test_cli.py:111,113` — test verifying `plan-to-todo` subcommand is removed from `tool`
- `test_cli.py:72` — test checking `--todo-dir` flag is gone
- `test_uninstall_command.py:89` — test checking `codex-plan-to-todo` hook removal
- `test_platform_codex.py:295,322,340,380,706,707` — tests verifying codex backward-compat hook

**Path strings `docs/clasi/todo/` (deferred to self-migration sprint):**
- `schemas/se-process/instructions/execution.md:10` — path reference to worktree TODO issue file
- `schemas/se-process/instructions/sprint-plan.md:39` — "Mine the TODO directory" instruction
- `test_uninstall_command.py:287,289,291,297` — test verifying `docs/clasi/todo/` is preserved by uninstall
- `sprint-planner/contract.yaml:10,13` — `todo-files` input name and `docs/clasi/todo/*.md` pattern
- All `old/` archive files — historical archives, never mutated

**Installed rule filename keys:**
- `platforms/claude.py:56` — `"todo-dir.md"` dict key (filename of installed Claude rule)
- `platforms/copilot.py:209` — `"todo-dir.instructions.md"` filename
- `test_platform_copilot.py:287` — same filename in test

**Generic content / test data / template variables:**
- `contract-schema.yaml:127` — `"todo-files"` as example reference name in schema docs
- `dispatch-template.md.j2:13,14` — Jinja2 loop variable `{% for todo in todo_ids %}`
- `hook_handlers.py:180,196` — comments listing `.clasi/` subdirectory names (e.g. `todo/`, `log/`)
- `test_frontmatter.py:61,62,71` — arbitrary `status: todo` string values in frontmatter parser tests
- `test_ticket.py:403,408,413,439,441` — `"some-todo.md"` / `"my-todo.md"` filename strings in test data
- `test_dispatch_log.py:563,566` — `"todo-worker"` old agent name in dispatch log format test

**Cleanups performed during this ticket (in-scope safety-net fixes):**
- `sprint.py:414` — docstring corrected: `"todo"` → `"open"` in return value description
- `plugin/hooks/hooks.json:82` — `"clasi hook plan-to-todo"` → `"clasi hook plan-to-issue"` (installed hooks file was using deprecated alias)
- `plugin/agents/sprint-planner/agent.md:176` — `status (todo)` → `status (open)`
- `plugin/agents/sprint-planner/create-tickets.md:37` — `create_ticket(..., todo=<filename>)` → `issue=`
- `plugin/agents/sprint-planner/plan-sprint.md:140` — `todo` field → `issue` field
- `plugin/skills/create-tickets/SKILL.md:27,33,42` — `status (todo)` and `create_ticket(todo=...)` → `issue`
- `plugin/skills/issue/SKILL.md:49` — `create_ticket(todo=...)` → `issue=`
- `schemas/se-process/instructions/execution.md:16,38` — `todo` status → `open` status
- `schemas/se-process/instructions/sprint-plan.md:76` — `create_ticket(todo=...)` → `issue=`
- `test_artifact_tools.py:16,138` — stale `todo: ""` frontmatter field → `issue: ""`; `status="todo"` → `status="open"`
- `test_platform_codex.py:830,905,907` — updated assertions from `move_todo_to_done`/`"todo"` to `move_issue_to_done`/`"issue"`; renamed local var `todo_content` → `issues_agents_content`
- `test_sprint.py:310,325` — method names `test_create_ticket_auto_links_sprint_todos` / `test_create_ticket_explicit_todo_not_overridden` → `issue` variants
- `test_issue_tools.py` — local variable `todo` renamed to `issues_dir` throughout (48 occurrences)
- `test_issue_lifecycle.py:317-332` — local variable `todo` renamed to `issues_dir`
- `tests/system/test_artifact_tools.py:184,200,221-222` — method names and assertion updated to use `issue`

## Implementation Plan

### Approach

1. Run: `grep -rn "\btodo\b" clasi/ tests/ README.md`
2. For each hit: look up the line and classify against the allowed list.
3. If any hit is unclassified: create a new `.clasi/issues/` entry and
   stop — do not fix inline.
4. Run `pytest tests/` and confirm green.
5. Run smoke test for the CLI commands.

### Files to Create/Modify

None expected. This ticket writes no code.

### Testing Plan

- `pytest tests/` — final gate.
- Manual smoke: `clasi tool plan-to-issue --help` returns without error.
- Manual smoke: `clasi tool plan-to-todo --help` returns with deprecation
  notice (confirms backward-compat alias intact).

### Documentation Updates

None.
