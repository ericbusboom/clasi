---
id: "016"
title: "Merge Architecture into Sprint Artifact"
status: active
branch: sprint/016-merge-architecture-into-sprint-artifact
use-cases:
  - SUC-016-001
  - SUC-016-002
  - SUC-016-003
---

# Sprint 016: Merge Architecture into Sprint Artifact

## Goals

Eliminate `technical-plan.md` as a separate artifact and merge its role into
`architecture.md`, which becomes a first-class sprint document. This makes
the architecture visible to agents during sprint work and removes the
redundancy between "what changes we're making" and "what the architecture
looks like after."

## Problem

Agents consistently forget to update the architecture document because it
lives outside the sprint directory. The technical plan and architecture
document cover overlapping content. See reflection:
`docs/plans/reflections/2026-03-10-missing-architecture-update-in-sprint-summary.md`

## Solution

- `create_sprint` copies the latest architecture into the sprint directory
- The architect updates it in-place with a `## Sprint Changes` section
- On sprint close, the document gets versioned into `docs/plans/architecture/`
- Delete `technical-plan.md` as a separate artifact everywhere

## Success Criteria

- `create_sprint` copies the previous architecture doc into new sprints
- `technical-plan.md` template and references are removed
- Sprint review tools validate `architecture.md` instead of `technical-plan.md`
- `close_sprint` copies architecture to `docs/plans/architecture/architecture-NNN.md`
- All skills, agents, and instructions reference the new workflow
- All tests pass

## Scope

### In Scope

- Template changes (delete technical-plan, add architecture)
- `artifact_tools.py` changes (create_sprint, insert_sprint, review tools)
- Skill updates (plan-sprint, close-sprint, delete create-technical-plan)
- Instruction updates (architectural-quality, agents-section)
- Agent updates (architect, architecture-reviewer)
- Test updates

### Out of Scope

- Retroactive conversion of existing archived sprints
- Changes to sprint.md, usecases.md, or brief.md templates
- Changes to the ticket workflow

## Test Strategy

Update existing system tests in `test_sprint_review.py` to reference
`architecture.md` instead of `technical-plan.md`. Add tests for the new
copy-on-create behavior. Update unit test tool counts if needed.

## Architecture Notes

This is a process/tooling change, not an architectural change to CLASI's
code structure. The main code changes are in `artifact_tools.py` (sprint
creation and review functions) and `templates.py`.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

(To be created after sprint approval.)
