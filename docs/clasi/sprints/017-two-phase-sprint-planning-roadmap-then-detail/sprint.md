---
id: "017"
title: "Two-phase sprint planning: roadmap then detail"
status: roadmap
branch: sprint/017-two-phase-sprint-planning-roadmap-then-detail
use-cases: []
source-todos:
  - two-phase-sprint-planning-roadmap-then-detail.md
---

# Sprint 017: Two-phase sprint planning: roadmap then detail

## Goals

Implement the two-phase sprint planning model in CLASI's MCP tooling so
that roadmap-first planning (batch, lightweight) and detail planning (single
sprint, full artifacts) are first-class operations, not workarounds.

After this sprint, `create_sprint` produces only `sprint.md` with
`status: roadmap` by default. A new `detail_sprint(sprint_id)` tool promotes a
roadmap sprint to a fully-scaffolded detail sprint. Agents and skills stop
fighting the tools.

## Problem

CLASI's `plan-sprint` skill and `sprint-planner` agent already document the
two-phase model, but the underlying MCP tooling ignores it. `create_sprint`
always scaffolds the full artifact set (sprint.md, usecases.md,
architecture-update.md, tickets/, tickets/done/) in one shot. There is no
way to create a roadmap-only sprint through the tools.

As a consequence, roadmap-first sessions require a manual workaround: the
sprint-planner creates sprints with the full scaffold and then manually deletes
the extra artifacts to simulate roadmap mode. This is the exact workaround
applied in the dispatch that created this roadmap (sprints 017-022). The
`detail_sprint` tool does not exist, so transitioning from roadmap to detail
planning has no gated, tool-enforced path.

## Solution outline

- Modify `create_sprint` to produce only `sprint.md` with `status: roadmap`.
  No usecases.md, no architecture-update.md, no tickets/ directory.
- Add a `roadmap` phase as the new first phase in the CLASI state machine.
  Phase order becomes: `roadmap -> planning-docs -> architecture-review ->
  stakeholder-review -> ticketing -> executing -> closing -> done`.
- Implement `detail_sprint(sprint_id)` as a new MCP tool. It validates the
  sprint is in `roadmap` phase, scaffolds the missing artifacts, and advances
  the phase to `planning-docs`.
- Update `list_sprints` to support `status="roadmap"` filtering.
- Update skill prose (`plan-sprint`, `sprint-planner`, `sprint-roadmap`,
  `team-lead`) to reflect the actual tool-level two-phase flow without
  contradictions.
- Add tests covering the new lifecycle: lightweight create, detail promotion,
  rejection of non-roadmap sprints, roadmap filtering.

## Success criteria

- `create_sprint(title=...)` produces exactly one file (`sprint.md`) with
  `status: roadmap`. No other artifacts. No `tickets/` directory.
- `detail_sprint(sprint_id)` scaffolds the full artifact set and advances the
  state-DB phase to `planning-docs`. Calling it on an already-detail-planned
  sprint returns a clear error (no silent partial re-scaffold).
- `list_sprints(status="roadmap")` returns only roadmap sprints. Default
  `list_sprints()` returns all statuses.
- A roadmap sprint cannot be advanced to `architecture-review` or later without
  going through `detail_sprint` first. The state machine enforces this.
- Skill and agent prose for `plan-sprint`, `sprint-planner`, `sprint-roadmap`,
  and `team-lead` match the actual tool-level two-phase flow with no
  contradictions between documented model and enforced transitions.
- Tests cover the new transitions; existing test suite stays green.

## In Scope

- `clasi/project.py` and/or `clasi/sprint.py`: modify `create_sprint` to
  produce roadmap-only output.
- `clasi/state_db_class.py`: add `roadmap` as the first phase in `PHASES`.
- `clasi/tools/artifact_tools.py`: new `detail_sprint(sprint_id)` MCP tool.
- `clasi/templates.py`: split sprint.md template from usecases /
  architecture-update templates so `create_sprint` can render only `sprint.md`.
- Skill and agent prose updates: `plan-sprint`, `sprint-planner`,
  `sprint-roadmap`, `team-lead`.
- Unit and system tests for the new lifecycle.

## Out of Scope

- Backfilling existing `done/` sprints into the new schema. They keep their
  current shape.
- Migrating the in-flight sprint 016 (created under the old one-shot model)
  into the new shape. Sprint 016 ships as-is.
- Roadmap dashboards or visualizations.
- Any GUI or non-MCP interface to the two-phase model.

## Dependencies and sequencing

This sprint is EARLY PRIORITY. Nearly every subsequent roadmap sprint
benefits from having the two-phase tooling in place before its own
detail-planning run. Specifically:

- Sprint 018 (lower-agent exception protocol), sprint 019 (clasr uninstall
  fix), sprint 020 (schema-driven workflow), sprint 021 (integration
  registry), and sprint 022 (worktree process) should all be detail-planned
  using the new `detail_sprint` tool after this sprint lands.
- No upstream dependencies. Sprint 016 must be closed first (it is in-flight
  under the old model), but 017 does not share any surface with 016.
- Independent of all other roadmap entries in this batch.

## Source TODOs

- `docs/clasi/todo/two-phase-sprint-planning-roadmap-then-detail.md`

## Tickets

| # | Title | Depends On |
|---|-------|------------|
