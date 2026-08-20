---
status: pending
type: task
tags:
- reliability-campaign
- phase-2
- testing
sprint: '030'
---

# Integration test: drive a sprint through the real writers, assert three-way state agreement

## Description

Today's state-machine tests stub readers that echo whatever phase string
the predicate asks for, making vocabulary drift structurally undetectable —
that is how `"ticketed"`-vs-`"ticketing"`, the unrecordable `sprint_review`
gate, and the frontmatter/DB divergences all shipped. From the reliability
review (01-state-layer.md finding 20 and recommendation 3).

One integration test that drives a sprint through the real writers —
create → detail → gates → tickets → in-progress → done → close — using a
real temporary project (real files, real DB), asserting at every step that:

1. DB phase, frontmatter status, and computed machine state agree,
2. gate predicates and `advance_phase` agree on gate semantics,
3. `detect_inconsistencies` reports zero drift for the healthy path.

This test would have caught six of the state-layer findings before they
shipped; it permanently converts the vocabulary/wiring drift class from
"weird runtime bug" to "red test."

## Acceptance criteria

- The test exists, runs in the default suite tier, and passes only after
  the Phase 2 vocabulary/predicate/close fixes land (it is the acceptance
  test for the phase).
- A deliberate vocabulary regression (e.g. reintroducing a stray status
  string) fails it.
