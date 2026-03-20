---
id: "024"
title: "E2E Test and Process Improvements"
status: planning
branch: sprint/024-e2e-guessing-game-test
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024: E2E Test and Process Improvements

## Goals

This sprint has two tracks:

1. **E2E test infrastructure** -- Build end-to-end test infrastructure
   that validates the entire CLASI SE process by having it build a real
   application from a spec. A test harness sets up a temporary project,
   initializes CLASI, places a guessing game spec, dispatches a
   team-lead subagent to implement it across 4 sprints, then verifies
   all artifacts are correct.

2. **Process improvements** -- Fix agent delegation boundaries and add
   TODO lifecycle traceability. The delegation fixes (tickets 004, 006,
   007) establish a consistent principle: controllers provide goals and
   references, subordinate agents make implementation decisions. The
   architecture revision (005) replaces full architecture copies with
   lightweight update documents. The cross-referencing ticket (008) adds
   bidirectional traceability between TODOs and tickets via frontmatter
   fields and MCP tool automation.

## Problem

### E2E testing gap

CLASI has 356+ unit tests covering individual tools and modules, but no
integration test that exercises the full SE process end-to-end: project
initiation, sprint planning, ticket execution, sprint closing, and
version tagging. Process regressions (broken lifecycle transitions,
missing artifacts, incomplete ticket moves) can only be caught by manual
testing today.

### Agent delegation boundaries

The team-lead agent does the work of subordinate agents. When delegating
to the todo-worker, it pre-formats TODO content instead of passing raw
stakeholder input. When delegating to the sprint planner, it provides
fully pre-digested ticket specifications instead of high-level goals
and TODO references. This makes subordinate agents into transcription
agents rather than planning/structuring agents.

### Architecture process overhead

Each sprint copies the full architecture document and the architect
rewrites it from scratch. This is expensive and error-prone. A
lightweight update model would be more efficient.

### TODO traceability gap

When a TODO is picked up for implementation, there is no visible link
between the TODO and the sprint/ticket addressing it. TODOs either
disappear immediately or sit in the pending list with no indication of
progress. Tickets also lack a backlink to their source TODO(s).

## Solution

### Track 1: E2E test infrastructure

1. **E2E test harness (`run_e2e.py`)** -- A Python script that:
   - Creates a temporary project directory
   - Runs `clasi init` to install the SE process
   - Copies the guessing game spec into the project
   - Dispatches a team-lead subagent (via the Agent tool) with
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

### Track 2: Process improvements

4. **Team-lead identity binding** -- Update CLAUDE.md and AGENTS.md so
   the top-level Claude session explicitly knows it is the team-lead
   and dispatches to subagents rather than writing files directly.

5. **Architecture process revision** -- Replace full architecture copies
   per sprint with lightweight architecture-update documents. Add an
   on-demand consolidation skill for merging updates into a full
   architecture document.

6. **TODO delegation fix** -- Update team-lead and todo-worker agent
   definitions so the team-lead passes raw stakeholder text to the
   todo-worker instead of pre-formatting it.

7. **Sprint planner delegation fix** -- Update team-lead and sprint-
   planner agent definitions so the team-lead provides high-level goals
   and TODO references instead of pre-digested ticket specifications.
   Depends on the TODO delegation fix (006) to ensure a coherent
   delegation philosophy.

8. **TODO-sprint-ticket cross-references** -- Implement bidirectional
   traceability: TODOs get sprint/ticket IDs in frontmatter when tickets
   are created from them; tickets get a `todo` frontmatter field
   pointing to source TODO(s). MCP tools (`create_ticket`,
   `close_sprint`, `list_todos`) are updated to facilitate this
   automatically.

## Success Criteria

### E2E test infrastructure
- `run_e2e.py` creates a valid temporary project with CLASI initialized
- `run_e2e.py` dispatches a team-lead subagent that can execute
  the full spec
- `verify.py` validates all expected artifacts exist and are correct
- `verify.py` validates the built application works
- Tests in `tests/e2e/` directory are self-documenting

### Process improvements
- Team-lead sessions self-identify and dispatch rather than writing directly
- Architecture process uses lightweight updates instead of full copies
- Team-lead passes raw input to todo-worker and goals to sprint planner
- TODOs show sprint/ticket linkage while work is in progress
- Tickets have `todo` frontmatter linking back to source TODO(s)
- MCP tools automate cross-referencing on ticket creation and sprint close

## Scope

### In Scope

- `tests/e2e/run_e2e.py` -- test harness script
- `tests/e2e/verify.py` -- verification script
- `tests/e2e/README.md` -- documentation for e2e tests
- `tests/e2e/guessing-game-spec.md` -- already exists
- CLAUDE.md / AGENTS.md -- team-lead identity binding
- `create_sprint` / `close_sprint` -- revise architecture process to use lightweight updates
- Architect agent definition -- write updates instead of full rewrites
- New consolidation skill for on-demand architecture merging
- Team-lead agent definition -- pass raw stakeholder text to todo-worker
- Todo-worker agent definition -- accept raw input, produce structured TODOs
- Dispatch protocol -- support raw-text delegation pattern
- Team-lead agent definition -- provide goals/TODO refs to sprint planner, not pre-digested tickets
- Sprint-planner agent definition -- own ticket decomposition, scoping, and specification
- `create_ticket` MCP tool -- accept optional `todo` parameter for cross-referencing
- `close_sprint` MCP tool -- move linked TODOs to done on sprint close
- `list_todos` MCP tool -- show sprint/ticket linkage for in-progress TODOs
- Ticket frontmatter -- `todo` field pointing back to source TODO(s)

### Out of Scope

- Changes to the CLASI Python package (`claude_agent_skills/`) beyond the MCP tool updates listed above
- Automated CI integration (future work)
- Performance benchmarks or timing constraints
- Modifications to the guessing game spec itself

## Test Strategy

### Track 1: E2E test infrastructure

This track produces test infrastructure itself, so the testing approach
is layered:

- **Unit verification**: Each script (`run_e2e.py`, `verify.py`) should
  be runnable independently. `verify.py` can be pointed at any project
  directory.
- **Integration**: Running `run_e2e.py` end-to-end is the integration
  test. This is expensive (dispatches a multi-sprint subagent) and would
  be run manually or in a dedicated CI step.
- **Regression**: `uv run pytest` must continue to pass (no regressions
  to existing tests).

### Track 2: Process improvements

- **MCP tool changes** (005, 008): Unit tests for modified `create_sprint`,
  `close_sprint`, `create_ticket`, and `list_todos` behavior.
- **Agent definition changes** (004, 006, 007): Manual verification by
  starting sessions and confirming agents identify correctly and delegate
  appropriately.
- **Regression**: `uv run pytest` must continue to pass for all tickets.

## Architecture Notes

This sprint has two tracks:

**Track 1: E2E test infrastructure** -- The test harness uses the Claude
Code Agent tool to dispatch a team-lead subagent, which in turn
dispatches its own subagents through the normal CLASI process. The
verification script is deliberately separate from the harness so it can
be run against any project directory.

Key design decisions:
- Temporary directory for isolation (no interference with this repo)
- `clasi init` for realistic project setup
- Agent tool dispatch mirrors how CLASI is actually used
- Verification checks artifacts, not just exit codes

**Track 2: Process improvements** -- Agent delegation boundaries and
TODO lifecycle cross-referencing. The delegation tickets (004, 006, 007)
establish a consistent principle: controllers provide goals and
references, subordinate agents make implementation decisions. The
cross-referencing ticket (008) adds bidirectional traceability between
TODOs and tickets via frontmatter fields and MCP tool automation.

## GitHub Issues

(None linked.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

### Track 1: E2E Test Infrastructure

1. **001** -- E2E test harness (run_e2e.py)
   - use-cases: SUC-001 | depends-on: none
2. **002** -- Verification script (verify.py)
   - use-cases: SUC-002 | depends-on: none
3. **003** -- Documentation and TODO cleanup
   - use-cases: SUC-001, SUC-002 | depends-on: 001, 002

### Track 2: Process Improvements

4. **004** -- Team-lead identity binding
   - use-cases: SUC-003 | depends-on: none | todo: team-lead-identity-binding.md
5. **005** -- Revise architecture process
   - use-cases: SUC-005 | depends-on: none | todo: revise-architecture-process.md
6. **006** -- Fix TODO delegation
   - use-cases: SUC-003 | depends-on: none | todo: fix-todo-delegation.md
7. **007** -- Fix team-lead over-specification to sprint planner
   - use-cases: SUC-003 | depends-on: 006 | todo: team-lead-over-specifies-tickets-to-sprint-planner.md
8. **008** -- TODO-sprint-ticket cross-references
   - use-cases: SUC-004 | depends-on: none | todo: todo-sprint-ticket-cross-references.md
9. **009** -- Subagent dispatch logging at all levels
   - use-cases: SUC-003 | depends-on: none | todo: subagent-dispatch-logging-at-all-levels.md
10. **010** -- Append subagent response to dispatch log
    - use-cases: SUC-003 | depends-on: none | todo: append-subagent-response-to-dispatch-log.md
11. **011** -- Missing sub-dispatch logs in e2e output
    - use-cases: SUC-003 | depends-on: 009 | todo: missing-sub-dispatch-logs-in-e2e-output.md
