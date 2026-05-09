---
id: '015'
title: CLASI artifact layout migration to .clasi/
status: done
branch: sprint/015-clasi-artifact-layout-migration-to-clasi
use-cases:
- SUC-001
- SUC-002
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 015: CLASI artifact layout migration to .clasi/

## Goals

1. Relocate the CLASI artifact root from `docs/clasi/` to `.clasi/` — a hidden
   top-level directory consistent with `.git/`, `.vscode/`, `.github/` conventions.
2. Rename the "TODO" concept to "issue" throughout the codebase (directory name,
   class name, MCP tool names, CLI subcommands, skill name, frontmatter fields).
3. Introduce sprint-scoped issue lifecycle: issues claimed by a sprint travel into
   `<sprint>/issues/` and archive with the sprint on close.
4. Consolidate the version marker into a single `.clasi/clasi-version` file per
   target project.
5. Add a `clasi migrate` subcommand for one-shot migration of existing projects.

## Problem

`docs/clasi/` mixes CLASI process artifacts (sprints, issues, architecture, logs)
with user-authored project documentation in `docs/`, which is confusing and pollutes
the `docs/` tree for projects that publish a documentation site.

The term "TODO" also collides with the Python developer convention (`# TODO:` comment
markers) and with GitHub Issues. Renaming to "issue" aligns with the GitHub vocabulary
and eliminates the collision.

Issues that are in-progress currently move to a global `issues/in-progress/` directory,
severing them from the sprint context that claimed them. Sprint-scoped storage keeps
the sprint's issues co-located with its tickets and architecture for a cleaner archive.

## Solution

- Change `Project.clasi_dir` to return `self._root / ".clasi"`. All derived path
  properties inherit automatically.
- Hard rename `Todo` → `Issue`, `todo.py` → `issue.py`, `plan_to_todo.py` → `plan_to_issue.py`.
- Update ticket frontmatter fields `todo:` → `issue:` and `completes_todo:` → `completes_issue:`.
- Change status enum value `todo` → `open` (tickets start as `open`, not `todo`).
- Sprint-scoped issues: `move_to_in_progress` writes to `<sprint>/issues/`; `move_to_done`
  is frontmatter-only; the sprint archive carries `<sprint>/issues/` to done automatically.
- Consolidate `write_version_stamp` to a single `.clasi/clasi-version` write per install.
- Add `clasi migrate` subcommand for existing projects.
- No backward-compat shims — hard cut.

Self-migration of this source repo (`git mv docs/clasi .clasi`) is deliberately deferred
to a clean session after the sprint closes, so the code is not running against old paths
during development.

## Success Criteria

- `grep -rn "docs/clasi" clasi/ tests/ .claude/ .github/ AGENTS.md README.md` returns
  zero hits (historical references inside done sprints are exempt).
- `grep -rn "\btodo\b" clasi/ tests/` returns zero references to the CLASI artifact
  concept (Python `# TODO:` comments and unrelated usages may remain).
- `clasi install` on a fresh target creates `.clasi/` (not `docs/clasi/`).
- Full test suite passes.
- `clasi migrate` relocates a project from `docs/clasi/` to `.clasi/` cleanly.
- README has a clearly-headed "Issues vs Tickets" section.
- All MCP tools, CLI subcommands, and skills work under their new names.

## Scope

### In Scope

- `Project.clasi_dir` path change and all derived path properties.
- `Todo` → `Issue` class rename (`todo.py` → `issue.py`).
- `plan_to_todo.py` → `plan_to_issue.py`.
- Ticket frontmatter fields: `todo:` → `issue:`, `completes_todo:` → `completes_issue:`.
- Status enum value: `todo` → `open`.
- CLI subcommand `plan-to-todo` → `plan-to-issue`; option `--todo-dir` → `--issues-dir`.
- Hook handler keys: `plan-to-todo`, `codex-plan-to-todo` → `plan-to-issue`, `codex-plan-to-issue`.
- Platform installer path references (globs, AGENTS.md body, rule body text).
- Init command: creates `.clasi/issues/` (no `in-progress/`, no `done/` at root level).
- Version marker consolidation: single `.clasi/clasi-version` per install.
- Sprint-scoped issue lifecycle: `move_to_in_progress`, `move_to_done` semantics, `Sprint.issues_dir`.
- Skill rename `/todo` → `/issue`.
- Agent prompts, README, and SE-overview template updates.
- All test fixtures updated for new paths and class names.
- MCP tool rename: `list_todos` → `list_issues`, `move_todo_to_done` → `move_issue_to_done` (last ticket).
- `clasi migrate` subcommand.

### Out of Scope

- Self-migration of `docs/clasi/` → `.clasi/` in this source repo (deferred post-sprint).
- Backward-compat shims or deprecated aliases.
- Touching historical ticket bodies inside done sprints.
- Any clasr-related changes (sprint 014 scope).
- Schema-driven workflow, integration registry, delta specs (separate TODOs).
- Acquiring execution lock (team-lead does that when ready to execute).

## Test Strategy

- Unit tests for each renamed module and changed path constant.
- Integration test: `clasi install` on a temp dir → `clasi` creates `.clasi/` layout correctly.
- Integration test for issue lifecycle: create issue → claim via sprint → verify file at
  `<sprint>/issues/<file>` → close sprint → verify file at
  `docs/clasi/sprints/done/<sprint>/issues/<file>`.
- `clasi migrate` smoke test against a copy of this repo's `docs/clasi/` tree.
- All existing `tests/unit/` and `tests/system/` tests must remain green.

## Architecture Notes

- `Project` is the single path arbiter. Hook handlers, platform installers, and the CLI
  all resolve paths via `Project` properties — no hardcoded `"docs/clasi"` strings.
- Dependency direction: `issue.py` does not import `sprint.py`; sprint dir is resolved
  by the caller (MCP tool or `artifact_tools.py`) via `Project.get_sprint(sprint_id)`.
- MCP tool rename is the last ticket (028) to avoid breaking the running MCP server
  mid-sprint.

## TODO References

- `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md` — umbrella migration
- `rename-clasi-todos-to-issues.md` — vocabulary rename
- `sprint-scoped-issues-directory.md` — issue lifecycle change
- `consolidate-the-clasi-version-marker-into-clasi-clasi-version.md` — version marker

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Rename status enum value `todo` → `open` | — |
| 002 | Rename ticket frontmatter fields `todo:` → `issue:` and `completes_todo:` → `completes_issue:` | 001 |
| 003 | Rename `clasi/todo.py` → `clasi/issue.py`; class `Todo` → `Issue` | 002 |
| 004 | Rename `clasi/plan_to_todo.py` → `clasi/plan_to_issue.py` | 003 |
| 005 | Update `Project` methods: `get_todo` → `get_issue`, `list_todos` → `list_issues`, `todo_dir` → `issues_dir` | 003 |
| 006 | `Project.clasi_dir` returns `.clasi/`; correct `design_dir` | 005 |
| 007 | Update `StateDB` path construction for new `clasi_dir` | 006 |
| 008 | Hook handlers: replace hardcoded `docs/clasi` path strings with Project properties | 006, 005 |
| 009 | `platforms/claude.py`: update path globs and rule frontmatter for new paths | 006 |
| 010 | `platforms/codex.py`: update path strings and AGENTS.md body content | 006 |
| 011 | `platforms/copilot.py`: update instruction path globs | 006 |
| 012 | `platforms/_rules.py`: update rule body text references to old paths | 006 |
| 013 | CLI: rename `plan-to-todo` → `plan-to-issue`; `--todo-dir` → `--issues-dir` | 004 |
| 014 | Rename skill `/todo` → `/issue` | 013 |
| 015 | `init_command.py`: create `.clasi/issues/` (no in-progress/done subdirs) | 006, 005 |
| 016 | `Issue.move_to_in_progress` writes to `<sprint>/issues/` | 006, 003 |
| 017 | `Issue.move_to_done` becomes frontmatter-only (no file move) | 016 |
| 018 | Add `Sprint.issues_dir` property and `Sprint.list_issues()`; update `Sprint.archive()` | 017 |
| 019 | `Project.list_issues()`: scan only `.clasi/issues/` (no subdirectory scanning) | 018 |
| 020 | Consolidate `write_version_stamp` to `.clasi/clasi-version`; update platform installers | 006 |
| 021 | Add `clasi migrate` subcommand | 015, 006 |
| 022 | Re-render rule body content and `se-overview-template.md` for new paths | 012 |
| 023 | Update `README.md`: add Issues vs Tickets section; remove `docs/clasi/` references | 022 |
| 024 | Update agent prompt files in `clasi/plugin/agents/` | 014, 022 |
| 025 | Update `tests/unit/test_hook_handlers.py` fixtures | 008 |
| 026 | Update platform test fixtures (`test_platform_claude.py`, `test_platform_codex.py`, `test_platform_copilot.py`) | 009, 010, 011, 020 |
| 027 | Rename and update remaining unit test files; add sprint-scoped issue lifecycle tests | 016, 017, 018, 019, 025, 026 |
| 028 | Rename MCP tools `list_todos`/`move_todo_to_done` → `list_issues`/`move_issue_to_done` | 019, 027 |

Tickets execute serially in the order listed.
