---
status: pending
---

# Use Case Review and Developer Engagement

**Do not implement yet.**

## Problem

Use cases currently serve as the agent talking to itself — organizing
its thinking about flows and scenarios. The developer should be reading
them, but in practice they're hard to engage with because there's no
signal about which parts need attention. The agent makes arbitrary
decisions throughout (error handling order, retry strategies, edge case
behavior) and those decisions compound. By the time they surface as
code, they're expensive to change.

The missing piece is a structured conversation between agent and
developer about use cases, triggered when the agent recognizes it has
made decisions that could reasonably have gone a different way.

## Proposed Solution

### Use-Case Reviewer Agent/Skill

A `use-case-reviewer` that runs after use cases are written during
sprint planning (between use case authoring and architecture). It reads
each use case critically and produces a verdict:

- **APPROVED** — use case is clear, complete, and the decisions in it
  are well-constrained by the problem.
- **NEEDS REVISION** — issues the agent can fix on its own (missing
  error paths, inconsistent preconditions, gaps in acceptance criteria).
- **NEEDS DISCUSSION** — the use case contains decisions with meaningful
  alternatives that the developer should weigh in on.

### Ambiguity Trigger

The trigger for NEEDS DISCUSSION is not complexity — it's ambiguity.
The question is: "how many decisions did I make that could reasonably
have gone a different way?" A complex but well-specified feature doesn't
need the conversation. A simple-sounding feature with lots of implicit
choices does.

Examples of what triggers discussion:
- Multiple valid error-handling strategies (retry vs fail vs escalate)
- User-facing behavior where the "right" answer depends on preference
- Architectural choices that trade off different qualities (simplicity
  vs flexibility, consistency vs performance)
- Flows where the order of operations is arbitrary but affects UX

### Developer Engagement Flow

For NEEDS DISCUSSION verdicts, the reviewer annotates specific decision
points within the use case. Example:

> SUC-003 step 4 assumes retry-then-fail after 3 attempts, but
> retry-then-escalate is equally valid. The choice affects whether
> the user ever sees a partial result. Ask the developer.

The planning flow pauses and presents flagged items to the developer.
The developer can:
- Engage and make the call on specific decisions
- Say "your call" to accept the agent's default
- Defer to discuss later

The developer should still read all use cases — the flags just help
them focus on where their input changes the outcome.

## Files to Create or Modify

```
agents/use-case-reviewer.md    (new agent, or skill)
skills/plan-sprint.md          (add review step after use case writing)
```

## Open Questions

- Agent or skill? An agent definition is more natural since it's a
  review role, but a skill might integrate more cleanly into the
  plan-sprint flow.
- Should the reviewer also check use cases written during requirements
  elicitation, or only sprint-level use cases?
- How to present flagged items — inline annotations in the use case
  file, or a separate review artifact?
