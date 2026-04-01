# Plan: 003 — Update team-lead agent to remove create_sprint steps and use extend mode

## Approach

Single-file edit: `clasi/agents/main-controller/team-lead/agent.md`.

Locate the three affected workflow sections and make targeted changes:

1. **"Execute TODOs"** section:
   - Delete the `create_sprint` step and its completion-check bullet.
   - Update `dispatch_to_sprint_planner(...)` call: remove `sprint_id=<id>`
     and `sprint_directory=<dir>`; add `title=<title>`.
   - Update the completion-check note: `sprint_id` and `sprint_directory`
     come from the dispatch return JSON.

2. **"Sprint Planning Only"** section:
   - Same changes as "Execute TODOs".

3. **"Implement new TODO in existing sprint"** section:
   - Replace `mode="add_to_sprint"` with `mode="extend"`.
   - Remove `sprint_directory=<dir>` from the dispatch call.
   - Keep `sprint_id=<id>` (required for extend mode).
   - Update prose that described the informal `add_to_sprint` behavior.

## Files to Create or Modify

| File | Action | Change |
|------|--------|--------|
| `clasi/agents/main-controller/team-lead/agent.md` | Modify | Remove create_sprint steps; update dispatch call signatures; replace add_to_sprint with extend |

## Testing Plan

**Type**: Manual review (agent markdown has no automated unit tests)

After editing, verify with grep:

```bash
grep -n "create_sprint" clasi/agents/main-controller/team-lead/agent.md
grep -n "sprint_directory" clasi/agents/main-controller/team-lead/agent.md
grep -n "add_to_sprint" clasi/agents/main-controller/team-lead/agent.md
uv run pytest
```

All three greps should return no results for the updated sections.

## Documentation Updates

- `agent.md` itself is the documentation artifact being updated.
- No README or architecture doc changes required from this ticket.
