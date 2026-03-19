---
id: "002"
title: "Update process_tools.py for directory tree"
status: todo
use-cases: []
depends-on: ["001"]
---

# Update process_tools.py for directory tree

## Description

The MCP process tools (`list_agents`, `get_agent_definition`,
`list_skills`, `get_skill_definition`, etc.) currently read from flat
directories. Update them to walk the new agent hierarchy.

### Changes

- `list_agents()` — walk `agents/` recursively, find all `agent.md` files
- `get_agent_definition(name)` — find the `agent.md` in the matching
  subdirectory by agent name
- New tool: `get_agent_context(name)` — returns the agent definition
  plus all other files in the agent's directory (skills, instructions)
- `list_skills()` — scan both global `skills/` and agent subdirectories
- `get_skill_definition(name)` — search global skills first, then agent
  directories

## Acceptance Criteria

- [ ] `list_agents()` returns all agents from the new tree
- [ ] `get_agent_definition(name)` finds agents in subdirectories
- [ ] `get_agent_context(name)` returns agent.md + sibling files
- [ ] `list_skills()` includes agent-specific skills
- [ ] Existing MCP tool tests updated and passing
- [ ] `get_se_overview()` reflects new agent/skill counts

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: test agent discovery from nested directories
- **Verification command**: `uv run pytest`
