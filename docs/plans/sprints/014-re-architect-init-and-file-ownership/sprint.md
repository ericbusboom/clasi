---
id: "014"
title: Re-architect Init and File Ownership
status: planning
branch: sprint/014-re-architect-init-and-file-ownership
use-cases: [UC-001, UC-002, UC-003]
---

# Sprint 014: Re-architect Init and File Ownership

## Goals

Introduce versioned architecture documents to the CLASI SE process. Replace
the flat architect and architecture-reviewer agents with versioned-aware
versions, add an architectural quality instruction guide, and update the
software-engineering process instructions to reference the new workflow.

## Problem

The current architect agent produces a single flat `technical-plan.md` with
no versioning and no sprint awareness. There is no shared quality guide for
evaluating architectural decisions. The architecture-reviewer has limited
review criteria. This means architecture decisions are not tracked over time
and there is no baseline document describing the current system state.

## Solution

1. Install a new `architectural-quality.md` instruction file as the shared
   reference for both architect and reviewer.
2. Replace the architect agent with a versioned-aware version that produces
   `docs/plans/architecture/architecture-NNN.md` documents and sprint
   technical plans.
3. Replace the architecture-reviewer with an expanded version that reviews
   both architecture versions and sprint plans against the quality guide.
4. Update `software-engineering.md` to reference the architecture directory,
   versioned workflow, and new instruction file.
5. Update sprint templates to include architecture version references.
6. Produce the initial `architecture-001.md` baseline describing the current
   system.

## Success Criteria

- `architectural-quality.md` instruction file exists and is served by MCP
- Architect agent definition references versioned architecture documents
- Architecture-reviewer agent includes design quality assessment criteria
- `software-engineering.md` references architecture directory and versioning
- Sprint technical plan template includes architecture version fields
- `architecture-001.md` baseline document exists describing current system
- All existing tests pass

## Scope

### In Scope

- New instruction file: `architectural-quality.md`
- Replacement agent: `architect.md`
- Replacement agent: `architecture-reviewer.md`
- Updated instruction: `software-engineering.md`
- Updated template: `SPRINT_TECHNICAL_PLAN_TEMPLATE` in `templates.py`
- New baseline: `docs/plans/architecture/architecture-001.md`

### Out of Scope

- Producing architecture-002.md (that happens in a future sprint)
- Changing the sprint lifecycle phases in the state database
- Modifying the MCP server code (content is served automatically)
- Retroactively versioning past sprints

## Test Strategy

- Run existing test suite to verify no regressions
- Verify the MCP server serves the new instruction file via `list_instructions`
- Verify updated agent definitions are served via `get_agent_definition`
- Manual verification that architecture-001.md is well-formed

## Architecture Notes

The reference files for the new agents and quality guide are stored in
`docs/plans/todo/done/add-versioned-architecture-process/`. These are the
source of truth for the replacement content.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, technical plan)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

(To be created after sprint approval.)
