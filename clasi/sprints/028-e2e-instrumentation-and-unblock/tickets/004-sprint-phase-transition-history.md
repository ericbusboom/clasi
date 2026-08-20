---
id: '004'
title: Sprint phase-transition history
status: open
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: sprint-phase-transition-history.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint phase-transition history

## Description

`advance_phase` updates only `sprints.phase`/`updated_at`, so there is no
record of when a sprint entered each phase — per-phase wall-time is
unmeasurable, both for this sprint's own E2E baseline report and for
real sprints going forward. This ticket adds a `phase_transitions`
history table, written transactionally, and exposes it through the
existing DB-backed status query. See sprint.md's Architecture, module 4
("Sprint Phase-Transition History") and SUC-004.

**Scope**: `src/clasi/state_db_class.py` and
`src/clasi/tools/artifact_tools.py`. Independent of every other ticket
except ticket 006 (report assembly), which reads this ticket's output
but does not depend on its code.

**Correction to the exposure point** — the issue file (and this
sprint's own `sprint.md`/design-overlay text) names `detail_sprint`/
`get_sprint_status` as where the history should be exposed. Verified
against current code: neither of those actually reads sprint phase from
the state DB. `detail_sprint` (`artifact_tools.py:264-283`) returns
`{sprint_id, phase, files_written}` from `sprint.detail_promote()` — a
one-time roadmap-promotion action, not an ongoing status query.
`get_sprint_status` (`artifact_tools.py:911-929`) returns `{id, title,
status, branch, worktree, tickets}` from the `Sprint` artifact model,
also not the DB. The MCP tool that actually reads DB-backed phase state
is **`get_sprint_phase`** (`artifact_tools.py:2082-2094`), which calls
`get_project().db.get_sprint_state(sprint_id)` —
`StateDB.get_sprint_state` (`state_db_class.py:218-...`), which already
returns `{id, slug, phase, branch, created_at, updated_at, gates,
lock}`. Add `phase_transitions` to *that* dict, not to `detail_sprint`/
`get_sprint_status`. (This ticket's own acceptance criteria below use
the corrected name; the sprint-planner will reconcile `sprint.md`'s
wording separately — do not block on that, implement against
`get_sprint_phase`.)

**Key source locations verified during sprint planning:**

- `src/clasi/state_db_class.py:64-113` — `_SCHEMA`, the executescript
  block defining `sprints`, `sprint_gates`, `execution_locks`,
  `recovery_state`, `active_agents`, `oop_state`. Add a `phase_transitions`
  table here: `sprint_id TEXT NOT NULL REFERENCES sprints(id), from_phase
  TEXT, to_phase TEXT NOT NULL, at TEXT NOT NULL` (plus an `id INTEGER
  PRIMARY KEY AUTOINCREMENT`, matching the `sprint_gates` table's own
  shape immediately above it in the schema). `from_phase` should be
  nullable or empty-string for a sprint's very first recorded transition
  if one is ever backfilled (it won't be, per sprint.md's Open Questions
  — this is just schema hygiene, not an invitation to backfill).
- `src/clasi/state_db_class.py:270-327` — `advance_phase`: computes
  `next_phase`, then at lines 320-325 does `conn.execute("UPDATE sprints
  SET phase = ?, updated_at = ? WHERE id = ?", ...)` followed by
  `conn.commit()`. Insert the `phase_transitions` row (`sprint_id,
  from_phase=current, to_phase=next_phase, at=now`) between the `UPDATE`
  and the `conn.commit()` call, so both writes land in the same
  transaction — if either fails, neither is committed.
- Check whether any other method in `state_db_class.py` writes
  `sprints.phase` directly (the issue says "and any other phase writer")
  — `advance_phase` looked like the only phase writer during planning,
  but confirm this against current code before assuming it's the only
  call site to update.
- `src/clasi/state_db_class.py:218-...` — `get_sprint_state`, called by
  the `get_sprint_phase` MCP tool. Add a query for this sprint's
  `phase_transitions` rows (ordered by `at`) and include them in the
  returned dict as `"phase_transitions": [{"from_phase":..., "to_phase":...,
  "at":...}, ...]`.

## Acceptance Criteria

- [ ] `_SCHEMA` gains a `phase_transitions` table (`sprint_id, from_phase,
      to_phase, at`), additive (`CREATE TABLE IF NOT EXISTS`).
- [ ] `advance_phase` writes one `phase_transitions` row in the same
      transaction as its `sprints.phase`/`updated_at` update.
- [ ] Any other method that writes `sprints.phase` directly (confirm
      whether one exists) is updated the same way.
- [ ] `get_sprint_phase` (via `StateDB.get_sprint_state`) returns the
      transition list with timestamps as part of its existing response
      dict.
- [ ] `get_sprint_phase`'s docstring (`artifact_tools.py:2082-2094`,
      currently `"""Get a sprint's current lifecycle phase and gate
      status. ... Returns JSON with {id, phase, gates, lock}."""`) is
      updated to document the new `phase_transitions` field in its
      return shape — the docstring is the literal contract calling
      agents see (per this doc set's own `tools-DESIGN.md` constraint:
      "every tool function is the literal contract agents depend on");
      leaving it stale after this ticket adds a field would mean the
      MCP tool description lies about its own return shape from the
      moment this ticket lands.
- [ ] Schema migration is additive; an existing project database gains
      the table automatically on next `init()` — no manual migration
      step, no data loss for existing rows in other tables.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_state_db_class.py
  tests/unit/test_state_db.py` (scoped, foreground) — confirms the
  schema addition and `advance_phase` change don't break existing gate/
  lock/phase behavior.
- **New tests to write**: a test that `init()` on a fresh DB creates the
  `phase_transitions` table; a test that calling `advance_phase` writes
  exactly one new row with the correct `from_phase`/`to_phase` and that
  the row and the `sprints.phase` update are atomic (e.g. assert both
  are visible after commit, or simulate a mid-transaction failure if the
  test harness supports it); a test that `get_sprint_phase` /
  `get_sprint_state` returns the accumulated transition list in order
  after multiple `advance_phase` calls.
- **Verification command**: `uv run pytest tests/unit/test_state_db_class.py
  tests/unit/test_state_db.py -v` (scoped, foreground — do not run the
  full suite for this ticket).
