---
id: 008
title: 'Hook handlers: replace hardcoded `docs/clasi` path strings with `Project`
  property lookups'
status: todo
use-cases:
  - SUC-001
depends-on:
  - "006"
  - "005"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Hook handlers: replace hardcoded `docs/clasi` path strings with `Project` property lookups

## Description

`clasi/hook_handlers.py` has approximately 14 occurrences of hardcoded `Path("docs/clasi...")`
and `file_path.startswith("docs/clasi/...")` strings. These must be replaced with
dynamic resolution via `get_project().clasi_dir` (or equivalent).

Also update handler function names:
- `handle_plan_to_todo` → `handle_plan_to_issue`
- `handle_codex_plan_to_todo` → `handle_codex_plan_to_issue`

And hook registry keys:
- `"plan-to-todo"` → `"plan-to-issue"`
- `"codex-plan-to-todo"` → `"codex-plan-to-issue"`

## Acceptance Criteria

- [ ] No `"docs/clasi"` string literals remain in `hook_handlers.py`
- [ ] All path constructions use `get_project().clasi_dir` or `Project` properties
- [ ] `"docs/clasi/todo"` references replaced with `get_project().issues_dir`
- [ ] Handler function names updated
- [ ] Hook registry keys updated
- [ ] `tests/unit/test_hook_handlers.py` imports updated (full fixture update in ticket 025)
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/hook_handlers.py` — all path strings and handler names

### Testing plan
- `uv run pytest tests/unit/test_hook_handlers.py`
- `uv run pytest` — full suite
