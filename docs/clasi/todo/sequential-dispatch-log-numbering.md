---
status: pending
---

# Sequential Dispatch Log Numbering

## Problem

Dispatch log files are currently named like `sprint-planner-001.md`,
`architect-001.md`, `sprint-executor-001.md` — each agent type gets
its own counter. When you look at a sprint's log directory, you can't
tell the order things happened:

```
sprint-planner-001.md    (was this first?)
architect-001.md         (or this?)
sprint-planner-002.md    (detail planning came later?)
sprint-executor-001.md   (when did execution start?)
code-monkey-001.md       (which ticket was this?)
```

## Proposed Change

Use a single three-digit sequential counter across all dispatch logs
within a sprint directory. The counter increments for every dispatch,
regardless of agent type:

```
001-sprint-planner.md     (first: roadmap planning)
002-sprint-planner.md     (second: detail planning)
003-architect.md          (third: architecture)
004-architecture-reviewer.md
005-technical-lead.md
006-sprint-executor.md
007-code-monkey.md        (ticket 001)
008-code-monkey.md        (ticket 002)
009-code-monkey.md        (ticket 003)
```

Now you can read the directory listing in order and see exactly what
happened and when.

## Implementation

In `dispatch_log.py`, the `log_dispatch()` function currently finds
the next number per agent name. Change it to find the next number
across ALL files in the sprint log directory, then prefix the filename
with that number.

The adhoc log directory should use the same pattern.
