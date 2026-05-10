---
id: "006"
title: "Update team-lead agent prompt with exception routing rules"
status: todo
use-cases:
  - SUC-003
  - SUC-004
depends-on:
  - "018-003"
  - "018-004"
  - "018-005"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update team-lead agent prompt with exception routing rules

## Description

Add an "Exception routing" section to `clasi/plugin/agents/team-lead/agent.md`.
The team-lead currently has no defined procedure for handling exception tickets.
Without routing rules, exceptions arrive and the team-lead improvises — or worse,
re-dispatches the same ticket to the same agent without resolving the structural
conflict.

The routing rules define: how to detect exceptions, how to classify them, and
what to do in each branch. The use-case doc is the routing anchor.

Depends on tickets 004 and 005 being done first, so the section can reference
the protocol the lower agents are following.

## Acceptance Criteria

- [ ] `clasi/plugin/agents/team-lead/agent.md` contains a clearly delimited
  "Exception routing" section.
- [ ] Section instructs the team-lead to call `list_tickets(status="exception")`
  after each lower-agent dispatch to detect thrown exceptions.
- [ ] Section instructs reading the ticket's `exception:` frontmatter block.
- [ ] Section defines the two routing branches:
  - User-visible (`surface: "user-visible"` or team-lead overrides after
    consulting `usecases.md`): escalate to stakeholder with a clear
    description of the conflict and the decision needed.
  - Internal (`surface: "internal"`): dispatch sprint-planner to revise
    `architecture-update.md` (or write `architecture-update-r1.md`),
    passing the full exception payload as context.
- [ ] Section instructs the team-lead to re-open or replace the ticket after
  resolution — no exception ticket is left in `exception` status permanently.
- [ ] Section states no silent abandonment: every exception ticket must
  produce either escalation or a revision cycle.
- [ ] Section references `usecases.md` as the anchor for the
  user-visible-vs-internal classification.
- [ ] No existing content removed or materially altered.
- [ ] No tests (documentation change only).

## Implementation Plan

**File to modify**: `clasi/plugin/agents/team-lead/agent.md`

**Approach**: Read the current file. Find the natural insertion point (after
execution-dispatch guidance, before sprint-close guidance). Insert:

```markdown
## Exception routing

After each programmer or sprint-planner dispatch, check for thrown exceptions:

1. Call `list_tickets(sprint_id=<current>, status="exception")`.
2. If no exception tickets, proceed normally.
3. For each exception ticket:
   a. Read the ticket's `exception:` frontmatter block.
   b. Consult `usecases.md`. Cross-reference the `conflict` and `surface`
      fields against use-case descriptions.
   c. **User-visible path** (surface maps to a use-case actor, trigger, or
      postcondition): Escalate to the stakeholder. Describe the conflict
      in plain terms. State what decision is needed to unblock. Do not
      re-dispatch the lower agent until the stakeholder has decided.
   d. **Internal path** (surface is structural — module boundary, dependency
      direction, internal data model): Dispatch the sprint-planner to revise
      the architecture. Pass the full exception payload as context. The
      sprint-planner writes `architecture-update-r1.md` (or `-r2.md`, etc.);
      the original is preserved.
4. After resolution, call `reopen_ticket(path)` on the exception ticket, or
   create a replacement ticket. Do not leave any ticket in `exception` status
   permanently.

**No silent abandonment**: If you cannot route (the use-case doc is too vague
to classify), escalate to the stakeholder to clarify the use cases before
routing.
```

**Verification**: Read the updated file; confirm section is present and the
rest of the agent prompt is intact.
