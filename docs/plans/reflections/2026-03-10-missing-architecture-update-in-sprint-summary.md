---
date: 2026-03-10
sprint: null
category: ignored-instruction
---

## What Happened

When asked to summarize the sprint process before starting sprint 027, I
listed the planning documents (sprint.md, usecases.md, technical-plan.md),
the review phases, ticketing, execution, and closure — but omitted the
architecture document update (`docs/plans/architecture/architecture-002.md`).

The stakeholder had to prompt me: "there's supposed to be an update to the
architecture document. Where is that?"

## What Should Have Happened

The sprint summary should have included the architecture version update as
a first-class planning artifact. The architectural-quality instruction is
explicit: "Each sprint that changes the architecture produces a new version."
This sprint clearly introduces new modules (Scheduler, backup rotation),
a new database table, new routes, and new middleware — all architectural
changes.

The architecture document should have appeared alongside the sprint
directory artifacts, not as an afterthought.

## Root Cause

**Ignored instruction.** The relevant rules are documented in two places:

1. `instructions/architectural-quality.md` — "Each sprint that changes the
   architecture produces a new version, numbered sequentially."
2. `instructions/software-engineering.md` — Stage 1b is Architecture, and
   the sprint lifecycle includes architecture review as a gate.

I had just read both of these instructions earlier in the same conversation
(to create the retroactive architecture-001.md). Despite having the
information in context, when I shifted to summarizing the sprint process
I fell back on a generic mental model of "sprint planning docs = sprint.md
+ usecases.md + technical-plan.md" and didn't include the architecture
version as a distinct deliverable.

The likely cause is that the sprint planning summary was generated from
the skill/phase structure (plan-sprint → architecture-review → ticketing →
execution → closure) rather than from the artifact list. The architecture
document is produced by the architect agent during the planning-docs phase,
but it lives outside the sprint directory (in `docs/plans/architecture/`),
which made it easy to overlook when listing "documents created in the
sprint directory."

## Proposed Fix

No new instruction is needed — the existing instructions are clear. The
fix is behavioral:

1. When summarizing sprint deliverables, always consult the artifact list
   in `instructions/software-engineering.md` (Section "Artifacts") rather
   than reconstructing from memory.
2. Explicitly check: "Does this sprint change the architecture?" If yes,
   list the new architecture version as a deliverable.
3. Remember that the architecture document lives at the project level
   (`docs/plans/architecture/`), not inside the sprint directory — it's
   easy to miss when thinking in terms of "what goes in the sprint folder."
