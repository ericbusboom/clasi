---
id: "024"
title: "E2E Guessing Game Test"
status: planning
branch: sprint/024-e2e-guessing-game-test
use-cases:
- SUC-001
- SUC-002
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024: E2E Guessing Game Test

## Goals

Build end-to-end test infrastructure that validates the entire CLASI SE
process by having it build a real application from a spec. A test harness
sets up a temporary project, initializes CLASI, places a guessing game
spec, dispatches a main-controller subagent to implement it across 4
sprints, then verifies all artifacts are correct.

## Problem

CLASI has 356+ unit tests covering individual tools and modules, but no
integration test that exercises the full SE process end-to-end: project
initiation, sprint planning, ticket execution, sprint closing, and
version tagging. Process regressions (broken lifecycle transitions,
missing artifacts, incomplete ticket moves) can only be caught by manual
testing today.

## Solution

1. **E2E test harness (`run_e2e.py`)** -- A Python script that:
   - Creates a temporary project directory
   - Runs `clasi init` to install the SE process
   - Copies the guessing game spec into the project
   - Dispatches a main-controller subagent (via the Agent tool) with
     instructions to implement the spec across 4 sprints
   - Captures the result and exit status

2. **Verification script (`verify.py`)** -- A Python script that:
   - Takes a completed project directory as input
   - Verifies the guessing game works (`python -m guessing_game`)
   - Checks that 4 sprints were created and closed
   - Confirms all tickets are in `done/` directories
   - Validates dispatch logs exist and contain content
   - Runs the project's own test suite (`pytest`)

3. **Documentation** -- A README for the `tests/e2e/` directory
   explaining how to run and extend e2e tests, plus cleanup of the
   originating TODO.

## Success Criteria

- `run_e2e.py` creates a valid temporary project with CLASI initialized
- `run_e2e.py` dispatches a main-controller subagent that can execute
  the full spec
- `verify.py` validates all expected artifacts exist and are correct
- `verify.py` validates the built application works
- Tests in `tests/e2e/` directory are self-documenting

## Scope

### In Scope

- `tests/e2e/run_e2e.py` -- test harness script
- `tests/e2e/verify.py` -- verification script
- `tests/e2e/README.md` -- documentation for e2e tests
- `tests/e2e/guessing-game-spec.md` -- already exists

### Out of Scope

- Changes to the CLASI Python package (`claude_agent_skills/`)
- Changes to MCP tools (the logging tools added previously are sufficient)
- Automated CI integration (future work)
- Performance benchmarks or timing constraints
- Modifications to the guessing game spec itself

## Test Strategy

This sprint produces test infrastructure itself, so the testing approach
is layered:

- **Unit verification**: Each script (`run_e2e.py`, `verify.py`) should
  be runnable independently. `verify.py` can be pointed at any project
  directory.
- **Integration**: Running `run_e2e.py` end-to-end is the integration
  test. This is expensive (dispatches a multi-sprint subagent) and would
  be run manually or in a dedicated CI step.
- **Regression**: `uv run pytest` must continue to pass (no regressions
  to existing tests).

## Architecture Notes

This sprint adds test infrastructure only -- no changes to the CLASI
package. The test harness uses the Claude Code Agent tool to dispatch a
main-controller subagent, which in turn dispatches its own subagents
through the normal CLASI process.

The verification script is deliberately separate from the harness so it
can be run against any project directory, enabling re-verification after
manual interventions or partial runs.

Key design decisions:
- Temporary directory for isolation (no interference with this repo)
- `clasi init` for realistic project setup
- Agent tool dispatch mirrors how CLASI is actually used
- Verification checks artifacts, not just exit codes

## GitHub Issues

(None linked.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **001** -- E2E test harness (run_e2e.py)
   - use-cases: SUC-001 | depends-on: none
2. **002** -- Verification script (verify.py)
   - use-cases: SUC-002 | depends-on: none
3. **003** -- Documentation and TODO cleanup
   - use-cases: SUC-001, SUC-002 | depends-on: 001, 002
