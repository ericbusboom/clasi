---
status: in-progress
sprint: '031'
tickets:
- 031-001
---

# Refactor dispatch_to_sprint_planner Signature and Add "extend" Mode

## Summary

Refactor `dispatch_to_sprint_planner` to remove the redundant
`sprint_directory` parameter, make `sprint_id` optional, and add an
`extend` mode for adding TODOs to an already-executing sprint.

## New Signature

```python
async def dispatch_to_sprint_planner(
    todo_ids: list[str],
    goals: str,
    mode: str = "detail",        # "roadmap", "detail", or "extend"
    sprint_id: str | None = None, # required for "extend", optional otherwise
    title: str | None = None,     # required when creating a new sprint
) -> str:
```

- Remove `sprint_directory` — derive it from `sprint_id` via
  `project.get_sprint()`.
- `sprint_id` optional: if `None` in roadmap/detail mode, the sprint
  planner creates the sprint (requires `title`).
- `sprint_id` required in `extend` mode (sprint must already exist).

## Mode Definitions

- **`roadmap`** — batch-plan multiple sprints, lightweight `sprint.md` only.
- **`detail`** — full planning: architecture, review, tickets.
- **`extend`** — sprint is already executing; create new ticket(s) for
  the added TODO(s), consistent with the existing plan. No architecture
  review, no stakeholder approval.

## Files to Update

### dispatch_to_sprint_planner implementation
- `clasi/tools/dispatch_tools.py` — update function signature and body.

### Sprint planner agent and artifacts
- `clasi/agents/domain-controllers/sprint-planner/agent.md` — document
  the `extend` mode workflow.
- `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` — add
  extend mode section.
- `clasi/agents/domain-controllers/sprint-planner/dispatch-template.md.j2`
  — add `extend` template branch.
- `clasi/agents/domain-controllers/sprint-planner/contract.yaml` — add
  `extend` mode inputs/outputs.

### Team-lead agent.md
- `clasi/agents/main-controller/team-lead/agent.md`:
  - **"Execute TODOs Through a Sprint"** — remove `create_sprint` step;
    let the sprint planner create the sprint internally.
  - **"Sprint Planning Only"** — same, remove `create_sprint` step.
  - **"Implement new TODO in an existing sprint"** — use
    `dispatch_to_sprint_planner(mode="extend", sprint_id=<id>, ...)`.

### Stretch: remove sprint_directory from other dispatch tools
- Consider removing `sprint_directory` from `dispatch_to_sprint_executor`,
  `dispatch_to_sprint_reviewer`, etc. since it's always derivable from
  `sprint_id`. Could be a separate TODO.
