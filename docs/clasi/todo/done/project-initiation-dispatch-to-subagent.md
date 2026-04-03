---
status: done
sprint: '003'
tickets:
- 003-003
---

# Project initiation skill should dispatch to a subagent instead of writing directly

The `project-initiation` skill currently instructs the invoking agent to write
`overview.md`, `specification.md`, and `usecases.md` directly. When the team-lead
invokes this skill, it violates the team-lead's behavioral rule: "You never write
planning content or code directly."

Change the skill so that the team-lead dispatches to a subagent (e.g. sprint-planner
or a dedicated initiation agent) for producing the design documents, rather than
writing them itself.
