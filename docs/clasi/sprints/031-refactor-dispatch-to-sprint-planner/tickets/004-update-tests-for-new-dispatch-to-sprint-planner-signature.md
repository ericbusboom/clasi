---
id: '004'
title: Update tests for new dispatch_to_sprint_planner signature
status: todo
use-cases:
  - SUC-031-01
  - SUC-031-02
  - SUC-031-03
depends-on:
  - '001'
  - '002'
  - '003'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update tests for new dispatch_to_sprint_planner signature

## Description

Update `tests/unit/test_dispatch_tools.py` to cover the new
`dispatch_to_sprint_planner` signature and ensure all regressions are caught.

**Pass 1 — Fix broken existing tests:**

- Remove `sprint_directory` from argument dicts/calls in parametrize tables.
- Convert any positional `sprint_id` args to keyword style to match new
  signature.

**Pass 2 — Add `TestSprintPlannerNewSignature` class with these test cases:**

| Test | Assertion |
|------|-----------|
| `test_sprint_directory_not_a_parameter` | `inspect.signature` confirms `sprint_directory` absent |
| `test_title_parameter_present` | `inspect.signature` confirms `title` present, default `None` |
| `test_sprint_id_defaults_to_none` | `inspect.signature` confirms `sprint_id` default is `None` |
| `test_sprint_id_none_without_title_raises` | call with `sprint_id=None, title=None` → `ValueError` |
| `test_extend_mode_without_sprint_id_raises` | call with `mode="extend", sprint_id=None` → `ValueError` |
| `test_mode_accepts_extend` | `mode` parameter default is a string; `"extend"` is valid |

## Acceptance Criteria

- [ ] All existing `test_dispatch_tools.py` tests pass with updated signature
- [ ] `sprint_directory` confirmed absent from `dispatch_to_sprint_planner` signature
- [ ] `title` parameter present with default `None`
- [ ] `sprint_id` defaults to `None`
- [ ] `sprint_id=None` without `title` raises `ValueError`
- [ ] `mode="extend"` without `sprint_id` raises `ValueError`
- [ ] `mode` still accepts `"roadmap"`, `"detail"`, and `"extend"`
- [ ] Full test suite passes: `uv run pytest`

## Implementation Notes

- Most new tests are `inspect.signature` checks — no mocking of dispatch pipeline needed.
- Error-path tests use `pytest.raises` with `asyncio.run()` or `pytest-asyncio`.
- The delegation edge parametrize table should add an `"extend"` mode row to
  confirm `team-lead` is the only allowed caller for extend mode too.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_dispatch_tools.py`
- **New tests to write**: `TestSprintPlannerNewSignature` class in `test_dispatch_tools.py`
- **Verification command**: `uv run pytest`
