---
id: "002"
title: "Update project-manager and execute-ticket with parallel option"
status: todo
use-cases: [SUC-001]
depends-on: ["001"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update project-manager and execute-ticket with parallel option

## Description

Update two existing content files to include guidance on parallel
execution as an opt-in capability:

1. **agents/project-manager.md** — Add parallel dispatch guidance. When
   a sprint has multiple independent tickets (no file overlap, no
   dependency edges), the project-manager may choose to execute them in
   parallel using the parallel-execution skill. This is an explicit
   opt-in decision — the project-manager must analyze independence
   before choosing parallel. Sequential execution remains the safe
   default.

2. **skills/execute-ticket.md** — Add a note explaining the parallel
   execution option. When the project-manager has opted into parallel
   mode, individual tickets may be executed in isolated worktrees.
   The execute-ticket skill itself does not change its core flow — it
   still executes a single ticket. The note clarifies that the
   dispatch may happen inside a worktree rather than the main working
   directory.

Parallel is opt-in. Sequential is the default. The project-manager or
stakeholder must explicitly choose parallel execution.

## Acceptance Criteria

- [ ] `agents/project-manager.md` includes parallel dispatch guidance
- [ ] `skills/execute-ticket.md` includes a note about parallel execution option
- [ ] Parallel is clearly documented as opt-in (not automatic)
- [ ] Sequential execution is clearly documented as the default
- [ ] Both files reference the parallel-execution skill

## Testing

- **Existing tests to run**: `uv run pytest` — agent and skill listing tests must continue to find both files
- **New tests to write**: None required (content modifications to existing files)
- **Verification command**: `uv run pytest`
