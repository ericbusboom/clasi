---
status: pending
type: task
tags:
- reliability-campaign
- phase-3
- process-docs
---

# One canonical text per process topic; stop routing agents into retired machinery

## Description

From the reliability review's process pass
(docs/reviews/2026-08-reliability/06-process-flow.md, findings 2 and 3,
plus its 20-row doc/code contradiction table). Process text lives in up
to four diverging copies per topic, and two of those copies actively
route agents into machinery that no longer exists.

**The two live traps — fix these first:**

1. `.claude/rules/source-code.md` — loaded on **every source edit** —
   tells agents to "follow the execute-ticket skill." No such skill
   exists. `get_skill_definition`'s `rglob` fallback
   (`src/clasi/tools/process_tools.py:120-124`) resolves it into
   `src/clasi/plugin/agents/old/sprint-executor/execute-ticket.md`, a
   retired process that mandates a full `uv run pytest` per ticket, a
   code-monkey dispatch, and a per-ticket two-stage review — precisely
   the ceremony the scoped-test discipline replaced.
2. `src/clasi/plugin/skills/dispatch-subagent/SKILL.md` says "you MUST
   call `log_subagent_dispatch`… If unavailable or fails, STOP. Do not
   dispatch without logging." That MCP tool does not exist anywhere in
   `src/clasi/`. Followed literally, every dispatch dead-ends.

**The duplication, which is what lets traps like those form:** plan-sprint
exists in four forms (skill wrapper, `$S` instruction, a stale
`agents/sprint-planner/plan-sprint.md`, and agent.md's inline workflow);
create-tickets, tdd-cycle, and systematic-debugging all have agent-local
copies that differ from their skills; the installed
`.claude/agents/team-lead/agent.md` has drifted ahead of the plugin
source, so the next plugin sync would regress the live process.
`plugin/instructions/software-engineering.md` — the largest instruction
file — describes a retired seven-agent roster with a per-ticket
code-reviewer and mandatory separate `-plan.md` files.

Also mismatched between docs and code: `move_ticket_to_done(sprint_id,
ticket_id)` vs its real single-`path` signature, and
`reconcile_worktrees(repo_root, sprint_dir)` vs `reconcile_worktrees(sprint_id)`.

## Acceptance criteria

- [ ] `src/clasi/plugin/agents/old/` is excluded from
      `get_skill_definition`/`get_agent_definition` lookup, so no
      fallback can resolve into retired process text. A test asserts a
      lookup for a nonexistent skill fails loudly rather than silently
      resolving into `old/`.
- [ ] `.claude/rules/source-code.md` (and its canonical source in
      `src/clasi/platforms/_rules.py`) points at the programmer agent
      definition instead of the nonexistent execute-ticket skill.
- [ ] `dispatch-subagent` is either rewritten to match reality or
      retired; no shipped skill mandates a tool that does not exist.
- [ ] One canonical file per process topic; agent definitions carry a
      pointer, not a copy. Stale agent-local duplicates deleted.
- [ ] The installed team-lead agent.md and the plugin source agree
      (whichever is newer wins, deliberately).
- [ ] `software-engineering.md` is rewritten to the real 3-agent process
      or reduced to a pointer page.
- [ ] Tool signatures named in docs match the code — verified by a test
      that introspects the MCP tool signatures rather than by reading.

## Why it matters

Every one of these is a live instance of the review's root cause RC-5:
dead machinery still wired into live instructions. An agent that follows
the docs correctly gets blocked or dead-ends, and the failure looks like
a mysterious mid-sprint problem rather than a stale document.
