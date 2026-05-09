---
id: "025"
title: "Update tests/unit/test_hook_handlers.py fixtures for new paths and status values"
status: open
use-cases:
  - SUC-001
depends-on:
  - "008"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update tests/unit/test_hook_handlers.py fixtures for new paths and status values

## Description

Update `tests/unit/test_hook_handlers.py` — the test file with the most `docs/clasi/`
references (approximately 12 occurrences per the TODO). All hardcoded path strings in
fixtures and assertions must be updated to the new `.clasi/` layout.

Also update any `status: todo` fixture values to `status: open`, and any
`plan-to-todo`/`codex-plan-to-todo` hook key references to the renamed keys.

## Acceptance Criteria

- [ ] No `docs/clasi` string literals in `test_hook_handlers.py`
- [ ] No `status: todo` fixture values (use `status: open`)
- [ ] Hook key references use new names
- [ ] All tests in `test_hook_handlers.py` pass
- [ ] `uv run pytest tests/unit/test_hook_handlers.py` — green

## Implementation Plan

### Files to modify
- `tests/unit/test_hook_handlers.py`

### Testing plan
- `uv run pytest tests/unit/test_hook_handlers.py`
- `uv run pytest` — full suite
