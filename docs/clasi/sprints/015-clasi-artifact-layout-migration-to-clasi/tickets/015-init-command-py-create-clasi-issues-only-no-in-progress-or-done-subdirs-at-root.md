---
id: '015'
title: '`init_command.py`: create `.clasi/issues/` only (no `in-progress/` or `done/`
  subdirs at root)'
status: todo
use-cases:
  - SUC-001
  - SUC-002
depends-on:
  - "006"
  - "005"
github-issue: ''
todo:
- move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
- sprint-scoped-issues-directory.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `init_command.py`: create `.clasi/issues/` only (no `in-progress/` or `done/` subdirs at root)

## Description

Update `clasi/init_command.py` to create the new layout on `clasi init`:
- Create `.clasi/issues/` (pending pool, with a `.gitkeep`)
- Create `.clasi/log/`, `.clasi/sprints/`, `.clasi/architecture/`, `.clasi/reflections/`
- Do NOT create `.clasi/issues/in-progress/` or `.clasi/issues/done/`
- Remove creation of `docs/clasi/todo/`, `todo/in-progress/`, `todo/done/`
- Update any echo/print statements that mention old paths

## Acceptance Criteria

- [ ] `clasi init` creates `.clasi/issues/` (pending pool) — no in-progress or done subdirs
- [ ] `clasi init` creates `.clasi/log/`, `.clasi/sprints/`, `.clasi/architecture/`,
  `.clasi/reflections/`
- [ ] No `docs/clasi/` directories are created
- [ ] `tests/unit/test_init_command.py` assertions updated for new layout
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/init_command.py` — directory creation block and echo statements

### Testing plan
- `uv run pytest tests/unit/test_init_command.py`
- Integration: `clasi init` in a temp dir; verify `.clasi/` structure
- `uv run pytest` — full suite
