---
id: '001'
title: Add roadmap as first phase in PHASES constant and update state DB default
status: done
use-cases:
  - SUC-004
depends-on: []
github-issue: ''
todo: two-phase-sprint-planning-roadmap-then-detail.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add roadmap as first phase in PHASES constant and update state DB default

## Description

The `PHASES` constant in `clasi/state_db_class.py` (line 17) currently begins
with `planning-docs`. This ticket prepends `roadmap` to make it the new first
phase. All subsequent phases are unchanged.

The `StateDB.advance_phase()` method uses sequential index arithmetic on
`PHASES`, so adding `roadmap` at position 0 automatically makes advancing from
`roadmap` yield `planning-docs` — no code change to advance logic is needed.

The SQLite schema default for the `phase` column (line 35: `DEFAULT 'planning-docs'`)
must be updated to `DEFAULT 'roadmap'`. This affects new sprints registered
after this ticket lands. Existing sprint records in the DB are unaffected.

**Files to modify:**
- `clasi/state_db_class.py`: prepend `"roadmap"` to `PHASES`; update schema default.

## Acceptance Criteria

- [x] `PHASES[0] == "roadmap"` in `clasi/state_db_class.py`.
- [x] The SQLite schema `DEFAULT` for the `phase` column is `'roadmap'`.
- [x] `StateDB.advance_phase()` called on a sprint in `roadmap` phase returns
      `{"old_phase": "roadmap", "new_phase": "planning-docs"}`.
- [x] All existing phase transitions from `planning-docs` onward continue to
      work as before.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

- Edit `clasi/state_db_class.py`:
  1. Line 17-25: insert `"roadmap",` as the first element of `PHASES`.
  2. Line ~35 in `_SCHEMA`: change `DEFAULT 'planning-docs'` to `DEFAULT 'roadmap'`.
- No other files change in this ticket.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_state_db_class.py` (if present), `uv run pytest`
- **New tests to write**: Covered in ticket 009 (unit tests). Verify here that
  advancing from `roadmap` phase succeeds.
- **Verification command**: `uv run pytest`
