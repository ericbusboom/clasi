---
status: pending
---

# Enforce Delegation Edges in Dispatch Tools

## Problem

The team-lead can call `dispatch_to_code_monkey` directly even though
its delegation map says to go through `dispatch_to_sprint_executor`.
All dispatch tools are exposed to all callers — there's no enforcement
that the calling agent is allowed to dispatch to the target agent.

This caused sprints 028 and 029 to skip the sprint-executor entirely,
producing incomplete dispatch logs and missing sprint-executor
validation.

## Proposed Fixes

### 1. Remove tier-2 dispatch tools from team-lead examples

The REMINDER section in team-lead agent.md mentions
`dispatch_to_code_monkey` as an example. This implies the team-lead
can call it. Remove all tier-2 dispatch tool names from team-lead
instructions. Only mention the tools the team-lead actually uses:
`dispatch_to_sprint_executor`, `dispatch_to_sprint_planner`,
`dispatch_to_project_manager`, `dispatch_to_project_architect`,
`dispatch_to_todo_worker`, `dispatch_to_ad_hoc_executor`,
`dispatch_to_sprint_reviewer`.

### 2. Add explicit "do not call" list to team-lead

Add a rule to team-lead agent.md:

"You NEVER call these dispatch tools directly — they are internal
delegation edges used by sprint-planner and sprint-executor:
- dispatch_to_code_monkey (called by sprint-executor)
- dispatch_to_architect (called by sprint-planner)
- dispatch_to_architecture_reviewer (called by sprint-planner)
- dispatch_to_technical_lead (called by sprint-planner)
- dispatch_to_code_reviewer (called by ad-hoc-executor)"

### 3. Add caller validation to dispatch tools

Each dispatch tool reads `CLASI_AGENT_NAME` from the environment
(set by Agent.dispatch()). If the caller is not in the expected
set for that dispatch edge, log a warning. For example:

```python
@server.tool()
async def dispatch_to_code_monkey(...):
    caller = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    allowed_callers = {"sprint-executor", "ad-hoc-executor"}
    if caller not in allowed_callers:
        logger.warning(
            "DELEGATION VIOLATION: %s called dispatch_to_code_monkey "
            "(expected: %s)", caller, allowed_callers
        )
    ...
```

Start with warnings, not blocks — blocking would break the
interactive session where the team-lead doesn't have
CLASI_AGENT_NAME set.

### 4. Contract-based delegation validation (future)

The `delegates_to` field in each agent's contract.yaml lists the
valid delegation edges. The dispatch tool could read the caller's
contract and verify the target is in its `delegates_to` list before
proceeding. This makes the contract the single source of truth for
delegation rules.

This is more complex and can be a future enhancement after the
warning-based approach proves effective.
