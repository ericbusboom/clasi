---
id: "024"
title: "Update agent prompt files in clasi/plugin/agents/ for new paths and issue terminology"
status: open
use-cases:
  - SUC-001
depends-on:
  - "014"
  - "022"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update agent prompt files in clasi/plugin/agents/ for new paths and issue terminology

## Description

Update agent prompt markdown files in `clasi/plugin/agents/` (team-lead, sprint-planner,
and any others):
- Replace `docs/clasi/` path references with `.clasi/`
- Replace "TODO" (as artifact name) with "issue" throughout
- Replace `status: todo` references with `status: open`
- Replace `/todo` skill references with `/issue`
- Replace `plan-to-todo` with `plan-to-issue`

Also update `clasi/plugin/instructions/subagent-protocol.md` and `clasi/plugin/rules/`
if they reference old terminology.

Skill files were updated in ticket 014. This ticket is for agent prompts and instructions.

## Acceptance Criteria

- [ ] All agent prompts in `clasi/plugin/agents/` use "issue" terminology
- [ ] All agent prompts reference `.clasi/` not `docs/clasi/`
- [ ] `status: open` used for unstarted tickets in prompts (not `status: todo`)
- [ ] `/issue` skill referenced (not `/todo`)
- [ ] `grep -rn "docs/clasi" clasi/plugin/` returns zero hits
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/plugin/agents/team-lead/agent.md`
- `clasi/plugin/agents/sprint-planner/agent.md` (if present)
- `clasi/plugin/agents/team-lead/project-status.md` (if present)
- `clasi/plugin/instructions/subagent-protocol.md`
- `clasi/plugin/rules/*.md`

### Testing plan
- Grep verification: `grep -rn "docs/clasi\|status: todo\|plan-to-todo\|/todo" clasi/plugin/`
- `uv run pytest` — full suite
