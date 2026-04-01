---
id: '003'
title: Update team-lead agent to remove create_sprint steps and use extend mode
status: todo
use-cases:
  - SUC-031-01
  - SUC-031-02
depends-on:
  - '001'
  - '002'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update team-lead agent to remove create_sprint steps and use extend mode

## Description

Update `clasi/agents/main-controller/team-lead/agent.md` to reflect the
simplified API now that `dispatch_to_sprint_planner` handles sprint creation
internally and supports a formal `extend` mode.

Three workflows need updating:

1. **"Execute TODOs"** — remove the `create_sprint` step. Update the
   `dispatch_to_sprint_planner` call to use the new signature:
   `(todo_ids=[...], goals=..., mode="detail", title=<title>)`.
   Note that `sprint_id` and `sprint_directory` come back in the return JSON.

2. **"Sprint Planning Only"** — same simplification: remove the `create_sprint`
   pre-step and update the dispatch call signature.

3. **"Implement new TODO in existing sprint"** — replace the informal
   `mode="add_to_sprint"` with the formal `mode="extend"`. Update the call to:
   `(todo_ids=[<new_todo>], goals=<description>, mode="extend", sprint_id=<id>)`.
   Remove the `sprint_directory` argument.

## Acceptance Criteria

- [ ] "Execute TODOs" workflow no longer includes a `create_sprint` step
- [ ] "Execute TODOs" `dispatch_to_sprint_planner` call uses new signature (no `sprint_directory`, uses `title`)
- [ ] "Execute TODOs" completion-check notes that `sprint_id`/`sprint_directory` come from return JSON
- [ ] "Sprint Planning Only" workflow no longer includes a `create_sprint` step
- [ ] "Sprint Planning Only" `dispatch_to_sprint_planner` call uses new signature
- [ ] "Implement new TODO in existing sprint" uses `mode="extend"` (not `mode="add_to_sprint"`)
- [ ] "Implement new TODO in existing sprint" does not pass `sprint_directory` to dispatch
- [ ] No remaining references to `sprint_directory` as an argument to `dispatch_to_sprint_planner`

## Implementation Notes

- The team-lead still needs `sprint_id` for `acquire_execution_lock` and
  `dispatch_to_sprint_executor`. These now come from the detail-mode return
  JSON (`sprint_id`, `sprint_directory`) instead of the preceding `create_sprint` call.
- `title` is required when no `sprint_id` is given. Document that it should
  come from the TODO's title or stakeholder-provided sprint name.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/`
- **New tests to write**: No automated tests for agent markdown; verify by grep
  that removed references are gone (see implementation notes)
- **Verification command**: `uv run pytest`
