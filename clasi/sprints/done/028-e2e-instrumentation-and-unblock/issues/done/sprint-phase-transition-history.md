---
status: done
type: feature
tags:
- reliability-campaign
- phase-0
- state-db
- observability
sprint: 028
tickets:
- 028-004
---

# State DB: record sprint phase-transition history with timestamps

## Description

`advance_phase` updates only `sprints.phase`/`updated_at`, so there is no
record of when a sprint entered each phase — per-phase wall-time is
unmeasurable, for the E2E run report and for real sprints alike. From the
reliability review (05-e2e-test-infra.md instrumentation plan item 4).

Add a `phase_transitions` table (`sprint_id, from_phase, to_phase, at`) to
`_SCHEMA` in `src/clasi/state_db_class.py`, written inside `advance_phase`
(and any other phase writer). Expose the history via `detail_sprint` and
`get_sprint_status`.

## Acceptance criteria

- Every phase change writes one history row in the same transaction as the
  phase update.
- `get_sprint_status` (or `detail_sprint`) returns the transition list with
  timestamps.
- Schema migration is additive; existing databases gain the table without
  manual steps.
