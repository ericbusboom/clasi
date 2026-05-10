---
id: "004"
title: "Implement Sprint.detail_promote() method"
status: todo
use-cases:
  - SUC-002
  - SUC-004
depends-on:
  - 017-001
  - 017-003
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement Sprint.detail_promote() method

## Description

`clasi/sprint.py` gains a new method `Sprint.detail_promote()`. This is the
domain-layer implementation of the roadmap-to-detail promotion. The MCP tool
`detail_sprint` (ticket 005) will delegate entirely to this method.

The method follows the same pattern as `Sprint.archive()`: it acts on the
sprint's own artifacts and calls `self.advance_phase()` to update the state DB.

**Files to modify:**
- `clasi/sprint.py`: add `detail_promote()` method to the `Sprint` class.

## Acceptance Criteria

- [ ] `Sprint.detail_promote()` raises `ValueError` if the sprint's current phase is not `roadmap`.
- [ ] `Sprint.detail_promote()` raises `ValueError` if `usecases.md` already exists (idempotency guard).
- [ ] On success, `usecases.md` is written from `SPRINT_USECASES_TEMPLATE`.
- [ ] On success, `architecture-update.md` is written from `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`.
- [ ] On success, `tickets/` and `tickets/done/` directories are created.
- [ ] `self.advance_phase()` is called, moving state DB from `roadmap` to `planning-docs`.
- [ ] The method returns a dict: `{"sprint_id": ..., "phase": "planning-docs", "files_written": [...]}`.
- [ ] `uv run pytest` passes with no regressions.

## Implementation Plan

- Add `detail_promote(self) -> dict` to `Sprint` in `clasi/sprint.py`:
  1. Check `self.phase == "roadmap"`; raise `ValueError` with message "Sprint {id} is not in roadmap phase (current: {phase})" if not.
  2. Check `self.usecases_md.exists()`; raise `ValueError` with message "Sprint {id} is already detail-planned (usecases.md exists)" if true.
  3. Read sprint frontmatter for `id`, `title`, `slug` to pass as template format args.
  4. Write `usecases.md` from `SPRINT_USECASES_TEMPLATE.format(id=..., title=..., slug=...)`.
  5. Write `architecture-update.md` from `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE.format(...)`.
  6. `self.tickets_dir.mkdir(parents=True, exist_ok=True)`.
  7. `self.tickets_done_dir.mkdir(exist_ok=True)`.
  8. `self.advance_phase()`.
  9. Return dict with sprint_id, phase, files_written list.
- Import `SPRINT_USECASES_TEMPLATE` and `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE` at top of file (already imported in current sprint.py; verify).

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_sprint.py`, `uv run pytest`
- **New tests to write**: Covered in ticket 009.
- **Verification command**: `uv run pytest`
