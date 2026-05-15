---
id: 005-004
title: Context dataclasses and StateReader protocol
status: done
sprint: '005'
use-cases:
- SUC-003
- SUC-004
- SUC-006
depends-on:
- 005-001
issues: []
---

## Description

Create `clasi/state_machine/context.py` with the three context dataclasses
(`ProjectContext`, `SprintContext`, `TicketContext`) and the `StateReader`
protocol. The `StateReader` protocol defines the narrow interface through which
all `is_*` predicates access external state (filesystem, git, DB). A
`NullStateReader` stub is provided for use in unit tests.

## Acceptance Criteria

- [x] `StateReader` is a `typing.Protocol` with methods covering all facts
  needed by the predicates in ticket 005. The method list is determined by
  implementing the predicates (do ticket 005 in the same pass if needed, or
  define placeholder methods from the design doc and fill them in ticket 005).
- [x] `ProjectContext` dataclass has at least: `reader: StateReader`.
- [x] `SprintContext` dataclass has at least: `sprint_id: str`,
  `reader: StateReader`, `project: ProjectContext`.
- [x] `TicketContext` dataclass has at least: `ticket_id: str`,
  `sprint_id: str`, `reader: StateReader`, `sprint: SprintContext`.
- [x] `NullStateReader` implements `StateReader` and returns safe defaults
  (False for bool methods, None for optional returns, empty lists for list
  returns) — suitable for instantiating contexts in tests without real I/O.
- [x] `StateReader` method surface does not exceed 15 methods total. If it
  does, surface as a note to team-lead (do not throw an exception — this is
  a sizing concern, not a conflict).
- [x] Unit tests in `tests/unit/test_state_machine/test_context.py` verify
  construction of each context type using `NullStateReader`.

## Implementation Plan

### Approach

Define `StateReader` as a `typing.Protocol` (structural subtyping — no
inheritance required for `StateReaderImpl` in sprint 006). Methods are named
after the facts they expose, e.g.:

```python
class StateReader(Protocol):
    def file_exists(self, path: str) -> bool: ...
    def git_branch(self) -> str: ...
    def execution_lock(self) -> dict | None: ...
    def sprint_phase(self, sprint_id: str) -> str: ...
    def sprint_gate(self, sprint_id: str, gate: str) -> dict | None: ...
    def sprint_branch(self, sprint_id: str) -> str: ...
    def ticket_status(self, sprint_id: str, ticket_id: str) -> str: ...
    def all_tickets_done(self, sprint_id: str) -> bool: ...
    def ticket_in_done_dir(self, sprint_id: str, ticket_id: str) -> bool: ...
    def exception_block(self, sprint_id: str, ticket_id: str) -> dict | None: ...
    def programmer_dispatched(self, sprint_id: str, ticket_id: str) -> bool: ...
    def default_branch(self) -> str: ...
```

Exact method list is finalized when implementing ticket 005 predicates. The
list above covers the predicates in `docs/design/state-machines.md` as written.

### Files to create

- `clasi/state_machine/context.py`
- `tests/unit/test_state_machine/test_context.py`

### Testing plan

Instantiate `ProjectContext(reader=NullStateReader())`. Instantiate
`SprintContext(sprint_id="001", reader=NullStateReader(), project=...)`.
Assert field access works. Verify `NullStateReader` satisfies the `StateReader`
protocol (Python's `isinstance` check with Protocol works at runtime if
`runtime_checkable` is set).

### Documentation updates

Docstring on `StateReader` should specify: "Sprint 006 provides the production
implementation. Sprint 005 tests use `NullStateReader`."
