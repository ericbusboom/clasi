---
id: '001'
title: Update team-lead instructions with do-not-call list and fix examples
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: enforce-delegation-edges-in-dispatch.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update team-lead instructions with do-not-call list and fix examples

## Description

The team-lead agent currently has `dispatch_to_code_monkey` referenced in its
instructions as an example tool, implying the team-lead may call it directly.
This caused sprints 028 and 029 to skip the sprint-executor entirely, producing
incomplete dispatch logs and missing sprint-executor validation.

Fix 1: Remove all tier-2 dispatch tool names from team-lead instructions and
examples. Only list the tools the team-lead actually uses directly:
`dispatch_to_sprint_executor`, `dispatch_to_sprint_planner`,
`dispatch_to_project_manager`, `dispatch_to_project_architect`,
`dispatch_to_todo_worker`, `dispatch_to_ad_hoc_executor`,
`dispatch_to_sprint_reviewer`.

Fix 2: Add an explicit "do not call" list to team-lead agent.md stating that the
team-lead NEVER calls these tools directly — they are internal delegation edges:
- `dispatch_to_code_monkey` (called by sprint-executor)
- `dispatch_to_architect` (called by sprint-planner)
- `dispatch_to_architecture_reviewer` (called by sprint-planner)
- `dispatch_to_technical_lead` (called by sprint-planner)
- `dispatch_to_code_reviewer` (called by ad-hoc-executor)

## Acceptance Criteria

- [x] `dispatch_to_code_monkey` is removed from all team-lead instruction examples
- [x] team-lead agent.md contains an explicit "do not call" list of internal dispatch tools
- [x] The "do not call" list includes all five tier-2 dispatch tools with explanations of which agent calls them
- [x] The team-lead's allowed dispatch tools list is accurate and complete
- [x] `uv run pytest` passes with no failures

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: None — this is a documentation-only change to agent instructions
- **Verification command**: `uv run pytest`
