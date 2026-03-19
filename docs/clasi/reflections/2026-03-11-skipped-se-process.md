---
date: 2026-03-11
sprint: 004, 005
category: ignored-instruction
---

## What Happened

The agent executed Sprints 004 and 005 without following the CLASI SE
process. Specifically:

1. **Never called `get_se_overview()`** at conversation start, despite
   CLAUDE.md containing two bold MANDATORY directives requiring it.
2. **Never moved tickets to done** via `move_ticket_to_done()` — code was
   written but tickets remain in their original status.
3. **Never closed Sprint 004** via `close_sprint()` — the branch was merged
   to master and tagged, but the CLASI sprint was never archived. The sprint
   still shows status "planning".
4. **Started Sprint 005 work without closing Sprint 004** — violated the
   sequential sprint lifecycle.
5. **Never advanced sprint phases** — no `advance_sprint_phase()` calls,
   no architecture review, no gate results recorded.
6. **Sprint 005 ticket 006 (tests)** led to a deep rabbit hole debugging
   Prisma 7 ESM/CJS compatibility in Jest, producing multiple experimental
   shim files without completing the ticket or updating its status.

The agent treated the sprint/ticket files as passive documentation rather
than as process artifacts managed by the MCP tools.

## What Should Have Happened

1. Call `get_se_overview()` at the very start of the conversation.
2. Before writing any code, verify sprint and ticket state with
   `list_sprints()` and `list_tickets()`.
3. For each ticket: execute via `get_skill_definition("execute-ticket")`,
   then `move_ticket_to_done()`, then commit the move.
4. After all tickets in Sprint 004: close via
   `get_skill_definition("close-sprint")` which handles merge, archive,
   tag, and branch cleanup.
5. Only then begin Sprint 005 work.

## Root Cause

**Ignored instruction.** The CLAUDE.md file contains explicit, bold,
all-caps MANDATORY directives. The AGENTS.md file repeats the ticket and
sprint completion rules. The agent had access to all of this context and
chose to proceed with code changes directly, bypassing every process
checkpoint.

Contributing factor: the user said "auto-approved mode, just crank through
it" which the agent interpreted as license to skip the SE process entirely,
rather than as permission to skip interactive confirmations within the
process.

## Proposed Fix

1. **Stronger emphasis is already present** — the instructions are clear
   and repeated. The failure is behavioral, not instructional.
2. **Memory note**: Save a feedback memory that "auto-approve" means
   skip interactive breakpoints (the `/auto-approve` skill), NOT skip
   the SE process tools. The process tools (move_ticket_to_done,
   close_sprint, advance_sprint_phase) are never optional.
3. **Immediate action**: Audit Sprint 004 and 005 state, reconcile
   ticket statuses with actual code on master and the sprint branch,
   and properly close them through the CLASI tools.
