---
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 012 Use Cases

## SUC-001: Project transitions to `planning` after initiation writes overview

- **Actor**: CLASI state machine / `get_status` caller
- **Preconditions**: A project has been initiated (project-initiation skill ran and wrote `.clasi/design/overview.md`).
- **Main Flow**:
  1. Caller invokes `get_status` on the project.
  2. `is_overview_present` predicate is evaluated.
  3. Predicate calls `ctx.reader.overview_exists()`.
  4. Reader returns True because `.clasi/design/overview.md` exists.
  5. `uninitialized → planning` transition fires.
- **Postconditions**: `get_status` reports the project state as `planning` (not `uninitialized`).
- **Acceptance Criteria**:
  - [ ] `is_overview_present` returns True when `.clasi/design/overview.md` exists.
  - [ ] `is_overview_absent` returns False when `.clasi/design/overview.md` exists.
  - [ ] `Project.design_dir` resolves to `.clasi/design/`.
  - [ ] `ClasiStateReader.overview_exists()` is the mechanism — not `file_exists("docs/clasi/overview.md")`.

## SUC-002: Sprint predicates see artifacts written by MCP sprint tools

- **Actor**: CLASI state machine / `get_status` caller
- **Preconditions**: A sprint has been created via `create_sprint` (which writes to `.clasi/sprints/<id>-<slug>/`).
- **Main Flow**:
  1. `create_sprint` writes `sprint.md`, `usecases.md` under `.clasi/sprints/012-state-machine-path-consistency/`.
  2. Caller invokes `get_status` on the sprint.
  3. `is_sprint_doc_present` and `is_usecases_present` predicates are evaluated.
  4. Predicates resolve the sprint directory by ID-prefix glob (`012-*`) and check for `sprint.md` and `usecases.md`.
  5. Both predicates return True.
- **Postconditions**: Sprint transitions from `open` to `planned` without manual path workarounds.
- **Acceptance Criteria**:
  - [ ] `is_sprint_doc_present` returns True for a sprint directory named `<id>-<slug>`.
  - [ ] `is_usecases_present` returns True for a file named `usecases.md` (not `use-cases.md`).
  - [ ] `is_architecture_present` returns True for `architecture-update.md` in the slugged sprint dir.
  - [ ] `is_close_report_present` returns True for `close-report.md` in the slugged sprint dir.

## SUC-003: Ticket predicates see ticket files written by MCP ticket tools

- **Actor**: CLASI state machine / `get_status` caller
- **Preconditions**: A ticket has been created via `create_ticket` (which writes `<sprint-id>-<slug>.md` under the sprint's `tickets/` directory).
- **Main Flow**:
  1. `create_ticket` writes `.clasi/sprints/012-state-machine-path-consistency/tickets/012-001-my-ticket.md`.
  2. Caller invokes `get_status` on the ticket.
  3. `is_ticket_file_present` predicate is evaluated.
  4. Predicate resolves the sprint dir by ID-prefix and searches `tickets/` for a file starting with `<ticket-id>-`.
  5. Predicate returns True.
- **Postconditions**: Ticket machine transitions from `open` to its next state without error.
- **Acceptance Criteria**:
  - [ ] `is_ticket_file_present` returns True for a ticket file named `<ticket-id>-<slug>.md`.
  - [ ] `is_ticket_file_present` also returns True for a ticket file moved to `tickets/done/`.
  - [ ] Predicates use the project/sprint path model, not hardcoded `docs/clasi/` strings.

## SUC-004: The clasi repo itself initializes cleanly after `git mv`

- **Actor**: Developer / CI running CLASI on the clasi codebase
- **Preconditions**: The clasi repo has `docs/design/overview.md` but not `.clasi/design/overview.md`.
- **Main Flow**:
  1. Developer runs `git mv docs/design/overview.md .clasi/design/overview.md` (and sibling files).
  2. `get_status` is called on the clasi project.
  3. `overview_exists()` finds `.clasi/design/overview.md`.
  4. Project transitions to `planning`.
- **Postconditions**: `get_status` no longer reports `uninitialized` for the clasi repo. `state_drift` disappears from sprint/ticket status.
- **Acceptance Criteria**:
  - [ ] After `git mv`, `get_status` on the clasi repo returns project state `planning` or later.
  - [ ] No `state_drift` for sprints whose artifacts exist at `.clasi/sprints/<id>-<slug>/...`.

## SUC-005: Sprint vocabulary is internally consistent

- **Actor**: Sprint-planner agent / `detail_sprint` MCP tool
- **Preconditions**: Sprint-planner calls `detail_sprint` which sets sprint DB phase to `planning-docs`.
- **Main Flow**:
  1. `detail_sprint` advances phase to `planning-docs` in the state DB.
  2. Agent later calls `advance_sprint_phase` to move to `architecture-review`.
  3. State DB accepts `planning-docs` as a valid phase.
  4. The state machine evaluator treats `planning-docs` as known (no `state_drift` from vocabulary mismatch).
- **Postconditions**: The sprint-planner's `planning-docs` status does not trigger `state_drift` in `get_status`.
- **Acceptance Criteria**:
  - [ ] DB phase `planning-docs` does not produce a `state_drift` inconsistency.
  - [ ] Sprint status vocab in sprint.md frontmatter aligns with the DB phases.
  - [ ] Stale `planning_docs` (underscore) vocab in plugin docs is corrected to `planning-docs`.

## SUC-006: Regression suite confirms end-to-end predicate/writer agreement

- **Actor**: CI / developer running `pytest`
- **Preconditions**: Test utilities can create sprint and ticket directories in `tmp_path`.
- **Main Flow**:
  1. Test creates sprint dir `.clasi/sprints/001-my-sprint/` with `sprint.md`, `usecases.md`, `architecture-update.md`.
  2. Test creates ticket file `tickets/001-001-my-ticket.md`.
  3. Predicate functions are called against a `ClasiStateReader` pointed at `tmp_path`.
  4. All relevant predicates return True.
- **Postconditions**: Test suite confirms that artifacts created by writers satisfy their own predicates.
- **Acceptance Criteria**:
  - [ ] `test_predicates.py` overview tests use `overview_exists` mock, not `file_exists`.
  - [ ] `test_reader.py` has a test for `overview_exists()` (true/false).
  - [ ] `test_project.py` asserts `design_dir == tmp_path / ".clasi" / "design"`.
  - [ ] New integration-style test confirms `is_sprint_doc_present`, `is_usecases_present`, `is_ticket_file_present` all return True for slugged-path artifacts.
