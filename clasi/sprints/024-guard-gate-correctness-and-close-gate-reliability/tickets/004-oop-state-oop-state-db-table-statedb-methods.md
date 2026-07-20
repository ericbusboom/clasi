---
id: '004'
title: 'OOP state: oop_state DB table + StateDB methods'
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: db-backed-oop-flag-file-as-unconditional-override.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# OOP state: oop_state DB table + StateDB methods

## Description

The OOP bypass today is a zero-byte marker file with no audit trail (who
set it, when, why, for how long). This ticket lays the DB foundation for
the redesign: a new `oop_state` singleton table and the `StateDB` methods
to set, clear, and read it. This is the first of three tickets implementing
the DB-backed OOP redesign (004 → 005 → 006); it does not touch
`hook_handlers.py`'s `_oop_active()` or the CLI — those are tickets 005 and
006, which depend on this one.

Model the new table and methods on the existing `recovery_state` singleton-
table pattern already in `state_db_class.py` — same shape (a single-row
table read/written via dedicated methods), same `CREATE TABLE IF NOT
EXISTS` migration-free approach.

## Acceptance Criteria

- [x] `state_db_class.py`'s `_SCHEMA` includes a new `oop_state` table
      (`CREATE TABLE IF NOT EXISTS`) with columns `id`, `set_at`, `reason`,
      `expires_at`, modeled on the existing `recovery_state` table's
      singleton-row pattern.
- [x] `StateDB.set_oop(reason, ttl_hours=8.0)` writes the singleton row
      with `set_at` (current time), the given `reason`, and `expires_at`
      computed from `ttl_hours`.
- [x] `StateDB.clear_oop()` removes the singleton row (idempotent — safe
      to call when no row exists).
- [x] `StateDB.get_oop()` returns the current row's data (or `None`/falsy
      if unset), with **expiry-on-read** semantics matching
      `get_recovery_state`'s existing pattern: if the row's `expires_at` is
      in the past, the row is deleted and a warning is emitted, and the
      method returns as if no row existed.
- [x] Module-level wrapper functions for `set_oop`, `clear_oop`, `get_oop`
      are added in `state_db.py`, and added to that module's `__all__`.
- [x] DB-level unit tests cover: set then get returns the reason/expiry;
      clear then get returns unset; set with a very short `ttl_hours` then
      get after expiry deletes the row and returns unset (with the warning
      emitted); clear on an already-unset table is a no-op, not an error.

## Implementation Plan

**Approach**: Mirror `recovery_state`'s existing schema-and-methods
pattern in the same two files, for the new `oop_state` concern. No new
subsystem — this is a same-shaped sibling table and method set.

**Files to modify**:
- `src/clasi/state_db_class.py` — add `oop_state` to `_SCHEMA`; add
  `set_oop`, `clear_oop`, `get_oop` methods to `StateDB`, matching the
  structure and expiry-on-read behavior of the existing
  `recovery_state`/`get_recovery_state` methods.
- `src/clasi/state_db.py` — add module-level wrapper functions for the
  three new methods; add them to `__all__`.

**Testing plan**:
- Existing tests to run: the full `state_db`/`StateDB` test suite, to
  confirm the new table and methods don't disturb existing schema/method
  behavior.
- New tests: set/get round-trip; clear then get returns unset; expiry-on-
  read deletes the row and warns (mirror whatever test pattern
  `get_recovery_state`'s expiry test already uses, since this ticket
  models that pattern exactly); clear-when-unset no-op.
- Verification command: `uv run pytest --no-cov -q
  tests/unit/test_state_db*` (or the equivalent path for this project's
  state_db test location) plus the full suite before calling this ticket
  done.

**Documentation updates**:
- None required at this ticket — CLI and docs rewording is ticket 006 in
  this same sprint, once the DB layer this ticket adds is in place.
