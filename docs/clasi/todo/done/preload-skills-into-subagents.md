---
status: done
sprint: '003'
tickets:
- 003-006
---

# Pre-load relevant skills into sprint-planner and programmer agent definitions

Currently the sprint-planner and programmer agents discover skills at runtime by
reading `.claude/skills/` or being told about them in the team-lead's dispatch
prompt. This is fragile — the agent may not find the right skill, or may
re-derive process steps that a skill already defines.

Instead, inline or reference the relevant skill content directly in each agent's
`agent.md` so it's available from the start of the subagent session.

## Sprint-planner

Should have pre-loaded:
- `plan-sprint` — the roadmap + detail planning process
- `create-tickets` — ticket decomposition and sequencing
- `architecture-authoring` — how to write architecture updates
- `architecture-review` — self-review criteria
- `consolidate-architecture` — when/how to consolidate

## Programmer

Should have pre-loaded:
- `code-review` — self-review before marking done
- `tdd-cycle` — red-green-refactor workflow (when applicable)
- `systematic-debugging` — structured debugging protocol for test failures

## Approach

Either append the skill content directly into the agent.md (keeps it self-contained)
or use a reference/include pattern if the agent framework supports it. Keep the
agent.md readable — summarize or link rather than dumping full skill text if it
would make the file unwieldy.
