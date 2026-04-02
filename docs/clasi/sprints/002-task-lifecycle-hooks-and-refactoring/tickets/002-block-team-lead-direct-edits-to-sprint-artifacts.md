---
id: '002'
title: Block team-lead direct edits to sprint artifacts
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: block-team-lead-direct-edits-to-sprint-artifacts.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Block team-lead direct edits to sprint artifacts

## Description

Tier 0 (team-lead / interactive session) must use MCP tools to manage sprint
artifacts. Direct file edits to `docs/clasi/sprints/` are now blocked by the
role guard hook, with a clear error message directing the user to MCP tools.

## Acceptance Criteria

- [x] `_handle_role_guard()` blocks tier 0 writes to `docs/clasi/sprints/` with returncode 2 and "ROLE VIOLATION" in stderr
- [x] Tier 0 is still allowed to write to other `docs/clasi/` paths (todo, reflections, etc.)
- [x] Tier 1 and tier 2 are still allowed to write to `docs/clasi/sprints/`
- [x] OOP bypass (`.clasi-oop`) allows tier 0 to write to `docs/clasi/sprints/`
- [x] `.claude/rules/clasi-artifacts.md` documents the restriction
- [x] `clasi/init_command.py` RULES template includes the restriction for new projects
- [x] All tests pass (`uv run pytest`)

## Testing

- **Existing tests to run**: `tests/unit/test_role_guard.py`
- **New tests to write**: `TestRoleGuardTeamLeadSprintBlock` class with 7 test cases
- **Verification command**: `uv run pytest`
