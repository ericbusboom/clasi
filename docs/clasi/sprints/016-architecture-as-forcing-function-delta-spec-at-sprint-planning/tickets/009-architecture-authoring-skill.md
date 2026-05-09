---
id: "016-009"
title: "architecture-authoring skill: brownfield delta mode"
status: todo
use-cases: [SUC-001]
depends-on: ["016-006"]
---

# 016-009: architecture-authoring skill — brownfield delta mode

## Description

Update `clasi/plugin/skills/architecture-authoring/SKILL.md` to add Mode 3:
Brownfield Delta. When producing an architecture for an existing project
sprint (not greenfield), the skill instructs the agent to output
`architecture-delta.md` in the structured delta format rather than free-prose
`architecture-update.md`.

## Acceptance Criteria

- [ ] `architecture-authoring/SKILL.md` has a Mode 3: Brownfield Delta section that:
  - States the output file name is `architecture-delta.md`.
  - References `clasi/schemas/se-process/delta-template.md` as the starting
    skeleton.
  - Explicitly documents all four valid section headings (ADDED / MODIFIED /
    REMOVED / RENAMED for both Components and Scenarios).
  - Explicitly forbids free prose outside delta sections for this mode.
  - States: "`clasi sprint validate-delta <id>` must return exit 0 before
    the sprint advances to architecture-review."
  - Documents item identity rules: component names and scenario titles are
    identity; renaming requires a RENAMED entry.
  - Documents Given/When/Then for new scenarios; existing scenarios unchanged
    until MODIFIED.
  - States that MODIFIED entries describe the change in prose (what changed
    and why). No requirement for full replacement content. Non-empty body
    is required; whitespace-only body is a format violation.
- [ ] Mode 2 (Sprint Architecture Update) is either removed or redirected to
  Mode 3 for new sprints — both the skill and any consuming agent prompts
  must not produce `architecture-update.md` for new sprints.
- [ ] The sprint-planner agent prompt references `architecture-delta.md`
  as the expected sprint planning artifact.

## Implementation Plan

### Approach

Edit `clasi/plugin/skills/architecture-authoring/SKILL.md`. Add Mode 3 as a
new section. Update Mode 2 to indicate it is deprecated for new sprints.
Update the sprint-planner agent prompt file to reference `architecture-delta.md`.

### Files to Modify

- `clasi/plugin/skills/architecture-authoring/SKILL.md`
- Sprint-planner agent prompt (locate via `clasi/plugin/agents/`)

### Testing Plan

No automated test for SKILL.md content. Verify manually that the Mode 3
instructions are complete and unambiguous.

### Documentation Updates

The SKILL.md IS the documentation update.
