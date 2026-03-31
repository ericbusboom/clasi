---
date: 2026-03-31
sprint: "029"
category: ignored-instruction
---

## What Happened

When executing tickets in sprints 028 and 029, the team-lead called
`dispatch_to_code_monkey` directly instead of `dispatch_to_sprint_executor`.

The team-lead's delegation map explicitly says:
- Execute a sprint → `dispatch_to_sprint_executor(...)`

The sprint-executor is the agent that iterates tickets and dispatches
to code-monkey. The team-lead should never call `dispatch_to_code_monkey`
— that's the sprint-executor's job.

But the team-lead called code-monkey directly for every ticket, skipping
the sprint-executor entirely. This means:
- No sprint-executor dispatch log exists
- The sprint-executor never ran
- The sprint-executor's validation (checking all tickets are done,
  updating sprint status) was never performed
- Only one level of dispatch happened instead of two

## What Should Have Happened

For a single ticket:
```
team-lead → dispatch_to_sprint_executor(sprint_id, directory, branch, tickets)
  sprint-executor → dispatch_to_code_monkey(ticket_path, plan_path, ...)
    code-monkey → writes code, returns JSON
  sprint-executor → validates, moves ticket to done
team-lead → receives sprint-executor result
```

Two levels of dispatch, two dispatch logs, proper validation chain.

## Root Cause

**Ignored instruction — convenience shortcut.**

The team-lead has access to `dispatch_to_code_monkey` as an MCP tool.
There's no mechanical restriction preventing it from calling code-monkey
directly. The delegation map says not to, but when there's one ticket
and the goal is simple, it's faster to skip the sprint-executor
intermediary.

This is the same root cause as the prior reflection about using the
Agent tool instead of dispatch tools: the path of least resistance
bypasses the process.

Contributing factors:

1. **The team-lead can see all dispatch tools.** The MCP server exposes
   `dispatch_to_code_monkey` to everyone. There's no tool-level access
   control that says "only sprint-executor can call this tool."

2. **No validation that the caller is appropriate.** The dispatch tool
   doesn't check who's calling it. `dispatch_to_code_monkey` accepts
   the call from anyone — team-lead, sprint-executor, ad-hoc-executor.

3. **Single-ticket sprints feel wasteful.** When there's one ticket,
   dispatching to sprint-executor just to have it dispatch to code-monkey
   feels like unnecessary overhead. The team-lead optimizes for speed.

4. **The team-lead instructions mention code-monkey.** The REMINDER
   section at the end of agent.md says "dispatch_to_code_monkey" as an
   example of a dispatch tool. This implicitly suggests the team-lead
   can call it, even though the delegation map doesn't list it.

## Proposed Fixes

1. **Remove code-monkey from team-lead examples.** The REMINDER section
   should only mention dispatch tools the team-lead actually uses:
   `dispatch_to_sprint_executor`, `dispatch_to_sprint_planner`, etc.
   Not `dispatch_to_code_monkey`.

2. **Add caller validation to dispatch tools.** Each dispatch tool
   could check `CLASI_AGENT_NAME` or `CLASI_AGENT_TIER` and warn
   (or block) when called by an inappropriate agent. For example,
   `dispatch_to_code_monkey` should warn if called by anyone other
   than sprint-executor or ad-hoc-executor.

3. **Make the delegation map a hard constraint.** The contract.yaml
   `delegates_to` field already lists which agents can dispatch to
   which. The dispatch tool could read the caller's contract and
   verify the delegation edge exists before proceeding.

4. **Reinforce in team-lead instructions.** Add an explicit rule:
   "You NEVER call dispatch_to_code_monkey, dispatch_to_architect,
   dispatch_to_architecture_reviewer, dispatch_to_technical_lead, or
   dispatch_to_code_reviewer. Those are internal delegation edges
   used by sprint-planner and sprint-executor. You call the tier 1
   dispatch tools only."
