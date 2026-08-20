---
id: '006'
title: Sprint-lifecycle three-way integration test
status: done
use-cases:
- SUC-006
depends-on:
- '001'
- '002'
- '003'
- '004'
github-issue: ''
issue: sprint-lifecycle-three-way-integration-test.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint-lifecycle three-way integration test

## Description

This is the sprint's acceptance test — it must land last, and it can only
pass once tickets 001-004 are done. Today's state-machine tests stub the
reader to echo whatever phase string the predicate asks for, which is
*why* the vocabulary drift this sprint fixes (`"ticketed"` vs.
`"ticketing"`, the unrecordable `sprint_review` gate, the
frontmatter/DB/computed-machine divergences) shipped repeatedly as "weird
runtime bugs" instead of red tests. See `sprint.md`'s Architecture M6 and
finding 20 of `01-state-layer.md`.

**Sequenced after ticket 005 in this sprint's execution order** (per
`sprint.md`'s Tickets table), even though this test does not assert
anything about the tool envelope shape 005 introduces — it drives real
writers and real DB state, not the MCP tool response contract. Landing it
after 005 rather than immediately after 004 avoids the test needing to be
touched again if 005's mechanical `@clasi_tool` application happens to
shift any call signature this test exercises directly. `depends-on` lists
001, 002, 003, 004 (the four fixes it actually asserts against); 005 is
not a formal dependency, the row order above is what encodes the
sequencing.

## Acceptance Criteria

- [x] One test drives a sprint through the **real writers** — create
      (`Project.create_sprint`), detail (`detail_promote`/
      `Sprint.set_sprint_stage`), gates (`record_gate`), tickets
      (`create_ticket`/`update_ticket_status`), in-progress, done, close
      (`close.SprintCloser`/`force_close`) — against a **real temporary
      project** (real files on a `tmp_path`, a real SQLite DB file, not an
      in-memory stub). No `StateReader` stubbing anywhere in this test.
- [x] At every lifecycle step, the test asserts:
      1. DB phase, frontmatter `status:`, and the computed sprint-machine
         state agree in the sense ticket 001's redesigned
         `detect_inconsistencies` defines agreement (DB phase ==
         frontmatter status; the computed machine state is a distinct,
         non-compared signal — do not assert DB phase equals the computed
         machine state name, they are not the same vocabulary by design).
      2. Gate predicates and `StateDB.advance_phase` agree on gate
         semantics (a `"failed"` gate result does not satisfy a predicate
         that a `"passed"`/`"skipped"` one does).
      3. `detect_inconsistencies` reports zero drift entries at every
         step along the healthy path.
- [x] The test exists in the default suite tier (a normal `tests/system/`
      or `tests/integration/` module collected by a plain `uv run
      pytest`, not gated behind a marker nothing currently activates).
- [x] A deliberately reintroduced vocabulary regression — e.g. a test
      variant that writes a stray `status:` string outside
      `set_sprint_stage()` — fails this test. Include this as an
      explicit sub-test or a documented manual verification step (revert
      one line of ticket 001's fix locally, confirm this test goes red,
      then re-apply the fix) — the point is proving the test actually
      has teeth, not just that it passes on a clean tree.

## Implementation Plan

**Approach**: build the fixture (temp project + temp DB) first, drive one
full lifecycle through it asserting agreement at each step, then add the
regression sub-test last, once the happy-path test is green.

**Files to create**:
- `tests/system/test_sprint_lifecycle_integration.py` (new)

**Files to modify**: none expected — this ticket should not need to
change any `src/clasi/` file. If writing this test surfaces a bug in
tickets 001-004's implementations, stop and report it rather than
patching around it in the test (e.g. by loosening an assertion) — a test
that passes by asserting less than the acceptance criteria above is not
this ticket done, it's this ticket's purpose defeated.

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block, not a silent allow —
  relevant here since this test exercises real MCP-tool-backing code
  paths (`create_sprint`, `create_ticket`, etc.) against a real temp
  project.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure — the stakeholder
  raised this explicitly for this sprint.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/integration/test_state_machine_smoke.py tests/system/test_sprint_review.py -v`
  (to confirm no regression in adjacent lifecycle tests before adding the
  new one)
- **New tests to write**: this ticket's entire deliverable *is* the new
  test — `tests/system/test_sprint_lifecycle_integration.py`.
- **Verification command**:
  `uv run pytest tests/system/test_sprint_lifecycle_integration.py -v`
  — and, since this is the sprint's acceptance test, also re-run
  tickets 001-004's own scoped test commands once more here to confirm
  nothing regressed across the full set before reporting this ticket
  done. The full-suite run remains sprint close's gate, not this
  ticket's — do not run the entire `uv run pytest` here either.
