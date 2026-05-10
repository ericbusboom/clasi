---
id: "003"
title: "Modify create_sprint to write only sprint.md and register sprint at roadmap phase"
status: todo
use-cases:
  - SUC-001
  - SUC-004
depends-on:
  - 017-001
  - 017-002
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Modify create_sprint to write only sprint.md and register sprint at roadmap phase

## Description

`Project.create_sprint()` in `clasi/project.py` currently writes three files
(`sprint.md`, `usecases.md`, `architecture-update.md`) and creates `tickets/`
and `tickets/done/` directories. This ticket removes all writes except
`sprint.md` and removes the directory creation.

The method still registers the sprint in the state DB via the existing
`register_sprint` call. Since ticket 001 updated the DB default to `roadmap`,
registration now enters at `roadmap` automatically — no explicit phase
argument needed.

Additionally, the `create_sprint` MCP tool in `clasi/tools/artifact_tools.py`
may import or use `SPRINT_USECASES_TEMPLATE` and `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`.
Remove those imports/uses if present.

**Files to modify:**
- `clasi/project.py`: strip `usecases_md`, `architecture_update_md`, and
  directory-creation lines from `create_sprint()`.
- `clasi/tools/artifact_tools.py`: remove unused template imports if present.

## Acceptance Criteria

- [ ] After `create_sprint(title=...)`, the sprint directory contains only `sprint.md`.
- [ ] No `usecases.md` exists after `create_sprint`.
- [ ] No `architecture-update.md` exists after `create_sprint`.
- [ ] No `tickets/` directory exists after `create_sprint`.
- [ ] `get_sprint_phase(sprint_id)` returns `{"phase": "roadmap"}` for the new sprint.
- [ ] `uv run pytest` passes with no regressions.

## Implementation Plan

- Edit `clasi/project.py` `create_sprint()`:
  1. Remove `SPRINT_USECASES_TEMPLATE` and `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` from the import.
  2. Remove `sprint.tickets_dir.mkdir()` and `sprint.tickets_done_dir.mkdir()` lines.
  3. Remove `sprint.usecases_md.write_text(...)` line.
  4. Remove `sprint.architecture_update_md.write_text(...)` line.
- Check `clasi/tools/artifact_tools.py` for corresponding unused imports and remove them.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_project.py`, `uv run pytest`
- **New tests to write**: Covered in ticket 009 (`test_create_sprint_writes_only_sprint_md`).
- **Verification command**: `uv run pytest`
