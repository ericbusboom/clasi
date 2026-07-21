---
id: '005'
title: _oop_active() DB-aware rewrite + status-block reporting
status: done
use-cases:
- SUC-004
depends-on:
- '004'
github-issue: ''
issue: db-backed-oop-flag-file-as-unconditional-override.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# _oop_active() DB-aware rewrite + status-block reporting

## Description

**Read `src/clasi/hook_handlers.py`'s current `_oop_active()` and
`_find_project_root()` before starting this ticket.** The narrower
cwd-resolution bug this issue originally described was **already fixed
out-of-process on 2026-07-17**: a `_find_project_root()` helper was added,
and `_oop_active()` already resolves `.clasi/oop` and `.clasi-oop` against
the discovered project root rather than a bare relative path. Do **not**
re-ticket or re-implement that fix — it is already in the codebase. This
ticket covers only what remains: the DB-backed redesign built on top of
ticket 004's new `oop_state` table.

What remains to build in this ticket:

1. Rewrite `_oop_active()` so it checks the flag file first (already
   root-resolved via the existing `_find_project_root()` — keep this as
   the unconditional override, checked first, per the stakeholder's
   2026-07-16 decision recorded in the issue and in sprint.md's Design
   Rationale: the file's entire value is that it needs no working
   subsystem to function, so it must not be merged with or gated behind
   the DB check), **then** checks the DB via `state_db.get_oop()` against
   the discovered root's `db_path`. Return `True` if either fires.
2. Add `_oop_source()` returning `"file" | "db" | None`, for reporting
   which channel (or both) is currently active.
3. Update `handle_status_inject` to emit a minimal status block (never
   silence) whenever OOP is active, naming source, reason, age, and
   expiry (expiry only applicable to the DB channel). Today it emits
   nothing when OOP is active — this is a deliberate, called-out breaking
   change to that silent behavior, not an accidental regression.
4. Update `tests/unit/test_status/test_hook_injection.py`'s existing
   empty-output assertions for the OOP-active case to instead assert the
   new minimal status block. This test file's assertions are expected to
   change as a consequence of item 3, not left failing.
5. Add handler-level tests (not just helper-level unit tests on
   `_oop_active()` in isolation) on **both** `role-guard` and `mcp-guard`,
   per the issue's explicit citation of the 019-002 lesson: helper-level
   tests alone can miss call sites that never got wired to the helper.
6. Add a broken/corrupt-DB test: with the DB file corrupted or otherwise
   unreadable, the file override must still work with no exception
   propagating out of the guard.
7. Re-assert (do not re-implement) the cwd-independence regression: flag
   set at project root, hook invoked with cwd = a subdirectory, bypass
   still resolves. This is a regression check on the already-existing
   `_find_project_root()` fix, confirming this ticket's changes don't
   undo it — not new work to build that mechanism.

## Acceptance Criteria

- [x] `clasi oop on --reason test` (or the equivalent direct `set_oop`
      call, if the CLI from ticket 006 isn't yet available when this
      ticket is executed — coordinate via `depends-on` ordering) → role-
      guard allows a source write (exit 0, reason `oop-bypass` or
      equivalent) → `clasi oop status` (or `get_oop`/`_oop_source()`
      directly) shows the reason and age → the status block emitted by
      `handle_status_inject` carries the OOP line → `clasi oop off` (or
      `clear_oop()`) → guard blocks again (exit 2).
- [x] Cwd-independence regression check: flag file set at project root,
      hook invoked with cwd set to a subdirectory — bypass still resolves.
      This re-asserts the existing `_find_project_root()` fix; it is not
      re-implemented by this ticket.
- [x] File override with DB empty: `touch .clasi/oop` → bypass works;
      `_oop_source()` reports `"file"`; the status block reports an
      override-file state with no audit record (no reason/age available
      from a bare marker file).
- [x] `clasi oop on --ttl-hours 0.0001` (or the equivalent direct
      `set_oop` call with a very short TTL) → the DB row auto-expires on
      next read (via ticket 004's expiry-on-read `get_oop()`); enforcement
      resumes once expired.
- [x] Handler-level tests cover the DB-backed OOP flag on **both**
      `role-guard` and `mcp-guard` — not only a unit test on `_oop_active()`
      called directly.
- [x] A corrupt/locked DB file test: `_oop_active()` does not raise; the
      file override, if present, still works; if the file is absent and
      the DB is broken, the guard fails closed (denies) rather than
      raising an unhandled exception.
- [x] `handle_status_inject` emits a minimal, non-empty status block
      whenever OOP is active (via either channel), naming source, and
      reason/age/expiry as applicable to that channel.
- [x] `tests/unit/test_status/test_hook_injection.py`'s OOP-active
      assertions are updated to match the new minimal-block behavior; the
      file no longer asserts empty output for the OOP-active case.
- [x] Full test suite remains green (`uv run pytest --no-cov -q`).

## Implementation Plan

**Approach**: Build directly on ticket 004's `state_db` methods. Do not
touch `_find_project_root()` or the cwd-resolution logic itself — confirm
it by reading, then build on top of it.

**Files to modify**:
- `src/clasi/hook_handlers.py` — rewrite `_oop_active()` (file-first,
  then DB, return `True` if either fires); add `_oop_source()`; update
  `handle_status_inject` to emit the minimal OOP status block; confirm
  (do not modify) `_find_project_root()`.
- `tests/unit/test_status/test_hook_injection.py` — update OOP-active
  assertions from empty-output to the new minimal block.
- New or existing handler-level test files covering `role-guard` and
  `mcp-guard` with the DB-backed OOP flag active.

**Testing plan**:
- Existing tests to run: full suite, with particular attention to
  `tests/unit/test_status/test_hook_injection.py` (expected to need
  updates, not silently fail) and any existing role-guard/mcp-guard OOP
  tests (regression).
- New tests: DB-channel allow/deny round trip on both guards; file-
  channel-only (DB empty) allow; both-channels-active reporting; TTL
  expiry-on-read resuming enforcement; corrupt/locked DB with file
  override still functioning; cwd-independence re-check.
- Verification command: `uv run pytest --no-cov -q`.

**Documentation updates**:
- None in this ticket — the CLI and prose docs rewording is ticket 006,
  which depends on this ticket's `_oop_source()` and status-block
  behavior being in place to document accurately.
