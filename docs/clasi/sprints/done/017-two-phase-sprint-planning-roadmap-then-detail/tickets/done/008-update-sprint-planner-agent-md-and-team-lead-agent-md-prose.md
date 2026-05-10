---
id: "008"
title: "Update sprint-planner agent.md and team-lead agent.md prose"
status: done
use-cases:
  - SUC-005
depends-on:
  - 017-007
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint-planner agent.md and team-lead agent.md prose

## Description

Two agent prompt files describe the two-phase model. After the MCP tools are
implemented (tickets 001-006), their prose must match the actual tool contract.

**`clasi/plugin/agents/sprint-planner/agent.md`**
- Roadmap Mode section: state that `create_sprint` produces only `sprint.md`
  with `status: roadmap`. No deletion step.
- Detail Mode section: state that the agent calls `detail_sprint(sprint_id)`
  as the first step. This call advances the state DB to `planning-docs` and
  scaffolds the missing artifact files. The agent then writes content into
  those files.

**`clasi/plugin/agents/team-lead/agent.md`**
- Sprint queue survey section: distinguish roadmap sprints (phase = `roadmap`,
  not yet ready for execution) from planning-docs or later sprints (eligible
  for execution dispatch). Roadmap sprints require `detail_sprint` before
  any execution.

**Files to modify:**
- `clasi/plugin/agents/sprint-planner/agent.md`
- `clasi/plugin/agents/team-lead/agent.md`

## Acceptance Criteria

- [x] `sprint-planner/agent.md` Roadmap Mode describes `create_sprint` producing only `sprint.md`.
- [x] `sprint-planner/agent.md` Detail Mode describes calling `detail_sprint(sprint_id)` first.
- [x] `team-lead/agent.md` distinguishes `roadmap`-phase sprints from detail-planned sprints.
- [x] No contradictions with the skill files updated in ticket 007.
- [x] `uv run pytest` passes (prose change only).

## Implementation Plan

- Read both agent files in full.
- Edit `sprint-planner/agent.md`:
  - Roadmap Mode: remove any workaround language; confirm `create_sprint` is the single call.
  - Detail Mode: add explicit step to call `detail_sprint(sprint_id)` before writing content.
- Edit `team-lead/agent.md`:
  - Find the sprint queue or "what to do next" section.
  - Add note: "Roadmap sprints (phase = roadmap) require `detail_sprint` before execution dispatch."

## Testing

- **Existing tests to run**: `uv run pytest` (no test changes; prose only)
- **New tests to write**: None (prose update).
- **Verification command**: `uv run pytest`
