---
id: 005-006
title: "State evaluator \u2014 evaluate_state, inspect_transitions, evaluate_predicates"
status: done
sprint: '005'
use-cases:
- SUC-003
- SUC-004
- SUC-005
depends-on:
- 005-002
- 005-003
- 005-004
- 005-005
issues: []
---

## Description

Create `clasi/state_machine/evaluator.py` implementing the three core engine
functions. This is the computational heart of the subsystem: it walks the
machine model, dispatches predicates via the registry, and returns structured
results.

## Acceptance Criteria

- [x] `evaluate_state(machine: Machine, context) -> State` iterates the
  machine's states; for each state, calls every invariant predicate; returns
  the single state whose invariants all return True.
- [x] `evaluate_state` raises `NoMatchingStateError` if no state matches.
- [x] `evaluate_state` raises `AmbiguousStateError` if more than one state
  matches (includes both matching state names in the error message).
- [x] `inspect_transitions(machine: Machine, state_name: str, context) -> list[TransitionResult]`
  returns one `TransitionResult` per outbound transition.
- [x] For each transition, conditions AND the destination state's invariants
  are both evaluated (per design doc rule: "the engine adds them automatically").
- [x] A fireable transition has `fireable=True` and `blocked_by=[]`.
- [x] A non-fireable transition has `fireable=False` and `blocked_by` contains
  the name of every predicate that returned False (conditions + destination
  invariants combined).
- [x] `inspect_transitions` raises `KeyError` if `state_name` is not in
  `machine.states`.
- [x] `evaluate_predicates(names: list[str], context) -> dict[str, bool | Exception]`
  calls each named predicate; captures per-predicate exceptions into the dict
  rather than propagating (diagnostic mode).
- [x] `evaluate_predicates` raises `UnknownPredicateError` for names not in
  the registry (fast-fail before calling any predicate).
- [x] Unit tests in `tests/unit/test_state_machine/test_evaluator.py` cover
  all success paths and all error paths listed above.

## Implementation Plan

### Approach

```python
def evaluate_state(machine, context):
    matches = []
    for state in machine.states.values():
        if all(get_predicate(inv)(context) for inv in state.invariants):
            matches.append(state)
    if len(matches) == 0:
        raise NoMatchingStateError(machine.name, list(machine.states.keys()))
    if len(matches) > 1:
        raise AmbiguousStateError([s.name for s in matches])
    return matches[0]
```

For `inspect_transitions`, collect the transition's `conditions` list plus
the destination state's `invariants` list as the full predicate set to
evaluate. Record each failing predicate name in `blocked_by`.

### Files to create

- `clasi/state_machine/evaluator.py`
- `tests/unit/test_state_machine/test_evaluator.py`

### Testing plan

Build minimal `Machine` objects in tests using dataclasses from ticket 001.
Register mock predicates using a `clear_registry()` fixture. Test scenarios:
- One state matches → correct state returned.
- No state matches → `NoMatchingStateError`.
- Two states match → `AmbiguousStateError`.
- Transition with all conditions met → `fireable=True`.
- Transition with one failing condition → `fireable=False`, `blocked_by` has
  that predicate name.
- Destination invariant fails → appears in `blocked_by`.
- `evaluate_predicates` with all passing → dict of True values.
- `evaluate_predicates` with one raising exception → exception captured in dict.

### Documentation updates

Module docstring on `evaluator.py` should describe the "conditions +
destination invariants" rule and cite the design doc.
