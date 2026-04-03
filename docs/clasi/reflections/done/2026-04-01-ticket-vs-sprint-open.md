---
date: 2026-04-01
sprint: "001"
category: ambiguous-instruction
---

# Left Ticket Open Instead of Sprint

## What Happened

Stakeholder said "leave the ticket open for additional testing and updates."
I interpreted "ticket" literally and left CLASI ticket 001-001 in `in-progress`
status. The implementation was complete — both scripts were written, executable,
and existing tests passed.

## What Should Have Happened

I should have:
1. Marked ticket 001-001 as `done` (the implementation work was finished).
2. Left the **sprint** open (not closed it), which is what the stakeholder
   actually meant — the sprint stays in `executing` phase for future
   additions and testing.

The stakeholder used "ticket" loosely to mean "this body of work," not the
specific CLASI ticket artifact. Context made this clear: the code was done,
so the ticket should be done. The sprint is the container that stays open.

## Root Cause

**Ambiguous instruction** — The stakeholder's request used "ticket" when they
meant "sprint." However, the context was unambiguous: when implementation is
complete, a ticket should be marked done. The agent should have applied
domain knowledge of the CLASI process (tickets track units of work;
sprints track batches of work) rather than taking the word "ticket"
literally.

More fundamentally: the agent defaulted to literal interpretation over
contextual reasoning. A completed unit of work is done. The question of
"what stays open for future updates" is naturally a sprint-level concern,
not a ticket-level one.

## Proposed Fix

When the stakeholder says to "leave X open" after implementation is complete:
- If the implementation is done, mark the ticket done.
- "Open" refers to the sprint (the container), not the completed work item.
- Apply the CLASI principle: tickets are atomic units of work. When the work
  is done, the ticket is done. Sprints are the lifecycle boundary.
