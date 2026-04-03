---
status: done
sprint: '003'
tickets:
- 003-007
---

# Move non-core agents to clasi/plugin/agents/old/

Ticket 005 consolidated too aggressively — it moved all 13 agents from
`clasi/agents/` into `clasi/plugin/agents/` as active agents. Our current model
only uses 3 agents: **team-lead**, **sprint-planner**, and **programmer**. The
other 10 agents (ad-hoc-executor, architect, architecture-reviewer, code-reviewer,
project-architect, project-manager, sprint-executor, sprint-reviewer, technical-lead,
todo-worker) are not active and should not be treated as current.

Move the 10 non-core agents into `clasi/plugin/agents/old/` so they're preserved
but clearly separated from the active agents. Update `contracts.py`, `project.py`,
and `process_tools.py` to only search the top-level `clasi/plugin/agents/` (not
recurse into `old/`), or adjust `list_agents` to skip the `old/` subdirectory.
