---
id: "012-004"
title: Reconcile planning-docs vocabulary in plugin docs and sprint state machine YAML
status: open
use-cases: [SUC-005]
depends-on: ["012-001"]
issue:
- gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md
---

# 012-004: Reconcile planning-docs vocabulary in plugin docs and sprint state machine YAML

## Description

The sprint-planner uses `planning_docs` (underscore) in some plugin documents as the
`status` value set in `sprint.md` frontmatter after `detail_sprint` runs. However, the
state DB uses `planning-docs` (hyphen) as the phase string. This mismatch means
`get_status` reports `state_drift` for sprints in the planning-docs phase because the
declared `status` in `sprint.md` doesn't match the computed state.

This ticket fixes the underscore/hyphen mismatch in `clasi/plugin/...` source-of-truth
files, and updates the sprint state machine YAML predicate descriptions to reference
`.clasi/` paths instead of `docs/clasi/`.

Note: the DB (`state_db_class.py`) and state machine YAML (`schemas/state-machines/sprint.yaml`)
already have `planning-docs` correctly. Only the agent/skill docs need fixing.

## Acceptance Criteria

- [ ] `clasi/plugin/agents/sprint-planner/dispatch-template.md.j2` line 55: `planning_docs` → `planning-docs`.
- [ ] `clasi/plugin/agents/sprint-planner/contract.yaml` line 58: `planning_docs` → `planning-docs`.
- [ ] `clasi/plugin/agents/sprint-planner/plan-sprint.md`: all `planning_docs` (underscore) occurrences changed to `planning-docs` (hyphen).
- [ ] Sprint state machine YAML `clasi/schemas/state-machines/sprint.yaml` predicate/action descriptions: `docs/clasi/sprints/<id>/` references updated to `.clasi/sprints/<id>-<slug>/`.
- [ ] After fix, a sprint in `planning-docs` DB phase does not generate a `state_drift` inconsistency due to vocabulary mismatch.
- [ ] `pytest` passes (no regressions).

## Implementation Plan

### Approach

Pure text substitutions in plugin docs and the schema YAML. No Python code changes.

### Files to Modify

**`clasi/plugin/agents/sprint-planner/dispatch-template.md.j2`** — line 55:
- Change: `status: planning_docs` → `status: planning-docs`

**`clasi/plugin/agents/sprint-planner/contract.yaml`** — line 58:
- Change: `status: planning_docs` → `status: planning-docs`

**`clasi/plugin/agents/sprint-planner/plan-sprint.md`** — audit all occurrences:
- Search for `planning_docs` (underscore) and replace with `planning-docs` (hyphen).
- Expected locations: line ~89 (`Set frontmatter status: planning_docs`), line ~98 (phase references).

**`clasi/schemas/state-machines/sprint.yaml`** — update stale path references in predicate/action descriptions:
- `is_sprint_doc_present` description: `docs/clasi/sprints/<id>/sprint.md` → `.clasi/sprints/<id>-<slug>/sprint.md`
- `is_architecture_present` description: update similarly
- `is_usecases_present` description: update similarly
- `is_close_report_present` description: update similarly
- `is_at_least_one_ticket` description: update similarly
- `write_tickets` action description: update similarly
- These are documentation strings only; they do not affect runtime behavior.

### Testing Plan

No new tests required. Run:
```
grep -r "planning_docs" clasi/plugin/agents/sprint-planner/
```
Should return no matches after the fix.

Run `pytest` to confirm no regressions.

### Documentation Updates

The changes in this ticket ARE the documentation updates.
