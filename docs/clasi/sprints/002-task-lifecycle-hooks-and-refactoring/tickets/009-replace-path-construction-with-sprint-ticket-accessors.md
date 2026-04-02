---
id: 009
title: Replace path construction with sprint/ticket accessors
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: replace-path-construction-with-sprint-ticket-accessors.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Replace path construction with sprint/ticket accessors

## Description

Audited all code that uses Sprint and Ticket objects to ensure no paths are
constructed manually via string concatenation or `sprint.path / "filename"`.
Added dedicated property accessors on the Sprint class for all well-known files
and replaced all manual path constructions in callers with the new accessors.

## Acceptance Criteria

- [x] Sprint class has `sprint_md`, `usecases_md`, `architecture_update_md`, `tickets_dir`, `tickets_done_dir` path properties
- [x] All manual `sprint.path / "filename"` constructions in `artifact_tools.py` replaced with accessors
- [x] All manual `self._path / "tickets"` constructions in `sprint.py` replaced with `self.tickets_dir` / `self.tickets_done_dir`
- [x] `project.py` `create_sprint` uses Sprint path accessors after creating the Sprint object
- [x] All existing tests still pass (812 passed)
- [x] New tests for path accessors written in `test_sprint.py`

## Testing

- **Existing tests to run**: `uv run pytest` — 812 passed
- **New tests to write**: `TestSprintPathAccessors` in `tests/unit/test_sprint.py` — 9 new tests
- **Verification command**: `uv run pytest`
