---
id: "009"
title: "Subagent dispatch logging at all levels"
status: done
use-cases: [SUC-003]
depends-on: []
github-issue: ""
todo: "subagent-dispatch-logging-at-all-levels.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Subagent dispatch logging at all levels

## Description

The sprint-executor dispatches code-monkey for each ticket during sprint
execution, but never calls `log_subagent_dispatch` before dispatching or
`update_dispatch_log` after the code-monkey returns. The sprint-planner
has the same gap when dispatching architect, architecture-reviewer, and
technical-lead. The result is that dispatch logs only contain team-lead-
level dispatches, missing all sub-dispatches within sprint execution and
planning.

In sprint 024, the sprint-executor ran code-monkey 8 times across 8
tickets, but the log directory has zero ticket-level dispatch log
entries. The stakeholder cannot see what happened during execution: what
prompts were sent to code-monkey, what each returned, or which files
each modified.

This ticket adds mandatory dispatch logging to every agent that
dispatches subagents, at every tier.

### Changes

#### 1. Sprint-executor agent definition

Update `claude_agent_skills/agents/domain-controllers/sprint-executor/
agent.md` to add logging as a mandatory step in the per-ticket workflow.
Before dispatching code-monkey, call `log_subagent_dispatch` with the
sprint name and ticket ID. After the code-monkey returns, call
`update_dispatch_log` with the result and files modified. Add a rule:
"Always log every code-monkey dispatch using `log_subagent_dispatch`
and `update_dispatch_log`."

#### 2. Sprint-planner agent definition

Update `claude_agent_skills/agents/domain-controllers/sprint-planner/
agent.md` to add logging as a mandatory step before and after each
delegation (architect, architecture-reviewer, technical-lead). Add a
rule: "Always log every subagent dispatch."

#### 3. Dispatch-subagent skill

If a generic dispatch skill exists (`claude_agent_skills/skills/
dispatch-subagent.md`), include logging as a mandatory step so that any
agent following the dispatch skill automatically logs.

#### 4. Audit all dispatching agents

Audit all agents in `claude_agent_skills/agents/` that have a "What You
Delegate" section. Each one must include logging instructions in its
workflow.

#### 5. Universal dispatch logging rule

Add a project-level rule (in `.claude/rules/` or AGENTS.md) stating:
"Every subagent dispatch must be logged. Call `log_subagent_dispatch`
before dispatching and `update_dispatch_log` after the subagent returns.
No exceptions."

## Acceptance Criteria

- [x] Sprint-executor agent definition includes mandatory `log_subagent_dispatch` / `update_dispatch_log` calls around each code-monkey dispatch
- [x] Sprint-planner agent definition includes mandatory logging around each subagent dispatch (architect, architecture-reviewer, technical-lead)
- [x] Dispatch-subagent skill includes logging as a mandatory step (if the skill exists)
- [x] All agents with a "What You Delegate" section have been audited and include logging instructions
- [x] A project-level rule enforces dispatch logging for all agents at all tiers
- [x] After a sprint execution, log directories contain entries for every dispatch at every level (team-lead, domain-controller, and task-worker tiers)
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Manual verification: Run a sprint and confirm dispatch logs exist for all tiers
  - Verify sprint-executor logs contain one entry per ticket dispatched to code-monkey
  - Verify sprint-planner logs contain entries for architect, architecture-reviewer, and technical-lead dispatches
- **Verification command**: `uv run pytest`
