---
id: "001"
title: "Restructure agent directories into tier hierarchy"
status: todo
use-cases: []
depends-on: []
---

# Restructure agent directories into tier hierarchy

## Description

Move the flat `agents/` directory into a three-tier hierarchy:
`agents/main-controller/`, `agents/domain-controllers/`,
`agents/task-workers/`. Each agent gets its own subdirectory containing
`agent.md`. Move agent-specific skills and instructions into the
agent's directory per the migration table in pc-architecture.md.

### Files to move

See the full migration table in pc-architecture.md § "Migration from
current layout". Key moves:

- `agents/project-manager.md` → `agents/main-controller/main-controller/agent.md`
- `agents/python-expert.md` → `agents/task-workers/code-monkey/agent.md`
- `skills/plan-sprint.md` → `agents/domain-controllers/sprint-planner/plan-sprint.md`
- `skills/execute-ticket.md` → `agents/domain-controllers/sprint-executor/execute-ticket.md`
- (34 total moves — see migration table)

Global skills and instructions stay in their current locations.

## Acceptance Criteria

- [ ] Three-tier directory structure created under `agents/`
- [ ] All existing agent files moved to `agent.md` in their new directories
- [ ] Agent-specific skills moved into agent directories
- [ ] `architectural-quality.md` moved into architect directory
- [ ] Global skills/instructions remain at top level
- [ ] No broken imports or path references in Python code

## Testing

- **Verification command**: `uv run pytest`
