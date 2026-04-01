# Plan: 002 — Update sprint-planner agent documents for extend mode

## Approach

Four Markdown/YAML files in `clasi/agents/domain-controllers/sprint-planner/`
need targeted edits. No code is written; all changes are to agent definition
documents. Work through each file in this order:

1. **`contract.yaml`** — add extend mode inputs/outputs section; add `sprint_id`
   and `sprint_directory` to detail-mode output schema.
2. **`dispatch-template.md.j2`** — add a `{% if mode == "extend" %}` branch
   that renders existing sprint context (current tickets + summary) alongside
   the new TODO(s). Remove `sprint_directory` as an input variable.
3. **`plan-sprint.md`** — add an "Extend Mode" section after the existing
   detail/roadmap sections. Update detail-mode step 1 to handle two cases.
4. **`agent.md`** — add an extend mode workflow entry.

## Files to Create or Modify

| File | Action | Change |
|------|--------|--------|
| `clasi/agents/domain-controllers/sprint-planner/contract.yaml` | Modify | Add extend mode inputs/outputs; add sprint_id/sprint_directory to detail output |
| `clasi/agents/domain-controllers/sprint-planner/dispatch-template.md.j2` | Modify | Add extend mode branch; remove sprint_directory input |
| `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` | Modify | Add extend mode section; update detail step 1 |
| `clasi/agents/domain-controllers/sprint-planner/agent.md` | Modify | Add extend mode workflow |

## Testing Plan

**Type**: Unit (contract validation) + manual review

- Run the full test suite to confirm no test references `sprint_directory` as
  a sprint-planner input: `uv run pytest`
- Visually verify that the extend mode template branch renders correctly.
- Contract YAML validation tests (added in ticket 004) confirm the schema
  is internally consistent.

```
uv run pytest tests/unit/test_dispatch_tools.py tests/unit/test_mcp_server.py -x
```

## Documentation Updates

- `architecture-update.md` already describes the intended final state; no
  further update needed after this ticket.
- README and top-level docs do not reference the sprint-planner contract
  directly; no update needed.
