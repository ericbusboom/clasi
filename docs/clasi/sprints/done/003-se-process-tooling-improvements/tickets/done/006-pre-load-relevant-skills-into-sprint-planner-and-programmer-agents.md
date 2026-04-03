---
id: '006'
title: Pre-load relevant skills into sprint-planner and programmer agents
status: done
use-cases: []
depends-on:
- '005'
github-issue: ''
todo: preload-skills-into-subagents.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Pre-load relevant skills into sprint-planner and programmer agents

## Description

Currently the sprint-planner and programmer agents discover skills at runtime via
the team-lead's dispatch prompt or by reading `.claude/skills/`. This is fragile —
the agent may not find the right skill, or may re-derive process steps that a skill
already encodes.

This ticket inlines core skill content directly into each agent's `agent.md` so it
is available from the start of every subagent session, making the agents
self-contained and reliable. Less critical skills are referenced by name only to
keep the files readable.

After ticket 005 completes, agent files live at `clasi/plugin/agents/<name>/agent.md`.
This ticket edits them at that new location.

**Sprint-planner agent.md** changes:
- Inline the roadmap vs. detail mode distinction from `plan-sprint` (~15 lines)
- Inline the 7-step architecture-authoring methodology into Phase 2 (~25 lines)
- Inline the architecture-review checklist into Phase 3 (~20 lines)
- Reference-only mentions for `create-tickets` and `consolidate-architecture`

**Programmer agent.md** changes:
- Replace the current Error Recovery section with the `systematic-debugging`
  4-phase protocol and 3-attempt cap
- Reference-only mentions for `code-review` and `tdd-cycle`

## Acceptance Criteria

- [x] Sprint-planner `agent.md` includes the roadmap/detail mode distinction inlined from `plan-sprint`
- [x] Sprint-planner `agent.md` includes the architecture authoring 7-step methodology in Phase 2
- [x] Sprint-planner `agent.md` includes the architecture self-review checklist in Phase 3
- [x] Sprint-planner `agent.md` references (does not inline) `create-tickets` and `consolidate-architecture`
- [x] Programmer `agent.md` includes the `systematic-debugging` 4-phase protocol with 3-attempt escalation cap
- [x] Programmer `agent.md` references (does not inline) `code-review` and `tdd-cycle`
- [x] `uv run pytest` passes with no failures

## Implementation Plan

### Approach

Read the source skill files to extract the relevant sections, then edit each
agent.md to splice in the content at the appropriate phase headings. Keep inlined
content concise — prefer structured lists and numbered steps over prose. Use
"Reference only" callouts for skills not inlined.

### Files to Create or Modify

- `clasi/plugin/agents/sprint-planner/agent.md` — inline plan-sprint modes,
  architecture-authoring steps, architecture-review checklist; add reference
  callouts for create-tickets and consolidate-architecture
- `clasi/plugin/agents/programmer/agent.md` — replace Error Recovery section with
  systematic-debugging 4-phase protocol + 3-attempt cap; add reference callouts
  for code-review and tdd-cycle

Source skill files to read (do not modify):
- `clasi/plugin/skills/plan-sprint.md`
- `clasi/plugin/skills/architecture-authoring.md`
- `clasi/plugin/skills/architecture-review.md`
- `clasi/plugin/skills/systematic-debugging.md`

### Testing Plan

- `uv run pytest` to confirm no test regressions.
- Manually review agent.md files to confirm inlined content is coherent and
  the file remains readable (not unwieldy).

### Documentation Updates

No separate documentation updates. The agent.md files are themselves the
documentation for the agents.
