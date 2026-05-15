---
id: 005-005
title: Implement all is_* predicates for project, sprint, and ticket machines
status: done
sprint: '005'
use-cases:
- SUC-006
depends-on:
- 005-003
- 005-004
issues: []
---

## Description

Create `clasi/state_machine/predicates/` sub-package with three modules
(`project.py`, `sprint.py`, `ticket.py`). Each module implements and registers
all `is_*` predicates for its machine. Predicates access external state only
via the context's `StateReader` — no direct filesystem or DB calls.

## Acceptance Criteria

- [x] Every predicate name in `clasi/schemas/state-machines/project.yaml`,
  `sprint.yaml`, and `ticket.yaml` has a corresponding registered Python
  function.
- [x] Total predicate count matches the design doc: 8 (project) + 12 sprint-only
  + 13 (ticket) = 33 predicates (`is_on_sprint_branch` shared between project
  and sprint machines, registered once). Ticket YAML has 13 predicates (not 10
  as initially estimated).
- [x] Each predicate signature is `(context: <ContextType>) -> bool`.
- [x] No predicate makes direct filesystem calls, DB calls, or subprocess
  calls — all access goes through `context.reader`.
- [x] `clasi/state_machine/predicates/__init__.py` imports all three modules
  so that all predicates are registered on `import clasi.state_machine.predicates`.
- [x] Unit tests in `tests/unit/test_state_machine/test_predicates.py` cover
  True and False cases for each predicate using a mock or stub `StateReader`.
- [x] All predicate tests pass with no skips (87 tests, 0 failures).

## Implementation Plan

### Approach

Each predicate module imports `@predicate` from `registry` and uses it to
decorate each `is_*` function. Functions call `context.reader` methods.
Example:

```python
# clasi/state_machine/predicates/project.py
from clasi.state_machine.registry import predicate
from clasi.state_machine.context import ProjectContext

@predicate("is_overview_present")
def is_overview_present(ctx: ProjectContext) -> bool:
    return ctx.reader.file_exists("docs/clasi/overview.md")

@predicate("is_overview_absent")
def is_overview_absent(ctx: ProjectContext) -> bool:
    return not ctx.reader.file_exists("docs/clasi/overview.md")
```

### Files to create

- `clasi/state_machine/predicates/__init__.py` — imports project, sprint, ticket modules.
- `clasi/state_machine/predicates/project.py` — 8 predicates.
- `clasi/state_machine/predicates/sprint.py` — 13 predicates.
- `clasi/state_machine/predicates/ticket.py` — 10 predicates.
- `tests/unit/test_state_machine/test_predicates.py`

### Predicate list by machine

**Project (8)**: `is_overview_absent`, `is_overview_present`,
`is_on_default_branch`, `is_on_sprint_branch`, `is_execution_lock_held`,
`is_execution_lock_released`, `is_any_sprint_ticketed`, `is_any_sprint_executing`.

**Sprint (13)**: `is_sprint_doc_present`, `is_architecture_present`,
`is_usecases_present`, `is_architecture_review_recorded`,
`is_pre_flight_satisfied`, `is_at_least_one_ticket`,
`is_no_other_sprint_executing`, `is_on_sprint_branch`,
`is_execution_lock_held_by_this_sprint`, `is_all_tickets_done`,
`is_review_satisfied`, `is_close_report_present`, `is_branch_merged`.

**Ticket (10)**: `is_ticket_file_present`, `is_ticket_in_done_dir`,
`is_ticket_not_in_done_dir`, `is_no_exception_block`,
`is_exception_block_present`, `is_programmer_dispatched`,
`is_sprint_executing`, `is_dependencies_done`, `is_acceptance_criteria_met`,
`is_tests_passing`, `is_blocker_identified`, `is_blocker_resolved`,
`is_reopen_requested`.

Note: ticket machine has more than 10 — count from the design doc; the
number above may be 13. Programmer should count from `ticket.yaml` (created
in ticket 002) as the authoritative source.

### Testing plan

For each predicate, write two tests: one where the reader returns the
"truthy" value and the predicate returns True, one where it returns the
"falsy" value and the predicate returns False. Use `unittest.mock.MagicMock`
or a simple stub `StateReader`. Use the `clear_registry()` fixture from
ticket 003.

### Documentation updates

Each predicate module gets a module-level docstring listing the machine it
serves and the `StateReader` methods it calls.
