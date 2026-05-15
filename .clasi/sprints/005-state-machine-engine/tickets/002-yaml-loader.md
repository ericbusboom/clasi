---
id: 005-002
title: "YAML loader \u2014 read state-machine YAML files into Machine objects"
status: done
sprint: '005'
use-cases:
- SUC-001
depends-on:
- 005-001
issues: []
---

## Description

Create `clasi/state_machine/loader.py` and the three YAML source files
(`project.yaml`, `sprint.yaml`, `ticket.yaml`) in
`clasi/schemas/state-machines/`. The loader reads a named machine from the
package data directory and constructs the in-memory `Machine` object.

## Acceptance Criteria

- [x] Directory `clasi/schemas/state-machines/` exists and contains
  `project.yaml`, `sprint.yaml`, and `ticket.yaml`.
- [x] Each YAML file faithfully transcribes the machine definition from
  `docs/design/state-machines.md` (states, invariants, transitions,
  conditions, action names, predicate descriptions).
- [x] `load_machine(name: str) -> Machine` resolves the YAML file via
  `importlib.resources.files("clasi.schemas").joinpath("state-machines", name + ".yaml")`.
- [x] Loading each of the three machines returns a `Machine` object with
  the correct number of states and transitions (verified in tests).
- [x] A missing name raises `FileNotFoundError` with a clear message.
- [x] Invalid YAML (syntax error) raises `MachineSyntaxError` wrapping the
  underlying parse error.
- [x] A YAML file missing required keys (e.g., `machine:` or `states:`)
  raises `MachineSyntaxError` with the offending key named.
- [x] `pyproject.toml` (or `MANIFEST.in`) ensures `clasi/schemas/state-machines/*.yaml`
  is included in the installed package data.
- [x] Unit tests in `tests/unit/test_state_machine/test_loader.py` cover:
  round-trip load of all three machines, missing name, invalid YAML,
  missing required key.

## Implementation Plan

### Approach

Use `importlib.resources.files()` (Python 3.9+) for package-relative path
resolution — same pattern as `clasi/state_db_class.py` line 23. Parse with
`yaml.safe_load`. Construct `Machine` → `State` → `Transition` objects by
walking the parsed dict.

### Files to create

- `clasi/schemas/state-machines/project.yaml` — Project machine definition.
- `clasi/schemas/state-machines/sprint.yaml` — Sprint machine definition.
- `clasi/schemas/state-machines/ticket.yaml` — Ticket machine definition.
- `clasi/state_machine/loader.py` — `load_machine(name)` function.
- `tests/unit/test_state_machine/test_loader.py` — loader tests.

### Files to modify

- `pyproject.toml` — confirm `clasi/schemas/**/*.yaml` is in `[tool.setuptools.package-data]`
  or equivalent; add `state-machines/` sub-directory if needed.

### YAML file structure (follows design doc format exactly)

```yaml
machine: project
context: ProjectContext
initial: uninitialized
states:
  uninitialized:
    description: "..."
    invariants:
      - is_overview_absent
    transitions:
      initialize:
        to: planning
        conditions: []
        action: write_overview
predicates:
  is_overview_absent:
    description: "..."
actions:
  write_overview:
    description: "..."
```

### Testing plan

Load each machine and assert: `machine.name`, `len(machine.states)`,
presence of specific state names, invariant lists, and transition condition
lists. Use `importlib.resources` in the test — do not hardcode paths.

### Documentation updates

None required beyond inline docstrings.
