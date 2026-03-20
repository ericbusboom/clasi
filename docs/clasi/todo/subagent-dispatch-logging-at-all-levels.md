---
status: pending
---

# All Dispatching Agents Must Log Subagent Dispatches

## Problem

The sprint-executor dispatches code-monkey for each ticket during sprint
execution, but it never calls `log_subagent_dispatch` before dispatching
or `update_dispatch_log` after the code-monkey returns. The result is
that the log directory only contains team-lead-level dispatches (e.g.,
team-lead -> sprint-executor, team-lead -> sprint-planner) but none of
the sub-dispatches within sprint execution (sprint-executor ->
code-monkey for ticket 001, ticket 002, etc.).

In sprint 024, the sprint-executor ran code-monkey 8 times across 8
tickets. The log directory for that sprint has only 5 entries — all
sprint-planner dispatches from the planning phase. Zero ticket-level
dispatch logs exist. The stakeholder cannot see what happened during
execution: what prompts were sent to code-monkey, what each returned,
which files each modified.

This is not limited to sprint-executor. The same gap exists for any
dispatching agent that is not the team-lead:

- **sprint-executor** dispatches **code-monkey** for each ticket — not logged
- **sprint-planner** dispatches **architect**, **architecture-reviewer**,
  and **technical-lead** — only logged when the team-lead's dispatch
  prompt explicitly reminds the sprint-planner to do it
- Any future doteam lead that dispatches task-workers will have the
  same gap unless the logging requirement is baked into agent definitions

The logging tools exist (`log_subagent_dispatch`, `update_dispatch_log`)
and the MCP server routes them correctly (sprint_name + ticket_id routes
to `log/sprints/<sprint>/ticket-<ticket>-NNN.md`). The problem is that
the agent definitions for dispatching agents do not include logging as
a required step in their workflow.

## Desired Behavior

Every agent that dispatches a subagent — at any tier — must call
`log_subagent_dispatch` before the dispatch and `update_dispatch_log`
after the subagent returns. This applies regardless of whether the
dispatching agent is team-lead, a doteam lead, or any other agent
that delegates work.

After a sprint execution, the log directory should contain entries for
every dispatch at every level:
- `sprint-planner-NNN.md` — team-lead dispatching sprint-planner
- `architect-NNN.md` — sprint-planner dispatching architect
- `architecture-reviewer-NNN.md` — sprint-planner dispatching reviewer
- `ticket-001-NNN.md` — sprint-executor dispatching code-monkey for ticket 001
- `ticket-002-NNN.md` — sprint-executor dispatching code-monkey for ticket 002
- etc.

## Changes Needed

1. **sprint-executor agent definition** (`claude_agent_skills/agents/
   domain-controllers/sprint-executor/agent.md`) — Add logging as a
   mandatory step in the per-ticket workflow. Before step 3c (dispatch
   code-monkey), call `log_subagent_dispatch` with the sprint name and
   ticket ID. After step 3d (validate the ticket), call
   `update_dispatch_log` with the result and files modified. Add a rule:
   "Always log every code-monkey dispatch using `log_subagent_dispatch`
   and `update_dispatch_log`."

2. **sprint-planner agent definition** (`claude_agent_skills/agents/
   domain-controllers/sprint-planner/agent.md`) — Add logging as a
   mandatory step before and after each delegation (architect,
   architecture-reviewer, technical-lead). Add a rule: "Always log
   every subagent dispatch."

3. **dispatch-subagent skill** (`claude_agent_skills/skills/
   dispatch-subagent.md`) — If a generic dispatch skill exists, it
   should include logging as a mandatory step. Any agent following the
   dispatch skill should automatically log.

4. **Any other dispatching agent definitions** — Audit all agents in
   `claude_agent_skills/agents/` that have a "What You Delegate"
   section. Each one must include logging instructions in its workflow.

5. **Consider a universal rule** — Add a project-level rule (in
   `.claude/rules/` or AGENTS.md) stating: "Every subagent dispatch
   must be logged. Call `log_subagent_dispatch` before dispatching and
   `update_dispatch_log` after the subagent returns. No exceptions."
