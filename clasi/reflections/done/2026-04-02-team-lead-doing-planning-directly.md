---
date: 2026-04-02
sprint: "002"
category: ignored-instruction
---

# Team-Lead Doing Sprint Planning Directly Instead of Dispatching

## What Happened

Throughout sprints 001 and 002, the team-lead agent performed all sprint
planning work directly: creating sprints, filling in sprint.md and
architecture-update.md, creating tickets, advancing phases, recording
gates. None of this was dispatched to a sprint-planner agent (Tier 1).

This is the same class of violation as writing source code directly
instead of dispatching to a programmer — but for planning work. The
team-lead should dispatch to sprint-planner for all planning artifact
creation, just as it dispatches to programmer for all code changes.

The result: no sprint-planner logs exist. The process appears to have
only two actors (team-lead + programmer) when it should have three
(team-lead + sprint-planner + programmer).

## What Should Have Happened

When the stakeholder requests a sprint or tickets:
1. Team-lead creates the sprint via MCP tools (this is fine — it's a
   process operation, not artifact authoring)
2. Team-lead dispatches to sprint-planner agent to fill in sprint.md,
   architecture-update.md, usecases.md, and ticket descriptions
3. Sprint-planner writes the planning docs and returns
4. Team-lead advances phases and records gates
5. Team-lead dispatches to programmer agents for execution

## Root Cause

**Ignored instruction.** The agent hierarchy is documented in the team-lead
agent.md and the CLASI specification. The team-lead knows about the
sprint-planner tier but has been bypassing it because:

1. The planning work felt "small" — just filling in templates
2. There was no enforcement mechanism — the role guard blocks code edits
   but doesn't block the team-lead from writing planning docs (until
   ticket 002-002 added the sprint directory block, but that only blocks
   Edit/Write, not MCP tool usage which creates the files)
3. The team-lead conflated "orchestrating the process" with "doing the
   work" — MCP tools create the files, but the content (sprint goals,
   architecture notes, ticket descriptions) should come from the
   sprint-planner

## Proposed Fix

1. Add explicit instructions to team-lead agent.md stating that after
   creating a sprint via MCP tools, the sprint-planner agent MUST be
   dispatched to fill in planning document content.
2. Add this as a feedback memory so future sessions follow the pattern.
3. The dispatch pattern should be:
   - Team-lead: `create_sprint(title)` → creates skeleton
   - Dispatch sprint-planner: "Fill in sprint.md, architecture-update.md,
     usecases.md for sprint 002 based on these TODOs: ..."
   - Sprint-planner returns with docs filled in
   - Team-lead: `record_gate_result`, `advance_sprint_phase`
   - Team-lead: dispatch sprint-planner for ticket creation
   - Sprint-planner: fills in ticket descriptions
   - Team-lead: dispatch programmers for execution
