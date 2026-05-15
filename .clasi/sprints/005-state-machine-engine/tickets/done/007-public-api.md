---
id: 005-007
title: "Public engine API \u2014 clasi/state_machine/__init__.py entry points"
status: done
sprint: '005'
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
depends-on:
- 005-006
issues: []
---

## Description

Populate `clasi/state_machine/__init__.py` with the public entry points that
sprint 006 will consume. This ticket also ensures that importing
`clasi.state_machine` auto-registers all predicates (by importing the
predicates sub-package), and writes an integration smoke test that exercises
the full load → evaluate → inspect pipeline against real YAML.

## Acceptance Criteria

- [x] `from clasi.state_machine import load_machine` works and returns a
  `Machine` for any of the three machine names.
- [x] `from clasi.state_machine import evaluate_state` works.
- [x] `from clasi.state_machine import inspect_transitions` works.
- [x] `from clasi.state_machine import evaluate_predicates` works.
- [x] `from clasi.state_machine import (ProjectContext, SprintContext, TicketContext, StateReader)` works.
- [x] `from clasi.state_machine import (MachineSyntaxError, DuplicatePredicateError, UnknownPredicateError, NoMatchingStateError, AmbiguousStateError)` works.
- [x] Importing `clasi.state_machine` triggers import of
  `clasi.state_machine.predicates` (which registers all 31+ predicates).
  `list_predicates()` returns all names after a bare `import clasi.state_machine`.
- [x] Integration smoke test in `tests/integration/test_state_machine_smoke.py`:
  load the sprint machine, create a `SprintContext` with `NullStateReader`,
  call `evaluate_state` (will raise `NoMatchingStateError` since NullStateReader
  returns False for everything — that is the expected result), and call
  `inspect_transitions` for the `open` state.
- [x] `__all__` is defined listing all public names.
- [x] No circular imports (verify by running `python -c "import clasi.state_machine"`).

## Implementation Plan

### Approach

```python
# clasi/state_machine/__init__.py
from clasi.state_machine.models import (
    Machine, State, Transition, TransitionResult,
    MachineSyntaxError, DuplicatePredicateError, UnknownPredicateError,
    NoMatchingStateError, AmbiguousStateError,
)
from clasi.state_machine.loader import load_machine
from clasi.state_machine.registry import get_predicate, list_predicates
from clasi.state_machine.evaluator import evaluate_state, inspect_transitions, evaluate_predicates
from clasi.state_machine.context import ProjectContext, SprintContext, TicketContext, StateReader, NullStateReader
import clasi.state_machine.predicates  # side-effect: registers all predicates

__all__ = [
    "load_machine",
    "evaluate_state", "inspect_transitions", "evaluate_predicates",
    "get_predicate", "list_predicates",
    "ProjectContext", "SprintContext", "TicketContext", "StateReader", "NullStateReader",
    "Machine", "State", "Transition", "TransitionResult",
    "MachineSyntaxError", "DuplicatePredicateError", "UnknownPredicateError",
    "NoMatchingStateError", "AmbiguousStateError",
]
```

### Files to modify

- `clasi/state_machine/__init__.py` — populate with public API (was empty
  from ticket 001).

### Files to create

- `tests/integration/test_state_machine_smoke.py` — smoke test.

### Testing plan

Integration smoke test uses real YAML files (from the installed package data)
and real predicates (registered by the import). Uses `NullStateReader` so no
real filesystem or DB access is needed. Verifies that the pipeline is wired end
to end: load → context → evaluate (expected `NoMatchingStateError` since all
predicates return False with NullStateReader) → inspect_transitions returns a
list with correct `name` and `to` fields.

### Documentation updates

Add a module docstring to `__init__.py` describing the four entry points and
the sprint 006 consumption pattern. Note that sprint 006 must supply a
`StateReaderImpl` to get meaningful results from `evaluate_state`.
