---
status: done
sprint: '031'
tickets:
- 031-002
---

# Sprint phase machine gates ticketing on stakeholder approval, but plan-sprint docs say tickets are created before review

## Description

During sprint 026 planning (2026-08-19), the dispatched sprint-planner
completed sprint.md, the design overlay, and the architecture-review gate,
then hit a hard rejection on `create_ticket`: "Tickets can only be created
in 'ticketing' phase or later." The phase machine (`_GATE_REQUIREMENTS` in
`state_db_class.py`) requires a recorded `stakeholder_approval` gate for
the `stakeholder-review` → `ticketing` transition.

The plan-sprint skill, the sprint-planner agent definition, and the
team-lead agent.md all describe the opposite order: the sprint-planner
creates tickets inline during its planning session, and the stakeholder
reviews the completed plan WITH its tickets afterward (team-lead agent.md
"Execute Issues Through a Sprint" steps 4-5). The planner had to park its
ticket breakdown as a table inside sprint.md and hand back a blocked
result, costing a second dispatch to materialize the tickets after
approval.

Either order is defensible; the two artifacts just have to agree.

## Cause

The stakeholder_approval gate was inserted into the phase machine without
updating the planning skill/agent documentation that predates it.

## Proposed fix

Pick one order and align everything to it:

- If review-before-ticketing is intended: update plan-sprint SKILL.md,
  sprint-planner agent.md, and team-lead agent.md to a two-dispatch flow
  (plan → stakeholder review → ticket materialization), and make the
  planner's parked-ticket-table handoff (as done in sprint 026) the
  documented mechanism.
- If ticketing-before-review is intended (the documented flow): drop the
  stakeholder_approval requirement from the `stakeholder-review` →
  `ticketing` transition and gate execution (`enter-sprint` /
  `acquire_execution_lock`) on it instead.

## Verification

- A single sprint-planner dispatch following the documented flow reaches
  ticket creation (or the docs explicitly describe the two-dispatch flow)
  with no rejected MCP calls.

## Related

- Sprint 026 planning handoff (first observed occurrence).
- `report-guard-friction-slowness-relax-tier-0-restrictions.md` — same
  theme: documented workflow disagreeing with enforced behavior.
