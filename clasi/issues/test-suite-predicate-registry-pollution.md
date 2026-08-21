---
status: pending
type: bug
tags:
- testing
- state-machine
sprint: '032'
---

# Test-order pollution: a test clears the predicate registry without repopulating it

## Description

Found by the programmer implementing ticket 030-006 while running
cross-module test combinations, and reported rather than worked around.

Concatenating several test modules into one pytest invocation in a
non-default order — specifically `tests/unit/test_state_machine/` before
`tests/integration/test_state_machine_smoke.py` — fails with:

```
UnknownPredicateError: Registered predicates: []
```

Some test in the unit tier calls `clear_registry()` (or equivalent) on
the global predicate registry and does not repopulate it, so any later
module in the same process that evaluates a real state machine finds an
empty registry.

This does not reproduce under the natural full-suite collection order,
and every ticket's own scoped test command passes standalone — which is
exactly why it has survived. It is latent, not currently breaking the
gate.

## Why it is worth fixing

Global mutable state shared across tests is the classic source of
"passes alone, fails in CI" and its mirror, "passes in CI, fails alone."
Either direction wastes a debugging session on a phantom. It also means
the suite's result depends on collection order, so adding or renaming a
test file can surface a failure that has nothing to do with the change —
precisely the "weird unrelated bug" pattern the reliability campaign set
out to eliminate.

## Acceptance criteria

- [ ] Identify the test(s) that clear the registry without restoring it.
- [ ] Restore via a fixture with teardown (or an autouse fixture that
      re-registers), so no test can leak an empty registry to another.
- [ ] Add a check that the suite passes under a deliberately shuffled or
      reversed module order, so this class of pollution is caught rather
      than rediscovered.

## Related

Two smaller items noted during sprint 030, recorded here so they are not
lost — neither warrants its own issue:

- `src/clasi/close.py` carries an unused `_PHASES` import (inert; the
  ticket-004 programmer was correctly guard-blocked from a cosmetic
  cleanup after flipping its ticket to done, and stopped rather than
  routing around it).
- The ticket machine's `finish` transition can structurally never report
  `fireable: true` before `move_ticket_to_done` runs, because
  `inspect_transitions` evaluates the `done` state's
  `is_ticket_in_done_dir` invariant against the pre-action context. This
  is sprint 030's Open Question 1 — a reporting artifact, not a
  functional break, but the status output is misleading as written.
