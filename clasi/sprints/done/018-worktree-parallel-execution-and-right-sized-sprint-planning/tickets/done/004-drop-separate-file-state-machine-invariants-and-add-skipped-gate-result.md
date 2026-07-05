---
id: '004'
title: Drop separate-file state machine invariants and add skipped gate result
status: done
use-cases:
- SUC-004
- SUC-005
depends-on:
- '003'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Drop separate-file state machine invariants and add skipped gate result

## Description

Issue B Part 2. Two independent-but-related changes to the declarative
YAML state machine and the linear StateDB gate system (the pre-existing
"two state models" caveat — this ticket must handle both).

**1. Declarative state machine (`src/clasi/schemas/state-machines/
sprint.yaml`)**: remove `is_architecture_present` and `is_usecases_present`
from the `invariants:` lists of the `planned`, `pre-flight`, and
`ticketed` states. `is_sprint_doc_present` remains in all three. Delete
the two predicate descriptions from the `predicates:` section at the
bottom of the same file.

**2. Predicate implementations (`src/clasi/state_machine/predicates/
sprint.py`)**: delete the `is_architecture_present` (currently lines
~35-38) and `is_usecases_present` (currently lines ~41-44) predicate
functions and their `@predicate(...)` registrations. Grep for any other
reference to these predicate names (registry lookups, tests) before
deleting.

**3. StateDB gate-result enum (`src/clasi/state_db_class.py`)**: this is
the concrete gap found during architecture review (see
architecture-update.md Open Questions #1, resolved). `VALID_GATE_RESULTS`
(currently line 27) is `{"passed", "failed"}` — a closed set that does
**not** include `"skipped"`. `record_gate` (currently ~line 272) raises
`ValueError` if `result not in VALID_GATE_RESULTS`. Add `"skipped"` to
`VALID_GATE_RESULTS`. Confirm `is_architecture_review_recorded`
(predicates/sprint.py, checks record *presence* only, not its result
value) and `is_pre_flight_satisfied`/`is_review_satisfied` (which check
for a *specific* gate name's presence, e.g. `stakeholder_approval`, not
`architecture_review`) are unaffected — they should already treat any
recorded value (including `skipped`) as satisfying, since they only test
`is not None`. If any other code path branches on `gate_result ==
"passed"` specifically for `architecture_review` (e.g. a status-rendering
or reporting function), that code must treat `"skipped"` as equivalent to
satisfied-but-distinguishable — flag such call sites for correction here.

This ticket depends on ticket 003 (the `Sprint` object rewrite) landing
first so the state-machine relaxation is validated against the
already-updated `Sprint` behavior, not the old one.

## Acceptance Criteria

- [x] `sprint.yaml`'s `planned`, `pre-flight`, and `ticketed` states list
      only `is_sprint_doc_present` (plus their other existing invariants,
      unchanged) — `is_architecture_present`/`is_usecases_present` are
      gone from all three.
- [x] The `predicates:` section of `sprint.yaml` no longer documents
      `is_architecture_present`/`is_usecases_present`.
- [x] `predicates/sprint.py` no longer defines
      `is_architecture_present`/`is_usecases_present`.
- [x] `VALID_GATE_RESULTS` in `state_db_class.py` includes `"skipped"`
      alongside `"passed"` and `"failed"`.
- [x] `record_gate_result(sprint_id, "architecture_review", "skipped")`
      succeeds (does not raise) and
      `is_architecture_review_recorded` returns `True` for that sprint
      afterward.
- [x] A sprint with only `sprint.md` (no `usecases.md`/
      `architecture-update.md` on disk) can advance through `planned` →
      `pre-flight` → `ticketed` given the other existing invariants are
      satisfied.
- [x] Any status-rendering code that special-cased `architecture_review
      == "passed"` is confirmed to also handle `"skipped"` sensibly (not
      as a failure).

## Files to create or modify

- `src/clasi/schemas/state-machines/sprint.yaml`
- `src/clasi/state_machine/predicates/sprint.py`
- `src/clasi/state_db_class.py`

## Testing

- **Existing tests to run**: state-machine test suite (grep for
  `is_architecture_present`/`is_usecases_present` in `tests/` first —
  update or remove those assertions), `record_gate`/`record_gate_result`
  tests, full `uv run pytest`.
- **New tests to write**: predicate-registry test confirming the two
  predicates are no longer registered; `record_gate` test for
  `result="skipped"` succeeding; a state-machine transition test driving
  a `sprint.md`-only sprint from `planned` to `ticketed`; a test that
  `is_architecture_review_recorded` returns `True` after a `skipped`
  record.
- **Verification command**: `uv run pytest`

## Completion Notes

Implemented together with tickets 002, 003, and 005 as one atomic
commit.

**Concrete gate-branching fix found and applied** (per the ticket's
instruction to grep for code branching on `architecture_review ==
"passed"`): `StateDB.advance_phase()` in `state_db_class.py` (around
line 244, pre-change) checked `gate_row["result"] != "passed"` to decide
whether a phase-gate requirement was satisfied — this is the "linear
StateDB gate system" the ticket description flags as a second, separate
model from the declarative predicates. A `"skipped"` result would have
been rejected as not-passed and blocked advancement. Fixed by
introducing `_SATISFYING_GATE_RESULTS = {"passed", "skipped"}` and
checking membership in that set instead of exact equality to `"passed"`
— `"failed"` still blocks. Covered by
`test_skipped_gate_satisfies_advance_phase` in `tests/unit/test_state_db.py`.

**Architecture-review finding (flagging for team-lead, not blocking)**:
removing `is_architecture_present`/`is_usecases_present` makes the
`open` and `planned` states in `sprint.yaml` share an identical
invariant set (`is_sprint_doc_present` only) — they were previously
distinguished by exactly the two predicates this ticket removes. This
means `evaluate_state()` now raises `AmbiguousStateError` for any sprint
that has only `sprint.md` (i.e. every sprint between `create_sprint` and
`detail_promote`, and every `planned`-phase sprint with no separate
files). This is **not a crash in practice**: `status/reporter.py`
already anticipated `AmbiguousStateError` as a possible outcome of
overlapping invariants and has a pre-existing fallback
(`_last_matching_state_from_error`) that picks the more-advanced
matching state — which resolves correctly to `"planned"` here, since
declaration order in the YAML lists `open` before `planned`. Verified
this resolves correctly via
`tests/integration/test_status_e2e.py::TestInconsistencyDetection` and
`tests/unit/test_state_machine/test_predicate_path_agreement.py::TestSprintMdOnlySprintTransitionsPlannedToTicketed`.
One existing test
(`test_state_drift_entry_produced`) relied on the `open`/`planned`
distinction to manufacture a state-drift scenario declared as
`"planned"`; updated it to use `"ticketed"` instead (still genuinely
distinguishable — requires `is_pre_flight_satisfied`/
`is_at_least_one_ticket`), preserving its actual intent (prove
state-drift detection works) without relying on the now-collapsed
distinction. The architecture-update.md's "strict relaxation, no
previously-valid transition becomes invalid" framing is correct for the
DB-driven linear phase machine, but the declarative `sprint.yaml`
machine's `open`/`planned` states are no longer mutually exclusive by
construction — recommend a future ticket either merge `open` into
`planned` (they're now behaviorally identical) or find a new
distinguishing signal if the distinction is still wanted for status
reporting.
