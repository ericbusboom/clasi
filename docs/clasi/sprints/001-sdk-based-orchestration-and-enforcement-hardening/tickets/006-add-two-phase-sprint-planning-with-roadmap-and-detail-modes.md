---
id: '006'
title: Add two-phase sprint planning with roadmap and detail modes
status: todo
use-cases:
  - SUC-008
depends-on:
  - '002'
github-issue: ''
todo: sdk-orchestration-cluster/team-lead-parallel-sprint-planning.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add two-phase sprint planning with roadmap and detail modes

## Description

Introduce a two-phase sprint planning model that separates lightweight
roadmap planning (batch, multiple sprints at once) from detailed
planning (one sprint at a time, pre-execution). This allows the
team-lead to plan multiple sprints ahead at a high level while deferring
detailed artifacts until each sprint is about to execute.

### dispatch_to_sprint_planner Mode Parameter

Update `dispatch_to_sprint_planner` to accept a `mode` parameter with
two values:

- **"roadmap"** -- Produces a lightweight `sprint.md` only, containing
  goals, feature scope, and TODO references. No use cases, no
  architecture document, no tickets. All planning happens on main
  (no branch created). The dispatch tool validates against a
  roadmap-specific contract return schema.

- **"detail"** -- Produces full planning artifacts: `usecases.md`,
  `technical-plan.md`, and tickets. The sprint-planner dispatches to
  the architect (SUC-002) for the architecture document. The dispatch
  tool validates against the detail-specific contract return schema
  (all required files exist, frontmatter correct, at least one ticket
  created). Also happens on main -- no branch yet.

### Sprint-Planner Contract Update

Update the sprint-planner's `contract.yaml` to declare mode-specific
outputs and return schemas. The contract should have separate validation
rules for roadmap vs. detail mode, so the dispatch tool knows what to
validate for each.

### Late Branching via acquire_execution_lock

Update `acquire_execution_lock` to create the sprint branch
(`git checkout -b sprint/NNN-slug`). Branches are only created when
execution begins, not during planning. This ensures all planning
(both roadmap and detail phases) happens on main, and only the sprint
about to execute gets a branch.

### Skill and Agent Documentation Updates

- Update the `plan-sprint` skill definition to document the two-phase
  model: use roadmap mode for batch planning, detail mode for
  pre-execution planning.
- Update `team-lead` agent.md to describe batch roadmap planning
  (plan multiple sprints in one session using roadmap mode).

## Acceptance Criteria

- [ ] `dispatch_to_sprint_planner` accepts a `mode` parameter ("roadmap" or "detail")
- [ ] Roadmap mode validates: `sprint.md` exists with goals, scope, and TODO references
- [ ] Detail mode validates: full artifact set with at least one ticket
- [ ] Sprint-planner contract has mode-specific outputs and return schemas
- [ ] `acquire_execution_lock` creates the sprint branch (late branching)
- [ ] `plan-sprint` skill documents the two-phase model
- [ ] `team-lead` agent.md describes batch roadmap planning
- [ ] Unit tests for mode parameter validation

## Testing

- **Existing tests to run**: `tests/test_dispatch_tools.py` (dispatch_to_sprint_planner changes), `tests/test_artifact_tools.py` (acquire_execution_lock changes)
- **New tests to write**: Tests in `tests/test_dispatch_tools.py` for: mode parameter validation (roadmap vs. detail), roadmap mode validates only sprint.md, detail mode validates full artifact set, missing mode parameter defaults or errors appropriately
- **Verification command**: `uv run pytest`
