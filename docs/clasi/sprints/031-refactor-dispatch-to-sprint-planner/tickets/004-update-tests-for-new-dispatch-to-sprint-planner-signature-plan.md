# Plan: 004 — Update tests for new dispatch_to_sprint_planner signature

## Approach

All test changes are in `tests/unit/test_dispatch_tools.py`. Two passes:

**Pass 1 — Fix broken existing tests:**
- Find every call or reference that passes `sprint_directory` as an argument
  (parametrize tables, direct calls). Remove it.
- For any positional `sprint_id` args, convert to keyword style to match the
  new `(todo_ids, goals, mode, sprint_id, title)` signature.

**Pass 2 — Add `TestSprintPlannerNewSignature` class:**
- `test_sprint_directory_not_a_parameter` — `inspect.signature` confirms absent.
- `test_title_parameter_present` — `inspect.signature` confirms present, default `None`.
- `test_sprint_id_defaults_to_none` — `inspect.signature` confirms default.
- `test_sprint_id_none_without_title_raises` — `ValueError` via `pytest.raises`.
- `test_extend_mode_without_sprint_id_raises` — `ValueError` via `pytest.raises`.
- `test_mode_accepts_extend` — `mode` parameter exists and is a string.

**Pass 3 — Run full suite:**
```
uv run pytest tests/unit/test_dispatch_tools.py -v
uv run pytest
```

## Files to Create or Modify

| File | Action | Change |
|------|--------|--------|
| `tests/unit/test_dispatch_tools.py` | Modify | Remove sprint_directory from call sites; add TestSprintPlannerNewSignature class |

## Testing Plan

**Type**: Unit (these tests ARE the testing artifact)

Verification:
```
uv run pytest tests/unit/test_dispatch_tools.py -v
uv run pytest  # full suite — must show no regressions
```

New tests use `inspect.signature` or `pytest.raises` — no full dispatch
pipeline mock required.

## Documentation Updates

- No external documentation changes needed from this ticket.
- After this ticket completes, all use cases are implemented, tested, and
  documented — the sprint is ready to close.
