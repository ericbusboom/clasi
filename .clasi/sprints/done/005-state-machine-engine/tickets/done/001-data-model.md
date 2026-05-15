---
id: 005-001
title: Define in-memory data model (Machine, State, Transition dataclasses)
status: done
sprint: '005'
use-cases:
- SUC-001
- SUC-003
- SUC-004
depends-on: []
issues: []
---

## Description

Create `clasi/state_machine/models.py` with the pure Python dataclasses that
represent the in-memory state machine model. This is the shared vocabulary used
by every other module in the subsystem. No I/O, no registry, no evaluation
logic.

## Acceptance Criteria

- [x] `Machine` dataclass has fields: `name` (str), `context_type` (str),
  `initial` (str), `states` (dict[str, State]).
- [x] `State` dataclass has fields: `name` (str), `description` (str),
  `invariants` (list[str]), `transitions` (dict[str, Transition]).
- [x] `Transition` dataclass has fields: `name` (str), `to` (str),
  `conditions` (list[str]), `action` (str | None).
- [x] `TransitionResult` dataclass has fields: `name` (str), `to` (str),
  `fireable` (bool), `blocked_by` (list[str]).
- [x] All five exception types are defined in `models.py`:
  `MachineSyntaxError`, `DuplicatePredicateError`, `UnknownPredicateError`,
  `NoMatchingStateError`, `AmbiguousStateError`.
- [x] All dataclasses are frozen (immutable) or use `__slots__`; none carry
  mutable default arguments.
- [x] `clasi/state_machine/__init__.py` exists (may be empty at this stage).
- [x] `clasi/state_machine/models.py` is importable without errors.
- [x] Unit tests in `tests/unit/test_state_machine/test_models.py` verify
  construction and immutability of each dataclass.

## Implementation Plan

### Approach

Pure Python dataclasses using `@dataclass(frozen=True)` or `dataclass` with
explicit `__hash__`. No external dependencies beyond the standard library.

### Files to create

- `clasi/state_machine/__init__.py` — empty at this stage; will be populated
  in ticket 007.
- `clasi/state_machine/models.py` — all dataclasses and exceptions.
- `tests/unit/test_state_machine/__init__.py` — empty.
- `tests/unit/test_state_machine/test_models.py` — construction, field access,
  exception hierarchy tests.

### Testing plan

Instantiate each dataclass with sample data; assert field values. Attempt to
mutate a frozen field; assert `FrozenInstanceError`. Verify exception
inheritance (all custom exceptions derive from a common `StateMachineError`
base for easy catching).

### Documentation updates

None required. Models are self-documenting via type annotations.
