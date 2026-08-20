---
id: '010'
title: Role-guard ticket-state gate must not block edits to completed tickets
status: done
use-cases: []
depends-on: []
github-issue: ''
issue: role-guard-cannot-see-done-tickets.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Role-guard ticket-state gate must not block edits to completed tickets

## Description

Newly reported defect (`role-guard-cannot-see-done-tickets.md`), added to
sprint 029 mid-execution. The stakeholder hit it recording after-the-fact
benchmark evidence on a completed ticket — checking a box and citing a
measured bench sequence — and the role-guard hook refused the edit with a
false `no ticket is in-progress` violation.

**Verified root cause** (read directly, not assumed from the issue text):
`_get_active_tickets()` (`src/clasi/hook_handlers.py:1344`) enumerates a
sprint's in-progress tickets with

```python
for ticket_file in tickets_dir.glob("*.md"):   # hook_handlers.py:1378
```

— non-recursive, so any ticket already relocated to `tickets/done/` is
invisible to this scan. Its caller, the ticket-state gate inside
`handle_role_guard` (`hook_handlers.py:1075-1095`), blocks every tier-2
write with `gate=ticket-state:no-ticket` / exit 2 whenever
`_get_active_tickets()` returns empty and an execution lock is held. Right
now, in this very sprint, tickets 001-008 already sit in `tickets/done/`
and ticket 009 is still `status: open` (not `in-progress`) — so
`_get_active_tickets("029")` already returns `[]`, and any tier-2 edit to
one of the eight completed ticket files would be blocked today.

**Important implementation trap, found during investigation — do not
"fix" this by only making the glob recursive.** `_get_active_tickets`
filters on the literal substring `"status: in-progress"`
(`hook_handlers.py:1381`). A ticket that has been moved to `tickets/done/`
has `status: done` in its frontmatter — a recursive
`tickets_dir.glob("**/*.md")` would find the file but its status would
still exclude it from `active_tickets`. A glob-only change does **not**
satisfy AC1 below; it changes nothing observable. The actual fix has to
be a new exemption in the gate itself (see Implementation Plan).

**Why this must land before ticket 009**: ticket 009 (`Guard fail-closed
exception boundary`, still `open`) converts every guard failure —
including this gate's false denial — from a silent allow into a hard
block. A gate that raises an unsatisfiable false violation gets strictly
worse once nothing can fall through around it. **This ticket must execute
before ticket 009.** No formal `depends-on` is recorded on ticket 009
itself (out of scope for this dispatch — ticket 009 is not to be touched),
but the sprint.md Tickets table row order is updated to place 010 ahead
of 009, and whoever picks up execution should treat that row order as the
real constraint.

## Acceptance Criteria

- [x] Editing a ticket file that already lives under a sprint's
      `tickets/done/` directory does not raise the ticket-state gate's
      `no ticket is in-progress` violation (`gate=ticket-state:no-ticket`,
      exit 2) — regardless of whether some other ticket in the sprint
      happens to be `in-progress` at the time.
- [x] The gate still fails closed for the case it exists to catch: a
      tier-2 write to an ordinary source path, with an execution lock
      held, zero tickets `in-progress`, and OOP not active, still exits 2
      with reason `no-ticket`. Verify this with a **real captured deny
      payload** added to the replay corpus (see Testing) — not a
      hand-built dict.
- [x] A test covers the done-ticket-edit case specifically, using a real
      captured payload shape (see Testing), not a hand-built dict.
- [x] This ticket records a recommendation — grounded in the verified gate
      code, not speculation — on whether the related guard-ordering trap
      (an agent cannot edit its own ticket's body after setting
      `status: done`, before it is moved to `tickets/done/`) should be
      fixed alongside this change or documented as deliberate. See
      Recommendation below; the implementing agent should follow it
      unless investigation during execution turns up a reason not to,
      in which case documenting the deviation in the ticket's final
      report is sufficient — no need to re-open planning for it.

## Recommendation: the guard-ordering trap

Investigated directly rather than left as an open question. The ordering
trap (status flips to `done` while the file is still in `tickets/`, not
yet moved — the very next tier-2 write, including finishing that same
ticket's own checkboxes, is blocked) is caused by the **same code path**
as this ticket's primary bug: the ticket-state gate's only exemptions
today are `_issues_prefix` / `_reflections_prefix`
(`hook_handlers.py:1058-1077`); a ticket file mid-transition gets no
exemption at all, `done` or not, moved or not.

**Recommendation: fix alongside, not document as deliberate.** Scope the
new exemption to *any* tier-2 write targeting a ticket's own `.md` file
under the sprint's `tickets/` tree (both `tickets/*.md` and
`tickets/done/*.md`), not just the `done/` subdirectory narrowly required
by AC1. That single change resolves both this ticket's reported bug and
the ordering trap as one consequence of the same fix, for no meaningful
increase in scope: a ticket file is process bookkeeping, not the
production source/tests the gate exists to police, the same reasoning
that already justifies the `issues_dir`/`reflections_dir` exemption. The
trap has independently bitten three programmers in this campaign
already (per the issue), so it is a demonstrated, recurring cost with no
compensating protection benefit — nothing dangerous is being newly
permitted. Before adopting this: re-verify AC2 is unaffected (confirmed
during planning — none of the 8 existing captured fixtures in
`tests/fixtures/hook_payloads/` target a `tickets/` path, so widening the
exemption does not silently change any already-pinned replay decision).

## Implementation Plan

**Files likely touched**: `src/clasi/hook_handlers.py` (the
`handle_role_guard` ticket-state gate, `hook_handlers.py:1071-1095`, and
possibly the exemption-prefix construction near `_issues_prefix`/
`_reflections_prefix` at `hook_handlers.py:1058-1077`); a new fixture
under `tests/fixtures/hook_payloads/`; `tests/unit/test_hook_payload_replay.py`
(`_FIXTURES` table); `tests/unit/test_hook_handlers.py` (the
`TestGetActiveTickets` / ticket-in-progress-gate test classes, see below).

**Suggested approach** (the implementing agent should verify and adjust,
not follow blindly):

1. Add a gate exemption for tier-2 writes whose `file_path` targets a
   ticket `.md` file already under this sprint's own `tickets/` tree
   (recommendation above covers both `tickets/*.md` and
   `tickets/done/*.md`) — mirroring the existing
   `_issues_prefix`/`_reflections_prefix` pattern at
   `hook_handlers.py:1075-1077`, evaluated regardless of whether
   `_get_active_tickets` finds anything `in-progress`. Resolving the
   sprint's own `tickets/` directory path needs the same sprint-dir
   lookup `_get_active_tickets` already performs internally
   (`hook_handlers.py:1364-1371`) — reuse or factor it out rather than
   duplicating the `iterdir()` scan.
2. Do **not** rely on making `_get_active_tickets`'s glob recursive as
   the primary fix — per the investigation above, it doesn't change the
   function's output for a `status: done` ticket either way. (A recursive
   glob may still be worth doing for `_get_active_tickets`'s *other*
   callers — the `UserPromptSubmit` status-injection message at
   `hook_handlers.py:1530`/`1641` — so the imperative note it prints
   doesn't itself imply a done-and-moved ticket is still open. Judge
   during implementation whether that's in scope here or a separate,
   smaller follow-up; it is not required by any acceptance criterion
   above.)
3. Capture one new real deny fixture for AC2/AC3: tier-2, execution lock
   held, zero tickets `in-progress`, `file_path` under an ordinary source
   prefix (not a ticket path) → expect exit 2, reason `no-ticket`. Follow
   the exact capture methodology documented at the top of
   `tests/unit/test_hook_payload_replay.py` (temporary shell-level `tee`
   against a throwaway scratch project, piped into the real, unmodified
   `clasi hook role-guard` entrypoint — no temporary capture code added to
   `hook_handlers.py` itself). Add a second fixture (or reuse/adapt the
   done-ticket-edit scenario) for AC1/AC3: tier-2, lock held, zero
   tickets `in-progress`, `file_path` under `tickets/done/` → expect exit
   0. Add both as new rows in `_FIXTURES`
   (`tests/unit/test_hook_payload_replay.py:115-157`), following the
   existing `_Fixture` dataclass shape and `path_rewrite_suffix`
   convention for re-rooting an absolute captured path under a fresh
   `tmp_path`.
4. Add/extend unit coverage in `test_hook_handlers.py` near the existing
   `TestGetActiveTickets` class (`tests/unit/test_hook_handlers.py:175-217`,
   helpers `_make_in_progress_ticket`/`_make_done_ticket` at lines
   159-172) and the ticket-in-progress gate test class around
   `tests/unit/test_hook_handlers.py:3127-3260` — add a helper that
   writes a done ticket into `sprint_dir/tickets/done/` (the existing
   `_make_done_ticket` writes into `sprint_dir/tickets/`, not the `done/`
   subdirectory — it does not cover this bug's actual scenario) and
   assert a tier-2 edit to that file is allowed even with zero
   `in-progress` tickets anywhere in the sprint.
5. If adopting the Recommendation above, add one more test asserting a
   tier-2 write to a ticket file still in `tickets/` (not yet moved),
   whose own `status` was just flipped to `done`, is also allowed — the
   ordering-trap scenario.

**Dogfooding lockout warning**: this ticket edits
`src/clasi/hook_handlers.py` — the exact module that enforces role-guard
on every `Edit`/`Write`/`MultiEdit` call this repo's own agents make,
including the agent implementing this ticket. Keep the module
**importable at every intermediate save point** (no half-written syntax
error left uncommitted-but-on-disk) — a broken import here fails closed
for every subsequent tool call in the session, this ticket's own edits
included. If a self-lockout happens anyway, `clasi oop on --reason '...'`
(or the emergency `.clasi/oop` file) is the unconditional, file-checked-
first escape hatch, unaffected by this gate.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_hook_payload_replay.py`
  (scoped to the modules this ticket touches, run in the foreground —
  per project convention the full suite is a sprint-close gate, not a
  per-ticket one).
- **New tests to write**: see Implementation Plan steps 3-5 — two new
  captured fixtures plus their `_FIXTURES` rows, and new
  `test_hook_handlers.py` coverage for the done-ticket-edit case (and,
  if the Recommendation is adopted, the ordering-trap case).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_hook_payload_replay.py`
