---
id: '004'
title: Add ticket summary table backfill to sprint-planner and sprint template
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
todo: sprint-planner-backfill-tickets-in-sprint-md.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add ticket summary table backfill to sprint-planner and sprint template

## Description

After the sprint-planner creates all tickets in Phase 4, the `## Tickets` section
of `sprint.md` is left with a placeholder ("To be created after sprint approval.")
or an empty table. The stakeholder must open individual ticket files to understand
what was planned and how tickets relate.

This ticket:
1. Updates `clasi/templates/sprint.md` to replace the prose placeholder with an
   empty summary table with the right column headers.
2. Updates `plugin/agents/sprint-planner/agent.md` (or `clasi/plugin/...` after 001)
   to add a new step after ticket creation that populates the table.
3. Updates `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` to add
   step 12b with the same table backfill instruction.

Parallel execution groups are computed via topological sort:
- Group 1: tickets with no dependencies
- Group 2: tickets whose only dependencies are in Group 1
- Group N: tickets whose dependencies are all in Groups 1..N-1

## Acceptance Criteria

- [x] `clasi/templates/sprint.md` `## Tickets` section contains:
      ```
      | # | Title | Depends On | Group |
      |---|-------|------------|-------|
      ```
      with a note that tickets in the same group can execute in parallel
- [x] `plugin/agents/sprint-planner/agent.md` (or `clasi/plugin/...` after 001) has
      a new step between current steps 14 and 15 that reads: after creating all
      tickets, update the `## Tickets` table in `sprint.md` with ticket number, title,
      depends-on values, and parallel execution group
- [x] `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` has a step 12b
      after step 12 with the same table backfill instruction
- [x] The updated sprint.md template produces a valid table when rendered by
      `create_sprint`
- [x] `uv run pytest` passes (the template change may affect template tests)

## Implementation Plan

### Approach

1. Edit `clasi/templates/sprint.md`: replace `(To be created after sprint approval.)`
   in the `## Tickets` section with:
   ```
   | # | Title | Depends On | Group |
   |---|-------|------------|-------|

   Tickets in the same Group can execute in parallel.
   ```

2. Edit `plugin/agents/sprint-planner/agent.md` (adjust path if ticket 001 done):
   Insert a new numbered step after current step 14 ("Propagate TODO and GitHub issue
   references to ticket frontmatter"):

   > 14b. After all tickets are created, update the `## Tickets` table in `sprint.md`:
   >   - List each ticket's number, title, depends-on value(s), and parallel execution
   >     group (Group 1 = no deps; Group N = depends only on groups 1..N-1).
   >   - Use topological ordering. If circular dependencies exist, flag the error and
   >     do not create the table.

3. Edit `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md`:
   Insert step 12b after step 12 ("Create tickets") with the same instructions.

4. Run `uv run pytest` — check if any test references the sprint template and needs
   updating.

### Files to Modify

- `clasi/templates/sprint.md` — update `## Tickets` section
- `plugin/agents/sprint-planner/agent.md` (or `clasi/plugin/agents/...` if 001 done)
  — add step 14b
- `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` — add step 12b

### Files to Create

None.

### Testing Plan

- `uv run pytest` — look for any test that renders or validates the sprint template.
- Manual review: `clasi/templates/sprint.md` should have the table header visible.
- Read the updated agent definition and confirm the new step is logically placed
  between ticket creation and the return step.

### Documentation Updates

None beyond the template and agent definition files.
