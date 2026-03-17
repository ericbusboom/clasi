---
id: "004"
title: "Update project-manager and execute-ticket for dispatch model"
status: todo
use-cases: [SUC-001]
depends-on: ["001", "002"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update project-manager and execute-ticket for dispatch model

## Description

Update two existing content files to adopt subagent dispatch as the
primary execution model, replacing the current persona-switching
approach:

1. **agents/project-manager.md** — Update the execution guidance so the
   project-manager uses the dispatch-subagent skill as its primary
   method for getting implementation work done. The project-manager
   becomes a controller: it plans, curates context, dispatches subagents,
   and reviews results. It no longer "switches persona" to an
   implementer role.

2. **skills/execute-ticket.md** — Update the execution workflow so that
   the primary mechanism is dispatching a subagent with the ticket plan
   and curated context, rather than having the current agent adopt an
   implementer persona. The dispatch-subagent skill should be referenced
   as the core implementation step. The two-stage review (from the
   restructured code-reviewer agent) should be invoked on the subagent's
   output.

Both files should reference `dispatch-subagent` skill and
`subagent-protocol` instruction for the details of how dispatch works.

## Acceptance Criteria

- [ ] `agents/project-manager.md` uses dispatch as the primary execution model
- [ ] `skills/execute-ticket.md` dispatches a subagent instead of persona switching
- [ ] Both files reference the dispatch-subagent skill
- [ ] Both files reference the subagent-protocol instruction
- [ ] Two-stage review is invoked on subagent output in execute-ticket flow

## Testing

- **Existing tests to run**: `uv run pytest` — agent and skill listing tests must continue to find both files
- **New tests to write**: None required (content modifications to existing files)
- **Verification command**: `uv run pytest`
