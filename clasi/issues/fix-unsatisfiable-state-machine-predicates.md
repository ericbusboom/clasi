---
status: pending
type: bug
tags:
- reliability-campaign
- phase-2
- state-machine
sprint: '030'
---

# State machine: fix unsatisfiable and never-true predicates; define match semantics

## Description

The descriptive state machines that feed `clasi status` reference things
the toolchain cannot produce, so the status layer reports against a
fictional process. From the reliability review (00-review.md C8;
01-state-layer.md findings 3, 4, 6, 7; 03-hooks-guards.md F10):

1. `is_any_sprint_ticketed` queries phase `"ticketed"`; the DB only ever
   holds `"ticketing"` — the project machine's `enter-sprint` transition is
   permanently blocked (visible in every session's status block).
2. `is_review_satisfied` requires a `sprint_review` gate that
   `record_gate` rejects (`VALID_GATE_NAMES`) and skip flags nothing
   writes; the `closed` invariant can never hold.
3. Gate predicates accept a failed review (`is not None`) while
   `advance_phase` requires passed/skipped — two semantics for one row.
4. The sprint machine's `open` and `planned` states have identical
   invariants, so ambiguity is the normal path and the reporter recovers
   the answer by regexing the exception's message text.

## Acceptance criteria

- Every phase string referenced by a predicate exists in the enforced
  phase list — asserted by a test over `ArtifactGraph.phases()`.
- `sprint_review` is either recordable (added to `VALID_GATE_NAMES` and
  written by close) or removed from the machine, along with the writer-less
  skip flags, `is_tests_passing`, and `reopen_requested`.
- Gate predicates check `result in {"passed", "skipped"}`.
- `evaluate_state` defines most-advanced-match-wins; the
  exception-message parser (`_last_matching_state_from_error`) is deleted.
- The status block for this repo no longer reports `enter-sprint` blocked
  by a predicate that cannot be true.
