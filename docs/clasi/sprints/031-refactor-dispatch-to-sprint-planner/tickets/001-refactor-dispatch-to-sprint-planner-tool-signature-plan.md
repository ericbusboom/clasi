# Plan: 001 — Refactor dispatch_to_sprint_planner tool signature

## Approach

Focused code change to `clasi/tools/dispatch_tools.py`. The function signature
changes and the internal logic gains two new branches:

1. **Sprint creation branch** (`sprint_id=None`): validate that `title` is
   provided, call `create_sprint(title=title)` to get `sprint_id` and
   `sprint_directory`, then proceed with the existing roadmap/detail flow.

2. **Directory derivation** (all modes): replace the `sprint_directory`
   parameter with a call to `project.get_sprint(sprint_id)`. Validate that
   the sprint exists before proceeding.

3. **Extend mode branch** (`mode="extend"`): validate that `sprint_id` is
   not `None`, derive the directory, render the extend-mode template, and
   dispatch to the sprint-planner without triggering architecture review.

Key design decisions:
- Keep `_check_delegation_edge` guard unchanged.
- The `mode` string is passed through to the template renderer.
- Return JSON for detail/roadmap includes `sprint_id` and `sprint_directory`.

## Files to Create or Modify

| File | Action | Change |
|------|--------|--------|
| `clasi/tools/dispatch_tools.py` | Modify | New signature; sprint-creation branch; directory-derivation; extend-mode branch; updated docstring |

No other files are changed in this ticket (agent docs in 002, team-lead in 003, tests in 004).

## Testing Plan

**Type**: Unit (signature inspection + error-path)

Tests are written in ticket 004. After implementing, run:

```
uv run pytest tests/unit/test_dispatch_tools.py -x
```

**Manual smoke check**: `import inspect; inspect.signature(dispatch_to_sprint_planner)` confirms
`sprint_directory` is absent and `title`/`sprint_id` are present with `None` defaults.

## Documentation Updates

- Docstring inside `dispatch_to_sprint_planner` updated in this ticket.
- Sprint architecture doc (`architecture-update.md`) already describes the
  final state — no further update needed.
- `contract.yaml` and sprint-planner agent docs updated in ticket 002.
