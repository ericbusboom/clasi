---
id: '003'
title: Agent-scope narrowing for sprint-planner and programmer views
status: done
use-cases:
- SUC-003
- SUC-004
depends-on:
- '002'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Agent-scope narrowing for sprint-planner and programmer views

## Description

The full status dict built by ticket 002 is the team-lead view. Sprint-planner
and programmer need narrowed views: sprint-planner sees the project block plus
one sprint (tickets summarized, no details); programmer sees the project block,
the parent sprint in summary form, and one ticket's full detail.

This ticket implements `clasi/status/narrowing.py` and wires `narrow_status`
into `clasi/status/__init__.py`. It also implements the fallback rules when a
required argument is missing (e.g., sprint-planner called without `--sprint`).

## Acceptance Criteria

- [x] `clasi/status/narrowing.py` defines `narrow_status(full, agent, sprint_id, ticket_id) -> dict`.
- [x] `narrow_status` for `agent="team-lead"` returns `full` unchanged.
- [x] `narrow_status` for `agent="sprint-planner"` with `sprint_id` provided:
  - Keeps `project:` block unchanged.
  - Keeps only the matching sprint entry under `sprints:`.
  - That sprint's `tickets:` has `total` and `by_state` but no `details:` list.
  - `notes:` is recomputed from the narrowed sprint only.
  - Other sprints are removed.
- [x] `narrow_status` for `agent="sprint-planner"` without `sprint_id`:
  - Falls back to the broadest view the agent can see (all sprints, no ticket details).
  - Adds a `notes.fallback:` field explaining the fallback.
- [x] `narrow_status` for `agent="programmer"` with `ticket_id` provided:
  - Keeps `project:` block as read-only context.
  - `sprints:` contains only the parent sprint in summary form (state + name only).
  - `tickets.details:` contains only the specified ticket.
  - `notes:` focuses on that ticket's transitions.
- [x] `narrow_status` for `agent="programmer"` without `ticket_id`:
  - Falls back to sprint-planner view (if sprint_id known) or team-lead view.
  - Adds `notes.fallback:` explanation.
- [x] `clasi/status/__init__.py` `narrow_status` export is real (not a stub).
- [x] Unit tests in `tests/unit/test_status/test_narrowing.py` cover all four agent/arg combinations.
- [x] `uv run pytest tests/unit/test_status/` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### Approach

`narrow_status` takes the full dict (output of `build_status`) and filters it
based on agent role and provided IDs. It does not re-evaluate the state machines;
it only filters the already-computed output.

For `programmer` view, infer `sprint_id` from `ticket_id` format (e.g., `"006-003"`
splits to sprint `"006"`, ticket `"003"`).

`notes:` recomputation: scan the narrowed `sprints` list for fireable and blocked
transitions, rebuild `current_focus`, `allowed_next_actions`, `blocked_actions`.

### Files to create

- `clasi/status/narrowing.py` — `narrow_status` function
- `tests/unit/test_status/test_narrowing.py` — unit tests

### Files to modify

- `clasi/status/__init__.py` — replace stub with real `narrow_status` export

### Testing plan

Build a minimal full-status dict in the test (no I/O). Apply `narrow_status`
with each agent/arg combination and assert the structure.

### Documentation updates

Docstring on `narrow_status` with each agent's scope definition and fallback rules.
