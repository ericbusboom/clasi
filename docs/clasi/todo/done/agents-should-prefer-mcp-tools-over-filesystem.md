---
status: done
sprint: '003'
tickets:
- 003-009
---

# Agents should use MCP tools for sprint/ticket queries, not filesystem exploration

The sprint-planner agent was observed using Glob and Bash `ls` to find ticket files
instead of calling `list_tickets(sprint_id="003")`. The Glob failed because tickets
in `done/` weren't matched by the pattern, leading to unnecessary fallback commands.

The MCP tools already handle this correctly — `list_tickets` searches both `tickets/`
and `tickets/done/` and returns status for each. The agent just didn't use it.

## Fix

Add explicit guidance to the sprint-planner and programmer agent definitions:

- Use `list_tickets(sprint_id=...)` to query tickets — not Glob, ls, or Bash
- Use `list_sprints()` to find sprints — not directory listing
- Use `get_sprint_status(sprint_id=...)` for sprint state
- Use `get_sprint_phase(sprint_id=...)` for phase info
- **Do not use Bash, Glob, or ls to explore `docs/clasi/sprints/`** — the MCP
  tools are the source of truth and handle edge cases (done/ subdirectories,
  state database lookups) that filesystem exploration misses.

Add this as a rule in each agent's Rules section, or as a shared rule in
`clasi/plugin/rules/`.
