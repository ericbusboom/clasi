---
id: "007"
title: "Fix team-lead over-specification to sprint planner"
status: done
use-cases: [SUC-003]
depends-on: ["006"]
github-issue: ""
todo: "team-lead-over-specifies-tickets-to-sprint-planner.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix team-lead over-specification to sprint planner

## Description

The team lead is doing the sprint planner's job when dispatching to it.
Instead of providing high-level goals and TODO references, the team lead
sends fully pre-digested ticket specifications -- exact titles, detailed
descriptions, dependency lists, acceptance criteria, and even YAML
frontmatter instructions. The sprint planner ends up as a transcription
agent rather than a planning agent.

This is the same class of problem as ticket 006 (fix TODO delegation),
but at a different boundary: team-lead-to-sprint-planner instead of
team-lead-to-todo-worker. Both tickets address the pattern of the team
lead doing subordinate agents' work.

Ticket 006 must be completed first because both tickets modify the
team-lead agent definition. The team-lead changes for TODO delegation
(006) and sprint-planner delegation (this ticket) should be coherent --
a single "delegation philosophy" section rather than scattered
instructions.

### Changes

1. **Team-lead agent definition** -- Add or extend delegation
   instructions to state: when dispatching to the sprint planner,
   provide high-level goals and TODO file references, not pre-digested
   ticket specifications. The team lead decides WHAT goes into a sprint;
   the sprint planner decides HOW to structure it into tickets. This
   should be consistent with the raw-text delegation pattern established
   in ticket 006.

2. **Sprint-planner agent definition** -- Confirm or add instructions
   making clear that the sprint planner is responsible for all ticket
   decomposition, scoping, and specification. It reads referenced TODOs,
   understands goals, and makes its own planning decisions about:
   - How to decompose goals into tickets
   - What each ticket's scope and acceptance criteria should be
   - What dependencies exist between tickets
   - How to sequence the work
   - Ticket titles and descriptions

3. **Dispatch protocol** -- The team lead's dispatch to the sprint
   planner should look like: "Plan this sprint with these goals and
   these TODOs: [list of TODO paths]" -- not "Create these specific
   tickets with these specific fields."

## Acceptance Criteria

- [x] Team-lead agent definition instructs providing high-level goals and TODO references to sprint planner
- [x] Team-lead agent definition explicitly prohibits pre-digesting ticket specs for the sprint planner
- [x] Sprint-planner agent definition states it owns ticket decomposition, scoping, and specification
- [x] Sprint-planner agent definition lists the planning decisions it is responsible for
- [x] Dispatch protocol supports goal-oriented delegation to sprint planner
- [x] Team-lead delegation instructions are coherent with the raw-text pattern from ticket 006
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (agent definition/protocol changes)
- **Manual verification**: Review the team-lead and sprint-planner agent definitions to confirm the delegation boundary is clear and consistent with ticket 006 changes
