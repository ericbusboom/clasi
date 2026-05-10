---
id: "009"
title: "Write unit tests for PHASES, create_sprint, and Sprint.detail_promote"
status: done
use-cases:
  - SUC-006
depends-on:
  - 017-004
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Write unit tests for PHASES, create_sprint, and Sprint.detail_promote

## Description

Unit tests covering the domain-layer changes from tickets 001-004. These
tests run without a live MCP server.

**Files to create or extend:**
- `tests/unit/test_state_db_class.py` (create if absent, extend if present)
- `tests/unit/test_project.py` (extend)
- `tests/unit/test_sprint.py` (extend)

## Acceptance Criteria

- [x] `test_roadmap_is_first_phase`: `PHASES[0] == "roadmap"`.
- [x] `test_advance_from_roadmap`: `StateDB.advance_phase()` from `roadmap` yields `planning-docs`.
- [x] `test_create_sprint_writes_only_sprint_md`: after `Project.create_sprint(title)`, only `sprint.md` exists in the sprint dir; `usecases.md`, `architecture-update.md`, `tickets/` are absent.
- [x] `test_create_sprint_status_roadmap`: `sprint.md` frontmatter has `status: roadmap`.
- [x] `test_detail_promote_scaffolds_artifacts`: `Sprint.detail_promote()` on a roadmap sprint writes `usecases.md`, `architecture-update.md`, creates `tickets/` and `tickets/done/`, and phase becomes `planning-docs`.
- [x] `test_detail_promote_rejects_non_roadmap`: calling `detail_promote()` on a sprint already in `planning-docs` raises `ValueError`.
- [x] `test_detail_promote_idempotent_guard`: manually creating `usecases.md` then calling `detail_promote()` raises `ValueError`.
- [x] All tests pass: `uv run pytest tests/unit/`.

## Implementation Plan

- Locate existing test files under `tests/unit/`.
- Add tests per the acceptance criteria above.
- Use `tmp_path` (pytest fixture) for sprint directories; create a minimal `Project` or just call `Sprint` directly with a fixture.
- For `StateDB` tests: instantiate `StateDB` with a temp SQLite path; call `register_sprint` then `advance_phase`.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/`
- **New tests to write**: All described in acceptance criteria.
- **Verification command**: `uv run pytest tests/unit/`
