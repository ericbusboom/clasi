---
id: '003'
title: Ticket status single writer
status: done
use-cases:
- SUC-004
depends-on: []
github-issue: ''
issue: ticket-status-single-writer.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Ticket status single writer

## Description

Moving a ticket to `tickets/done/` and writing `status: "done"` are two
separate, uncoordinated operations today — skip either call (or call
them out of order) and frontmatter-based ticket counts
(`all_tickets_done`, `ticket_counts`) permanently disagree with
directory-based checks (`is_ticket_in_done_dir`). This ticket makes one
call do both. See `sprint.md`'s Architecture M4.

**Verified evidence** (checked against this repo's own code during
planning):
- `update_ticket_status(path, status)` (`tools/artifact_tools.py:944-970`)
  sets frontmatter only — `artifact.update_frontmatter(status=status)` —
  and never moves the file.
- `move_ticket_to_done(path)` (`tools/artifact_tools.py:1043-1075`) calls
  `Ticket.move_to_done_with_plan()`, which moves the file and its plan
  companion, but never sets `status: "done"` in frontmatter.
- `Ticket.move_to_done()` itself (`ticket.py:142-156`) is a pure file
  move — no frontmatter write.
- Ticket-count computation globs `tickets/*.md` in at least three places
  (`sprint.py:189-204` for `list_tickets`, `status/reader.py:549-575` for
  `all_tickets_done`, `status/reader.py:720-733` for `ticket_count`),
  each independently, and each matches `<ticket>-plan.md` companion files
  left in `tickets/` — a stray plan file inflates counts and can make
  `all_tickets_done` False even when every real ticket is done.

**Independent of tickets 001, 002, and 004** at the code level (touches
`ticket.py`, the ticket-status tool functions in `artifact_tools.py`, and
the ticket-listing glob sites — no file overlap with any other ticket in
this sprint). Sequenced before ticket 004 because it shrinks the repair
surface `close_sprint`'s own self-repair logic has to reason about — see
that ticket's Description.

## Acceptance Criteria

- [x] `update_ticket_status(path, "done")` performs both the frontmatter
      write and the `tickets/done/` move in one call — internally
      delegating to `Ticket.move_to_done()` (or
      `move_to_done_with_plan()`, matching today's plan-file-aware
      behavior) rather than requiring a separate `move_ticket_to_done`
      call. For any status value other than `"done"`, behavior is
      unchanged (frontmatter write only — there is nothing to move for
      `open`/`in-progress`/`exception`).
- [x] `move_ticket_to_done` becomes a thin alias calling the same
      combined path `update_ticket_status(path, "done")` now uses — not
      a second, independent implementation. No behavior divergence
      between the two entry points for a ticket already in the expected
      pre-state.
- [x] One shared ticket-listing helper, excluding `*-plan.md`
      companions, is used by all three of: `Sprint.list_tickets`
      (`sprint.py`), `all_tickets_done`
      (`status/reader.py`), and `ticket_count` (`status/reader.py`) —
      replacing their three independent `glob("*.md")` call sites.
- [x] `reopen_ticket`'s existing converse logic (`ticket.py`'s
      `reopen()`) is verified unchanged and still correct — it already
      does frontmatter+move together correctly; this ticket does not
      need to modify it, only confirm via test that it remains the exact
      converse of the newly-unified done-transition.
- [x] A test asserts frontmatter and directory agree after every status
      transition (`open`→`in-progress`→`done`→reopen back to `open`).
- [x] A test asserts a stray `*-plan.md` companion file in `tickets/`
      affects none of `list_tickets`, `all_tickets_done`, or
      `ticket_count`.

## Implementation Plan

**Approach**: unify the two `artifact_tools.py` entry points around one
combined operation in `ticket.py`, then extract and share the
plan-file-excluding glob helper across the three count sites.

**Files to modify**:
- `src/clasi/ticket.py` — the combined done-transition primitive
  `update_ticket_status`/`move_ticket_to_done` both call
- `src/clasi/tools/artifact_tools.py` — `update_ticket_status`,
  `move_ticket_to_done`
- `src/clasi/sprint.py` — `list_tickets`'s glob call site
- `src/clasi/status/reader.py` — `all_tickets_done`, `ticket_count`'s
  glob call sites

**Do not modify**: anything under `state_machine/` (ticket 002),
`sprint.py`'s stage-writing methods (`set_sprint_stage`,
`detail_promote`, `advance_phase`, `archive` — ticket 001), or
`_close_sprint_full`'s self-repair logic (ticket 004 — that ticket
*consumes* this one's fix by having less to repair, it does not modify
this ticket's files).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010** — including this very
  ticket file, once you're implementing the fix this ticket describes.
  Check-boxes-then-flip or flip-then-check-boxes both work; you will not
  get blocked either way.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or similar. Reporting a
  block is a successful outcome, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_ticket.py tests/unit/test_artifact_tools.py tests/system/test_artifact_tools.py tests/system/test_exception_flow.py -v`
- **New tests to write**: combined move+status-write test for
  `update_ticket_status(path, "done")`; alias-equivalence test for
  `move_ticket_to_done`; shared-glob-helper test with a stray
  `*-plan.md` file present; round-trip (done → reopen → done) agreement
  test.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — not the full suite.
