---
id: '002'
title: Fix unsatisfiable state-machine predicates
status: open
use-cases: [SUC-003]
depends-on: []
github-issue: ''
issue: fix-unsatisfiable-state-machine-predicates.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix unsatisfiable state-machine predicates

## Description

Several predicates in the sprint and ticket state machines reference
values, gates, or flags the shipped toolchain never writes, so `clasi
status` reports against a process that cannot actually complete. This
ticket makes every referenced predicate satisfiable by something real,
fixes the `evaluate_state` "exactly one match" contract (which the sprint
machine's own `open`/`planned` states violate by design), and deletes the
exception-message-parsing workaround that contract violation forced into
existence. See `sprint.md`'s Architecture M3 and the two "remove rather
than make recordable" / "most-advanced-match-wins" Design Rationale
entries for the full reasoning.

**Independent of ticket 001**: this ticket touches
`state_machine/predicates/*.py`, `evaluator.py`,
`schemas/state-machines/{sprint,ticket}.yaml`, and the three
`AmbiguousStateError`-handling call sites in `status/reporter.py` — no
file overlap with ticket 001's `sprint.py`/`status/inconsistency.py`
changes. It can be implemented in any order relative to ticket 001, but
both are sequenced before ticket 004 (close_sprint) because a low-risk,
independent fix should land before the sprint's highest-risk change, not
because of a hard code dependency.

**Verified evidence** (checked against this repo's own code during
planning, not assumed):
- `is_any_sprint_ticketed` (`state_machine/predicates/project.py:76-79`)
  queries DB phase `"ticketed"`; the DB phase list
  (`_ArtifactGraph.phases()`, derived from
  `schemas/se-process/schema.yaml`) only ever contains `"ticketing"` — no
  writer ever produces `"ticketed"`. This is why this repo's own status
  block currently reports `enter-sprint` permanently blocked.
- `is_architecture_review_recorded`/`is_pre_flight_satisfied`
  (`state_machine/predicates/sprint.py:35-51`) check
  `sprint_gate(...) is not None` — a **failed** review satisfies them,
  while `StateDB.advance_phase` (`state_db_class.py:356`) requires
  `result in {"passed", "skipped"}`. Two semantics for one row.
- `is_review_satisfied` (`state_machine/predicates/sprint.py:88-98`)
  requires a `sprint_review` gate; `record_gate`'s `VALID_GATE_NAMES`
  (`state_db_class.py:55`) is `{"architecture_review",
  "stakeholder_approval"}` — `sprint_review` cannot be recorded. Grepped
  during planning: zero writers anywhere for `close-report.md`
  (`is_close_report_present`), the `pre_flight_review`/`post_review`
  frontmatter flags, `.clasi/test-cache` (`is_tests_passing`, ticket
  machine), or `reopen_requested` (`is_reopen_requested`, ticket
  machine).
- `sprint.yaml`'s `open` and `planned` states have byte-identical
  invariant lists (`[is_sprint_doc_present]`) — `evaluate_state`'s
  "exactly one state must match" contract (`evaluator.py:69-80`) is
  violated on essentially every evaluation. The actual running behavior
  today: `AmbiguousStateError` is caught in three places in
  `status/reporter.py` (lines 198, 238, 319), and
  `_last_matching_state_from_error` (`reporter.py:516-539`) recovers the
  answer by regexing the exception's own message text
  (`r"simultaneously:\s*(\[[^\]]+\])"`) and `ast.literal_eval`-ing it.

## Acceptance Criteria

- [ ] `is_any_sprint_ticketed` (`state_machine/predicates/project.py`)
      queries DB phase `"ticketing"`, not `"ticketed"`.
- [ ] The reader method it calls, `any_sprint_in_phase`
      (`status/reader.py:445-460`), is scoped to active (non-archived)
      sprints only — do not count a sprint under `sprints/done/` toward
      `any_sprint_in_phase`. (This also resolves the sprint-012 false
      positive described in ticket 001 as a side effect of the correct
      semantic, not as a special case — do not add sprint-012-specific
      logic.)
- [ ] `is_architecture_review_recorded`/`is_pre_flight_satisfied`
      (`state_machine/predicates/sprint.py`) check
      `result in {"passed", "skipped"}`, matching
      `StateDB.advance_phase`'s own semantics, instead of `is not None`.
- [ ] `sprint_review`, `is_review_satisfied`, `is_close_report_present`,
      the `pre_flight_review`/`post_review` skip-flag predicates,
      `is_tests_passing` (ticket machine), and `is_reopen_requested`
      (ticket machine) are removed — not made recordable — from both
      `schemas/state-machines/sprint.yaml` and `ticket.yaml` and their
      backing predicate functions in
      `state_machine/predicates/{sprint,ticket}.py`. The `closed` state's
      invariants become `[is_branch_merged]` only; the `finish`
      transition's conditions become `[is_acceptance_criteria_met]`
      only; the `reopen` transition drops `is_reopen_requested` from its
      conditions.
- [ ] `evaluate_state` (`state_machine/evaluator.py`) defines
      most-advanced-match-wins: when more than one state's invariants
      hold, return the last-declared match (declaration order in the
      YAML is significant) instead of raising `AmbiguousStateError`.
      Zero matches still raises `NoMatchingStateError`, unchanged.
- [ ] `_last_matching_state_from_error` and its three call sites in
      `status/reporter.py` (lines 198, 238, 319) are deleted — no
      remaining caller of the function, and no remaining
      `except AmbiguousStateError` block anywhere in `reporter.py`.
- [ ] A test asserts every phase string referenced by any predicate
      exists in `ArtifactGraph.phases()` (closes the class of bug that
      shipped this defect the first time — the existing unit test at
      `tests/unit/test_state_machine/test_predicates.py:261` stubs the
      reader to agree with the predicate, which cannot catch this).
- [ ] `evaluate_state` is exercised against a context matching both
      `open` and `planned` simultaneously and returns a determinate
      state, not an exception.
- [ ] This repo's own status block no longer reports `enter-sprint`
      blocked by a predicate that cannot be true (verify via `clasi
      status` or `get_status` against this repo after the fix — but see
      the stale-server note below).

## Implementation Plan

**Approach**: fix predicate logic and query strings first (small,
independent changes), then remove the unsatisfiable predicates from both
YAML machines and their backing functions together (they must stay in
sync — a predicate removed from YAML with its function left behind, or
vice versa, is a dangling reference), then change `evaluate_state`'s
contract and delete its caller's workaround last (the workaround exists
*because* of the contract this ticket is fixing, so removing it first
would leave `reporter.py` broken mid-ticket).

**Files to modify**:
- `src/clasi/state_machine/predicates/project.py` — `is_any_sprint_ticketed`
- `src/clasi/state_machine/predicates/sprint.py` — gate-result semantics;
  remove `is_review_satisfied`, `is_close_report_present`
- `src/clasi/state_machine/predicates/ticket.py` — remove
  `is_tests_passing`, `is_reopen_requested`
- `src/clasi/state_machine/evaluator.py` — `evaluate_state`
- `src/clasi/schemas/state-machines/sprint.yaml` — `closed` state
  invariants; predicate list
- `src/clasi/schemas/state-machines/ticket.yaml` — `finish`/`reopen`
  transition conditions; predicate list
- `src/clasi/status/reader.py` — `any_sprint_in_phase` scoping
- `src/clasi/status/reporter.py` — delete
  `_last_matching_state_from_error` and its 3 call sites

**Do not modify**: `sprint.py`, `status/inconsistency.py` (ticket 001);
`ticket.py`, ticket-status tool functions (ticket 003); anything under
`close_sprint`/`close.py` (ticket 004).

**Flag, do not fix**: while removing `is_tests_passing`/
`is_reopen_requested`, you may notice the ticket machine's `finish`
transition can structurally never show `fireable: true` before
`move_ticket_to_done` runs, because `inspect_transitions`'s "conditions +
destination invariants" rule evaluates the destination state's own
invariants (`is_ticket_in_done_dir`) against the *pre-action* context.
This is a real, separate defect (see `sprint.md`'s Open Question 1) — do
not attempt to fix it in this ticket; file a follow-up issue instead if
you confirm it.

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or similar. Reporting a
  block is a successful outcome, not a failure.
- **This ticket changes code the running MCP server also reads**
  (predicate evaluation feeds `clasi status`/`get_status`). The MCP
  server in the driving session is already stale relative to this
  ticket's changes (same-version staleness detection exists since sprint
  029, but the server itself won't pick up new code without a restart).
  Verify this ticket's fix via the test suite, not via a live status
  call through the current session's MCP connection.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_state_machine/ tests/unit/test_status/test_reporter.py tests/integration/test_state_machine_smoke.py -v`
- **New tests to write**: a phase-string-coverage test over
  `ArtifactGraph.phases()` vs. every predicate's referenced phase string;
  a gate-result-semantics test (failed gate does not satisfy the
  predicate); an `evaluate_state` ambiguity test asserting determinate
  most-advanced output; a regression test confirming no caller of
  `_last_matching_state_from_error` remains.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — not the full suite.
