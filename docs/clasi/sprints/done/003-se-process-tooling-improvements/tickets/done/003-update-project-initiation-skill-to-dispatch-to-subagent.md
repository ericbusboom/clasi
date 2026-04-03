---
id: '003'
title: Update project-initiation skill to dispatch to subagent
status: done
use-cases:
- SUC-002
- SUC-003
depends-on:
- '002'
github-issue: ''
todo: project-initiation-dispatch-to-subagent.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update project-initiation skill to dispatch to subagent

## Description

The `project-initiation` skill currently instructs the invoking agent (team-lead) to
write `overview.md`, `specification.md`, and `usecases.md` directly. This violates
the team-lead's core behavioral rule: "You never write planning content or code
directly."

Update the skill so that the team-lead dispatches to the sprint-planner agent (via
the Agent tool) to produce the design documents. The sprint-planner already has
write access to planning artifacts and is the correct author for this content.

This ticket depends on ticket 002 (output directory confirmed/fixed) so that the
subagent instructions reference the correct directory from the start.

## Acceptance Criteria

- [x] `plugin/skills/project-initiation/SKILL.md` (or `clasi/plugin/...` after 001)
      instructs the team-lead to dispatch to the sprint-planner agent via the Agent
      tool, passing the specification file path
- [x] The skill does NOT instruct the team-lead to write documents itself
- [x] The skill specifies that the dispatched subagent writes all three documents to
      `docs/clasi/design/` and calls `create_overview`
- [x] The `plugin/agents/team-lead/agent.md` (or `clasi/plugin/...`) "Project
      Initiation" scenario description is consistent with the updated skill
      (i.e., team-lead dispatches, does not write)
- [x] `clasi/agents/main-controller/team-lead/agent.md` is also checked for
      consistency and updated if it contradicts the dispatch pattern
- [x] After running `clasi init`, the installed `project-initiation` skill reflects
      the subagent dispatch pattern
- [x] `uv run pytest` passes

## Implementation Plan

### Approach

1. Read the current `plugin/skills/project-initiation/SKILL.md` Process section.
2. Rewrite the Process section to instruct the team-lead to:
   a. Dispatch to the sprint-planner agent via the Agent tool.
   b. Pass: specification file path, instruction to write to `docs/clasi/design/`,
      instruction to call `create_overview` MCP tool after writing `overview.md`.
   c. Await completion and report result.
3. Remove any step that says "write [document]" from the team-lead's perspective.
4. Read `plugin/agents/team-lead/agent.md` "Project Initiation" section and confirm
   it says "dispatch to sprint-planner" (not "write documents"). Update if needed.
5. Check `clasi/agents/main-controller/team-lead/agent.md` for consistency.
6. Run `uv run pytest`.

### Files to Modify

- `plugin/skills/project-initiation/SKILL.md` (or `clasi/plugin/...` if 001 done)
  — rewrite Process section to dispatch pattern
- `plugin/agents/team-lead/agent.md` (or `clasi/plugin/...`) — verify/update Project
  Initiation scenario if it describes direct writing
- `clasi/agents/main-controller/team-lead/agent.md` — verify/update for consistency

### Files to Create

None.

### Testing Plan

- `uv run pytest` for regressions.
- Manual review: read installed `project-initiation` SKILL.md and confirm no
  instruction tells the invoking agent to write files directly.
- Manual review: confirm team-lead agent.md Project Initiation section says
  "dispatch" not "write".

### Documentation Updates

None beyond the skill and agent md files.
