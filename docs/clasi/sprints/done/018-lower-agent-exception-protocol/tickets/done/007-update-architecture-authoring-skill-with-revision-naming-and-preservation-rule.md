---
id: "007"
title: "Update architecture-authoring skill with revision naming and preservation rule"
status: done
use-cases:
  - SUC-005
  - SUC-006
depends-on:
  - "018-006"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update architecture-authoring skill with revision naming and preservation rule

## Description

Add a "Revision naming and preservation" rule to
`clasi/plugin/skills/architecture-authoring/SKILL.md`. When the exception
loop triggers an architecture revision, the skill currently has no guidance
on whether to overwrite `architecture-update.md` or create a new file. Without
an explicit rule, agents will overwrite — destroying the calibration signal.

The rule: never overwrite `architecture-update.md`. Write revisions as
`architecture-update-r1.md`, `-r2.md`, etc. The original persists.

Also update the sprint-planner agent prompt to reference this convention,
since the sprint-planner is the agent that performs revision writes.

Depends on ticket 006 (team-lead routing), because the team-lead is the one
that dispatches the sprint-planner into a revision loop. The revision naming
rule needs to be consistent with what the team-lead instructs.

## Acceptance Criteria

- [x] `clasi/plugin/skills/architecture-authoring/SKILL.md` contains a
  "Revision naming and preservation" rule or equivalent clearly delimited
  sub-section.
- [x] Rule states: do NOT overwrite `architecture-update.md`.
- [x] Rule states: write revision as `architecture-update-r1.md`; subsequent
  revisions increment the suffix (`-r2.md`, `-r3.md`, etc.).
- [x] Rule states: the latest `-rN.md` is the active planning artifact.
- [x] Rule states: original and all intermediate revisions remain as
  historical record (calibration signal).
- [x] `clasi/plugin/agents/sprint-planner/agent.md` references the revision
  naming convention (brief cross-reference is sufficient — full rule lives
  in the skill).
- [x] No existing skill content removed or materially altered.
- [x] No tests (documentation change only).

## Implementation Plan

**Files to modify**:
1. `clasi/plugin/skills/architecture-authoring/SKILL.md` — add revision
   naming rule in the Mode 2 section (sprint architecture updates, not
   Mode 1 / initial architecture).
2. `clasi/plugin/agents/sprint-planner/agent.md` — add brief note in the
   architecture-authoring guidance referencing the `-rN.md` naming convention.

**Approach**:
- Read both files first.
- In `SKILL.md`, find the Mode 2 section. Append after the existing Mode 2
  content (or insert as a new sub-section `### Revision naming and
  preservation`).
- In `sprint-planner/agent.md`, find where architecture authoring is mentioned.
  Add one sentence: "When revising in response to an exception, write
  `architecture-update-r1.md` (never overwrite `architecture-update.md`) —
  see `architecture-authoring` skill for the full rule."

**Verification**: Read both updated files; confirm rules are present and
existing content is intact.
