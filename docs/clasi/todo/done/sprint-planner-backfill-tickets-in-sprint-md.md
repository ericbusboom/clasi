---
status: done
sprint: '003'
tickets:
- 003-004
---

# Sprint-planner should backfill sprint.md with ticket summary after ticket creation

After creating ticket files in Phase 4, the sprint-planner should update sprint.md's
`## Tickets` section with a summary table listing each ticket's number, title,
dependencies, and parallel execution group.

## Changes

1. **`clasi/templates/sprint.md`** — Replace the placeholder text in `## Tickets`
   with an empty table: `| # | Title | Depends On | Group |` and a note that
   tickets in the same group can execute in parallel.

2. **`.claude/agents/sprint-planner/agent.md`** — Insert a new step between
   current steps 14 and 15: after creating tickets and propagating references,
   update sprint.md's `## Tickets` table with ticket numbers, titles, depends-on
   values, and parallel execution groups (topological ordering: no deps = Group 1,
   depends only on Group 1 = Group 2, etc.).

3. **`clasi/agents/domain-controllers/sprint-planner/plan-sprint.md`** — Insert
   step 12b after step 12 (Create tickets): update sprint.md's `## Tickets`
   section with the same summary table.
