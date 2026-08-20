---
id: '004'
title: State DB reads stop creating databases
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: state-db-reads-stop-creating-databases.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# State DB reads stop creating databases

## Description

Every `StateDB` method calls `init()` first (`state_db_class.py:166`),
which runs the full `executescript(_SCHEMA)` — a write transaction —
even for pure reads, and `_connect` (`state_db_class.py:143`) uses the
default 5-second busy timeout. Two failure modes this closes: a hook
fired with the wrong cwd auto-creates a phantom, empty
`.clasi/.clasi.db` at that path (OOP off, lock invisible, tier unset —
guards then resolve against a database that answers everything with
defaults); and under parallel agents, the per-read write transactions
contend, and the 5-second busy wait can consume role-guard's entire
5-second harness timeout, which kills the hook process — an
unrecoverable, unloggable fail-open no exception boundary can catch
(see sprint.md's Architecture Migration Concerns for why this residual
risk is narrowed, not eliminated, by this ticket).

**Scope**: `src/clasi/state_db_class.py` only.

**Files to touch (verified during planning):**

- `state_db_class.py:143` (`_connect`) — pass `timeout=1` (or similarly
  short value) to `sqlite3.connect` instead of the sqlite3 default
  (5s).
- `state_db_class.py:166` (`StateDB.init`) — must run at most once per
  `StateDB` instance (track with an instance flag) and must never be
  called implicitly from inside a read method.
- Every read method that currently calls `self.init()` unconditionally
  at its own-connection entry point (e.g. `get_lock_holder:543-557`,
  `get_active_tier:759-774`, `get_oop:845-860`, and others sharing the
  same `_owns_conn = conn is None: self.init(); conn =
  _connect(self._path)` pattern) — when the DB file does not exist,
  return the method's own already-documented "absent"/default value
  (`None`, `""`, empty list, etc. — whatever that method already
  returns for "no record") instead of calling `init()` and creating the
  file. Only an explicit write path (`set_oop`, `acquire_lock`,
  `record_gate`, etc.) is allowed to create the schema.

## Acceptance Criteria

- [x] Read methods return their documented "absent"/default value when
      the DB file does not exist, without creating it
- [x] `sqlite3.connect` uses `timeout=1` (or similar short value) —
      verify via the `_connect` call site, not just behaviorally
- [x] `init()` runs at most once per `StateDB` instance (add an
      instance-level guard flag)
- [x] A test asserts that a read against a nonexistent DB path creates
      no file (`assert not db_path.exists()` after the call)
- [x] Every existing write path (anything that legitimately needs the
      schema to exist) still creates it correctly — do not break
      `clasi init` or the first legitimate write to a fresh project

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_state_db.py tests/unit/test_state_db_class.py`
  (scoped, foreground)
- **New tests to write**: the no-file-created-on-read test above, for
  at least two read methods; a timeout-value assertion (mock or inspect
  the `sqlite3.connect` call); an `init()`-called-at-most-once assertion
  across multiple method calls on one instance.
- **Verification command**: `uv run pytest tests/unit/test_state_db.py tests/unit/test_state_db_class.py -v`
