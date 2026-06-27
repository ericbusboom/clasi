# Use MCP tools for sprint and ticket queries

Do NOT use Bash, Glob, ls, or filesystem exploration to query sprint or
ticket state. Use the CLASI MCP tools instead:

- `list_sprints()` — find sprints (not `ls clasi/sprints/`)
- `list_tickets(sprint_id=...)` — find tickets including done (not Glob on tickets/)
- `get_sprint_status(sprint_id=...)` — sprint state and ticket counts
- `get_sprint_phase(sprint_id=...)` — current phase and gate status

The MCP tools are the source of truth. They handle edge cases (done/
subdirectories, state database lookups) that filesystem exploration misses.
