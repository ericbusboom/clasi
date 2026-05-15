---
id: '002'
title: Build StatusReporter to assemble the output shape
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build StatusReporter to assemble the output shape

## Description

With `ClasiStateReader` in place (ticket 001), this ticket builds the core
output assembly logic: `reporter.py` and `formatting.py` in `clasi/status/`,
plus the `build_status` public entry point in `clasi/status/__init__.py`.

`StatusReporter` calls `evaluate_state` and `inspect_transitions` for each
machine (project, each sprint, each sprint's tickets), then assembles the
nested dict matching the YAML shape defined in the issue. `formatting.py`
serializes the dict to YAML or JSON.

## Acceptance Criteria

- [x] `clasi/status/reporter.py` defines `StatusReporter` with `build(agent, sprint_id, ticket_id) -> dict`.
- [x] `build()` returns a dict with top-level keys: `agent`, `computed_at`, `project`, `sprints`, `issues`, `notes`, `inconsistencies`.
- [x] `project:` block has `state` (from `evaluate_state`) and `available_transitions` list.
- [x] Each sprint entry has `id`, `state`, `available_transitions`, and `tickets` sub-dict with `total`, `by_state`, `details`.
- [x] Each transition entry has `name`, `to`, `fireable`, and `blocked_by` list.
- [x] `issues:` has `total`, `pending`, `assigned_to_sprint` counts.
- [x] `notes:` has `current_focus`, `allowed_next_actions`, `blocked_actions`.
- [x] `inconsistencies:` is an empty list (completed in ticket 004).
- [x] `clasi/status/formatting.py` defines `to_yaml(d) -> str` and `to_json(d) -> str`.
- [x] `clasi/status/__init__.py` exports `build_status(project, agent, sprint_id, ticket_id) -> dict`.
- [x] `NoMatchingStateError` is handled: emit `state: "unknown"` and empty transitions.
- [x] Unit tests in `tests/unit/test_status/test_reporter.py` cover dict structure with `NullStateReader`.
- [x] `uv run pytest tests/unit/test_status/` passes.
- [x] `uv run pytest` (full suite) passes with no regressions.

## Implementation Plan

### Approach

`StatusReporter.__init__(project, reader)` takes a project and a `StateReader`.
`build()` loads all three machines, evaluates states, assembles the nested dict.
Calls `detect_inconsistencies` stub (from ticket 004 skeleton).

`build_status` in `__init__.py` instantiates `ClasiStateReader(project)` and
delegates to `StatusReporter(project, reader).build(agent, sprint_id, ticket_id)`.

For `to_yaml`: use `yaml.dump(d, sort_keys=False, allow_unicode=True)`.
For `to_json`: use `json.dumps(d, indent=2, default=str)`.

### Files to create

- `clasi/status/reporter.py` — `StatusReporter` class
- `clasi/status/formatting.py` — `to_yaml`, `to_json`
- `tests/unit/test_status/test_reporter.py` — structural unit tests

### Files to modify

- `clasi/status/__init__.py` — add real `build_status` export (stub narrowing)

### Testing plan

Use `NullStateReader` to test dict structure without I/O. Verify `to_yaml`
is parseable by `yaml.safe_load`; verify `to_json` is parseable by `json.loads`.

### Documentation updates

Docstring on `StatusReporter.build()` describing the output contract.
