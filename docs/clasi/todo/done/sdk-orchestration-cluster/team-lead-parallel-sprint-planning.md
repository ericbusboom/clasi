---
status: in-progress
sprint: '001'
tickets:
- 001-006
---

# Team Lead Should Plan Multiple Sprints in One Pass

## Problem

When the stakeholder asks the team lead (project-manager agent) to plan
multiple sprints, it plans one sprint and then stops — waiting for that
sprint to finish before planning the next. This is overly cautious.
Sprint planning is a design-time activity that doesn't depend on the
previous sprint's execution being complete. The agent should be able to
look at all the tickets/work it has queued up and plan several sprints
in sequence when asked.

## Stakeholder Input

> "Can we ensure that the team lead agent understands that it doesn't
> have to wait to plan one sprint until the previous sprint is finished.
> If I ask it to plan sprints, plural, it should just go through all the
> tickets it's got and plan all the sprints. It seems to be timid about
> doing that."

## Proposed Solution

Update the project-manager agent definition and/or the plan-sprint skill
to make it clear that:

1. **Planning is not gated on execution.** When the stakeholder asks to
   plan multiple sprints, the agent should plan them all in the current
   conversation — creating sprint documents, branches, architecture
   updates, and tickets for each sprint before stopping.
2. **Batch planning is the expected behavior** when the stakeholder says
   "plan sprints" (plural) or otherwise signals they want more than one
   sprint planned.
3. **The agent should not ask for permission** to proceed to the next
   sprint's planning after finishing the previous sprint's plan. It
   should continue until all identified work is planned or the
   stakeholder interrupts.

## Files to Review or Modify

```
agents/project-manager.md     (add guidance on batch sprint planning)
skills/plan-sprint.md         (clarify that planning doesn't require
                               prior sprint completion)
```

## Open Questions

- Should there be a limit on how many sprints can be planned in one
  pass, or should the agent just plan everything it has?
- Does the plan-sprint skill need a loop/batch mode, or is the fix
  purely in the agent's instructions?
