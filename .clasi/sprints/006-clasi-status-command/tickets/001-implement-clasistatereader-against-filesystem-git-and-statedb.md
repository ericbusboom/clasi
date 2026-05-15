---
id: '001'
title: Implement ClasiStateReader against filesystem, git, and StateDB
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
depends-on: []
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement ClasiStateReader against filesystem, git, and StateDB

## Description

Sprint 005 shipped the state machine engine with `NullStateReader` as the
only `StateReader` implementation. Every predicate returns a safe default
(`False`) until a real implementation exists, making `evaluate_state` and
`inspect_transitions` useless in production.

This ticket creates `clasi/status/` as a new package and implements
`ClasiStateReader` in `clasi/status/reader.py`. `ClasiStateReader` satisfies
the `StateReader` protocol defined in `clasi/state_machine/context.py` by
reading real data from the filesystem, git subprocess calls, and `StateDB`.

This is the foundation ticket: tickets 002-008 all depend on it.

## Acceptance Criteria

- [x] `clasi/status/__init__.py` exists (package marker; exports `build_status` and `narrow_status` as stubs for now).
- [x] `clasi/status/reader.py` defines `ClasiStateReader` that satisfies `isinstance(ClasiStateReader(project), StateReader)`.
- [x] All 20 `StateReader` protocol methods are implemented:
  - `file_exists(path)` — delegates to `Path(project.root / path).exists()`.
  - `git_branch()` — runs `git branch --show-current` in `project.root`.
  - `default_branch()` — reads from git config or falls back to `"master"`.
  - `execution_lock()` — calls `StateDB.get_lock_holder()`.
  - `sprint_phase(sprint_id)` — calls `StateDB.get_phase(sprint_id)`.
  - `sprint_gate(sprint_id, gate)` — calls `StateDB.get_gate_result(sprint_id, gate)`.
  - `sprint_branch(sprint_id)` — reads sprint.md frontmatter `branch:` field.
  - `ticket_status(sprint_id, ticket_id)` — reads ticket frontmatter `status:`.
  - `all_tickets_done(sprint_id)` — checks all tickets in sprint's `tickets/` dir (not `tickets/done/` — those are already done) have `status: done`.
  - `ticket_in_done_dir(sprint_id, ticket_id)` — checks if ticket file is under `tickets/done/`.
  - `exception_block(sprint_id, ticket_id)` — reads ticket frontmatter `exception:` block.
  - `programmer_dispatched(sprint_id, ticket_id)` — reads ticket frontmatter; check for a `dispatched_at:` field or `status: in-progress`; document decision in code.
  - `sprint_flag(sprint_id, flag)` — reads sprint.md frontmatter for the flag key.
  - `branch_merged(sprint_id)` — checks if `sprint_branch(sprint_id)` is merged into `default_branch()` via `git branch --merged`.
  - `dependencies_done(sprint_id, ticket_id)` — reads ticket `depends-on:` list and checks each dependency's `ticket_status`.
  - `acceptance_criteria_met(sprint_id, ticket_id)` — checks all `- [x]` checkboxes are checked in ticket body; returns False if any `- [ ]` remain.
  - `tests_passing()` — returns the value of `.clasi/test-cache` marker if present, else `False`. Document this clearly.
  - `blocker_identified(sprint_id, ticket_id)` — checks if ticket frontmatter has a non-empty `exception:` block.
  - `blocker_resolved(sprint_id, ticket_id)` — checks if `exception:` block is present and has a `resolved: true` field.
  - `reopen_requested(sprint_id, ticket_id)` — checks if ticket frontmatter has `reopen_requested: true`.
  - `any_sprint_in_phase(phase)` — iterates all sprints and checks `StateDB.get_phase()`.
  - `ticket_count(sprint_id)` — counts `.md` files in `tickets/` (excluding `done/` subdir).
- [x] All methods handle `FileNotFoundError`, missing DB rows, and subprocess errors gracefully (return safe defaults).
- [x] Unit tests in `tests/unit/test_status/test_reader.py` use a temporary directory fixture to verify each method against real filesystem state.
- [x] `uv run pytest tests/unit/test_status/test_reader.py` passes.
- [x] `uv run pytest` (full suite) passes with no regressions.

## Implementation Plan

### Approach

Create `clasi/status/` package with `__init__.py` (stub) and `reader.py`.
`ClasiStateReader.__init__(project: Project)` stores the project reference.
Each method is a direct read — no caching, no mutations.

For git operations, use `subprocess.run(["git", ...], cwd=project.root, ...)`.
Wrap in try/except for robustness.

For `tests_passing()`: check `(project.clasi_dir / "test-cache").exists()`.
Write a comment explaining this is a deliberate deferral; the file is written
by CI or a post-commit hook, not by `clasi status` itself.

For `programmer_dispatched()`: implement as `ticket_status(sprint_id, ticket_id) == "in-progress"`. This is a reasonable proxy — a programmer has been dispatched when the ticket is in-progress. Document this in a comment.

### Files to create

- `clasi/status/__init__.py` — package init, stub exports
- `clasi/status/reader.py` — `ClasiStateReader` class
- `tests/unit/test_status/__init__.py` — empty
- `tests/unit/test_status/test_reader.py` — unit tests with tmp_path fixture

### Files to modify

None (tickets 002+ will add to `clasi/status/__init__.py`).

### Testing plan

Use `pytest`'s `tmp_path` fixture to create a minimal CLASI project structure.
Test each method with both the positive case (feature present) and the negative
case (feature absent). Git method tests can use `git init` in `tmp_path`.

### Documentation updates

Add docstring to `ClasiStateReader` explaining each method's data source.
