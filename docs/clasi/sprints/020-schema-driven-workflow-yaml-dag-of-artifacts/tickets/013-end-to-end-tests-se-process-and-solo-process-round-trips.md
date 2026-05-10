---
id: "013"
title: "End-to-end tests: se-process and solo-process round-trips"
status: todo
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004, SUC-005, SUC-006]
depends-on: ["009", "012"]
github-issue: ""
todo: "schema-driven-workflow-yaml-dag.md"
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# End-to-end tests: se-process and solo-process round-trips

## Description

Write comprehensive end-to-end tests that exercise the full schema stack for
both `se-process` and `solo-process`. These tests load the actual shipped
schema files (as package data), not hand-crafted fixtures. They verify:

- Both schemas load without errors.
- The derived `PHASES` list from each schema matches expectations.
- `ArtifactGraph` queries return correct values.
- `clasi schema validate` exits 0 for both schemas.
- `clasi init --process solo` + server startup selects the solo schema.

These are the tests the architecture-update says "load them in CI."

## Acceptance Criteria

- [ ] `test_se_process_round_trip`: loads `se-process/schema.yaml` via `loader.load()`; asserts `schema.name == "se-process"`; asserts `ArtifactGraph(schema).phases() == ["roadmap", "planning-docs", "architecture-review", "stakeholder-review", "ticketing", "executing", "closing", "done"]`.
- [ ] `test_solo_process_round_trip`: loads `solo-process/schema.yaml`; asserts `ArtifactGraph(schema).phases() == ["roadmap", "planning-docs", "ticketing", "executing", "closing", "done"]`.
- [ ] `test_se_gate_for_architecture_review`: `ArtifactGraph.gate_for("architecture-review")` returns `GateSpec(kind="review", record="architecture_review")`.
- [ ] `test_se_gate_for_stakeholder_review`: `ArtifactGraph.gate_for("stakeholder-review")` returns `GateSpec(kind="stakeholder-review", record="stakeholder_approval")`.
- [ ] `test_solo_no_architecture_review_phase`: `"architecture-review"` is not in `ArtifactGraph(solo_schema).phases()`.
- [ ] `test_se_phases_match_state_db_phases`: `ArtifactGraph(se_schema).phases()` equals the `PHASES` list from `state_db_class.py` (validates the unconditional migration from ticket 009 is correct).
- [ ] `test_cli_validate_se_schema`: `CliRunner` invokes `clasi schema validate <se-schema-path>`; exit code 0.
- [ ] `test_cli_validate_solo_schema`: `CliRunner` invokes `clasi schema validate <solo-schema-path>`; exit code 0.
- [ ] All tests live in `tests/clasi/schemas/test_round_trip.py`.
- [ ] `uv run pytest` passes, including the full existing test suite.

## Implementation Plan

**Approach**: Use `importlib.resources` to resolve the shipped schema paths
inside tests, so tests work both in development (editable install) and in CI.
The `PHASES` equality check is the critical integration assertion: if the
schema topo-sort order ever drifts from what `state_db_class.py` expects, this
test catches it.

**Files to create**:
- `tests/clasi/schemas/test_round_trip.py`

**Files to modify**:
- None (this is a test-only ticket)

**Testing plan**: This ticket IS the tests. Run `uv run pytest tests/clasi/schemas/test_round_trip.py -v` to see all assertions. Run the full suite to confirm no regressions: `uv run pytest`.

**Documentation updates**: None.
