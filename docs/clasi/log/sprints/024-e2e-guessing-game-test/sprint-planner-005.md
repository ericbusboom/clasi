---
timestamp: '2026-03-20T01:27:36'
parent: team-lead
child: sprint-executor
scope: docs/clasi/sprints/024-e2e-guessing-game-test/, tests/e2e/, claude_agent_skills/,
  CLAUDE.md, AGENTS.md
sprint: 024-e2e-guessing-game-test
---

# Dispatch: team-lead → sprint-executor

You are the **sprint-executor** agent. Execute all 8 tickets for sprint 024 "E2E Test and Process Improvements".

Read the sprint docs at `docs/clasi/sprints/024-e2e-guessing-game-test/` to understand the full scope. Read each ticket before executing it.

Two tracks can run in parallel since they don't share files:
- Track 1 (E2E): tickets 001, 002, 003 (003 depends on 001+002)
- Track 2 (Process): tickets 004, 005, 006, 007 (007 depends on 006), 008

For each ticket:
1. Read the ticket
2. Dispatch code-monkey to implement it
3. Validate the code-monkey's output: check ticket frontmatter is updated to done, acceptance criteria checked off
4. Move completed ticket to tickets/done/

After all tickets are done, update sprint.md status to active, then to done.

IMPORTANT: Use `log_subagent_dispatch` MCP tool BEFORE each code-monkey dispatch, and `update_dispatch_log` AFTER each returns.

Working directory: /Volumes/Proj/proj/RobotProjects/scratch/claude-agent-skills
Branch: sprint/024-e2e-guessing-game-test

Run tests after code changes: `uv run pytest -p no:cacheprovider --override-ini="addopts="`

Commit after each ticket.
