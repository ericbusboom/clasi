---
status: in-progress
sprint: '017'
tickets:
- 017-001
---

# Two-phase sprint planning: roadmap then detail

## Context

CLASI's `plan-sprint` skill and `sprint-planner` agent already document a two-phase planning model:

- **Phase 1 — Roadmap**: lightweight `sprint.md` for many sprints upfront (goals, scope, TODO references; no use-cases, no architecture, no tickets).
- **Phase 2 — Detail**: full planning artifacts for one sprint just before execution (use-cases, architecture-update, tickets, gates).

But the underlying implementation silently ignores this distinction. The MCP tool `mcp__clasi__create_sprint` always scaffolds the **full** artifact set (sprint.md, usecases.md, architecture-update.md, tickets/, tickets/done/) in one shot — there is no way to create a "roadmap-only" sprint. As a result, the documented two-phase flow is impossible to execute through the tools, and sprint-planner agents have been doing one-shot planning even when the user expects roadmap-first.

This was just hit in practice: the user asked for "roadmap planning of all the sprints, then we review, then detail-plan one." The team-lead invented a `docs/clasi/sprints/draft/` holding pen — a process violation. The right fix is to make CLASI's documented two-phase model actually work in the tools.

## Outcome

- `create_sprint` produces a lightweight, roadmap-only sprint by default (`sprint.md` only, `status: roadmap`).
- A new `detail_sprint(sprint_id)` MCP tool transitions a roadmap sprint into detail-planning by scaffolding the rest of the artifacts and advancing the phase.
- The phase machine adds `roadmap` as its new first phase: `roadmap → planning-docs → architecture-review → stakeholder-review → ticketing → executing → closing → done`.
- `list_sprints(status="roadmap")` works.
- The `plan-sprint` skill, `sprint-planner` agent, and `sprint-roadmap` skill stop fighting the tools.

## Action: capture as a TODO

This change has architecture impact (phase machine, MCP surface, state DB) and should go through the normal CLASI sprint flow. The plan is to capture it as a TODO at:

`docs/clasi/todo/two-phase-sprint-planning-roadmap-then-detail.md`

When picked up for sprint planning, the resulting sprint will implement the changes described below.

## Locked-in decisions (from AskUserQuestion this turn)

1. **Roadmap shape**: `create_sprint` writes ONLY `sprint.md` with `status: roadmap` frontmatter. No `usecases.md`, no `architecture-update.md`, no `tickets/` dir. Detail-promotion adds those.
2. **Roadmap → Detail transition**: explicit new MCP tool `detail_sprint(sprint_id)`. It reads the lightweight sprint.md, scaffolds the missing artifacts (usecases.md, architecture-update.md, tickets/ + tickets/done/), and updates state-DB phase from `roadmap` to `planning-docs`.
3. **Phase machine**: add `roadmap` as the new first phase. Sprints register at `roadmap` on `create_sprint`. `detail_sprint` advances them to `planning-docs`. Existing transitions from `planning-docs` onward are unchanged.
4. **Listing**: `list_sprints(status="roadmap")` returns roadmap sprints. Default `list_sprints()` includes all states. No new dedicated `list_roadmap` tool.

## Surface area to change (when this work runs as a sprint)

**Python source**

- `clasi/sprint.py` and/or `clasi/project.py` — `create_sprint` no longer writes usecases.md, architecture-update.md, or tickets/ subdirs by default. Sprint.md frontmatter gets `status: roadmap`.
- New module / method: `Sprint.detail_promote()` (or equivalent). Reads roadmap sprint.md, writes the rest of the artifact set from templates, touches state DB.
- `clasi/state_db_class.py` — `PHASES` constant gets `roadmap` prepended. Phase-transition validation accepts `roadmap → planning-docs` via `detail_sprint`.
- `clasi/tools/artifact_tools.py` — new `@server.tool() detail_sprint(sprint_id)`. Validates: sprint exists, is in `roadmap` phase, has only `sprint.md`. Errors clearly otherwise.
- `clasi/templates.py` or wherever the templates live — split the sprint.md template from the usecases / architecture-update templates so create_sprint can render only sprint.md.

**Skills and agents**

- `clasi/plugin/skills/plan-sprint/SKILL.md` — already documents the two-phase model. Just verify the prose now matches the implementation. Update any line that implied `create_sprint` was the detail call.
- `clasi/plugin/agents/sprint-planner/agent.md` — same. The agent already has Roadmap Mode and Detail Mode; tighten the language about which MCP tools each mode calls.
- `clasi/plugin/skills/sprint-roadmap/SKILL.md` — currently calls `create_sprint`, then writes a "lightweight" sprint.md over the bloated default. After the fix, it just calls the new lightweight `create_sprint` and writes content. Drop the workaround steps.
- `clasi/plugin/agents/team-lead/agent.md` — when surveying the queue, distinguish roadmap sprints (preview-only, not yet ready to execute) from detail-planned sprints (ready or in flight).

**Tests**

- `tests/unit/test_sprint.py`, `test_project.py` — `create_sprint` produces only sprint.md.
- New tests for `detail_sprint`: round-trip from roadmap-only sprint → fully scaffolded sprint; rejects non-roadmap sprints; rejects sprint that already has usecases.md.
- `tests/unit/test_state_db_class.py` (if present) — `roadmap` is in PHASES; transitions validated.
- `tests/system/test_artifact_tools.py` — new MCP tool registered, lifecycle test.

## Acceptance criteria for the future sprint

- `create_sprint(title=...)` produces a single `sprint.md` file with `status: roadmap`. No other files. No `tickets/` dir.
- `detail_sprint(sprint_id="NNN")` scaffolds usecases.md, architecture-update.md, tickets/, tickets/done/, and advances state-DB phase to `planning-docs`. Idempotent on already-detail-planned sprints (no-op or clear error).
- `list_sprints(status="roadmap")` returns roadmap sprints; default returns all.
- `mcp__clasi__create_sprint` cannot create a fully-scaffolded sprint in one shot. Hard cut.
- `plan-sprint` skill text and `sprint-planner` agent prompt both reflect the actual two-phase tool flow without contradictions.
- Tests cover the new transitions and the lightweight create.
- A roadmap sprint cannot be advanced to `architecture-review` (or any later phase) without going through `detail_sprint` first.

## Out of scope

- Backfilling existing `done/` sprints into the new schema. They keep their current shape.
- Migrating the in-flight sprint 016 (which was created under the old one-shot model) into the new shape mid-sprint. Sprint 016 ships as-is.
- Designing the user-experience for "roadmap dashboards" or visualizations. Future concern.

## Why this is a TODO and not a direct edit

Three reasons:

1. **Architecture impact**: changing `PHASES`, adding a new MCP tool, splitting templates, and updating multiple skills is sprint-shaped work, not an inline change.
2. **Sprint 016 is already mid-planning under the old model.** Fixing the planning machinery while sprint 016 is using it would create an unstable target. Land 016 first; then this work.
3. **The user wanted to plan the next round of sprints with two-phase planning before this fix lands.** The pragmatic answer for the *current* run is: have the sprint-planner agent simulate the two-phase model manually (write only sprint.md for several sprints upfront, then return to detail-plan one), even though the underlying tool is bloated. That's an unrelated immediate action — not part of this TODO.

## Files to read for context (when planning the future sprint)

- `clasi/project.py` — `create_sprint` location.
- `clasi/sprint.py` — Sprint class; archive/state methods are the pattern to follow for `detail_promote`.
- `clasi/state_db_class.py:17-25` — `PHASES` constant.
- `clasi/templates.py` — current monolithic template generation.
- `clasi/plugin/skills/plan-sprint/SKILL.md` — existing two-phase prose.
- `clasi/plugin/agents/sprint-planner/agent.md` — existing two-phase prose.
- `clasi/plugin/skills/sprint-roadmap/SKILL.md` — current workaround in skill form.

## Verification (when the future sprint runs)

End-to-end smoke after implementation:

```
clasi  # MCP server up
# Roadmap phase: plan five sprints
mcp__clasi__create_sprint(title="Sprint A")  # only sprint.md written
mcp__clasi__create_sprint(title="Sprint B")
mcp__clasi__create_sprint(title="Sprint C")
mcp__clasi__list_sprints(status="roadmap")  # returns A, B, C
# Pick A for detail planning
mcp__clasi__detail_sprint(sprint_id="<A's id>")  # scaffolds rest
mcp__clasi__get_sprint_phase(sprint_id="<A's id>")  # returns planning-docs
# B and C still at roadmap
```

Existing test suite stays green; new tests cover the lightweight-create behavior, `detail_sprint` round trip, and `roadmap` phase validity.
