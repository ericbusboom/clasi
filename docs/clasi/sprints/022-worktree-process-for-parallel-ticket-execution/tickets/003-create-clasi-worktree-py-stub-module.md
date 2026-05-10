---
id: "003"
title: "Create clasi/worktree.py stub module"
status: todo
use-cases:
  - SUC-005
  - SUC-006
depends-on:
  - "002"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create clasi/worktree.py stub module

## Description

Create `clasi/worktree.py` as a new, standalone stub module that defines the
public API for the worktree lifecycle. Every function raises `NotImplementedError`
with a docstring describing its contract as specified in the design document
(ticket 002). This gives a single future attachment point for the parallel
implementation and makes the intended API visible to code review before any
real logic is written.

**Programmer decision gate**: If ticket 001's audit reveals that no existing
production code references worktrees (which is expected — only archived docs
and a log label are present), then the stub module is still valuable as an
API declaration. Proceed with the stub. If the programmer judges the stub adds
no value, note the decision in the commit message and reduce this ticket to a
no-op commit with a clear explanation. Do not silently skip.

This sprint is design-only. The stub raises `NotImplementedError` for all
functions. No caller in the existing codebase imports this module.

## Acceptance Criteria

- [ ] `clasi/worktree.py` is created.
- [ ] Module docstring references `docs/clasi/design/worktree-process.md` as the
      authoritative spec.
- [ ] Module imports only from Python stdlib (`subprocess`, `json`, `pathlib`,
      `datetime`). No CLASI package imports.
- [ ] The following functions are defined as stubs (each raises
      `NotImplementedError` or returns a documented sentinel):
      - `create_worktree(repo_root: Path, sprint_id: str, ticket_id: str) -> Path`
      - `create_ticket_branch(worktree_path: Path, sprint_id: str, ticket_id: str, slug: str) -> str`
      - `validate_worktree(worktree_path: Path, ticket_path: Path) -> bool`
      - `merge_ticket_branch(repo_root: Path, sprint_branch: str, ticket_branch: str) -> None`
      - `cleanup_worktree(repo_root: Path, worktree_path: Path, ticket_branch: str, keep_branch: bool = False) -> None`
      - `write_audit_record(sprint_dir: Path, event: dict) -> None`
      - `read_audit_record(sprint_dir: Path) -> dict`
      - `check_independence(tickets: list[dict]) -> list[list[str]]`
- [ ] Each function has a docstring stating: purpose, parameters, return value,
      and a "See: worktree-process.md §<section>" cross-reference.
- [ ] No existing module in `clasi/` imports `clasi.worktree`.
- [ ] `uv run pytest` passes (no regressions; new module is not imported by tests
      unless a smoke test is added per the optional criterion below).
- [ ] Optional: a smoke test in `tests/clasi/test_worktree_stubs.py` that imports
      the module and asserts each function raises `NotImplementedError`. Add if
      the programmer judges it valuable; note the decision either way.

## Implementation Plan

### Approach

Write `clasi/worktree.py` from scratch following the function signatures and
docstring requirements above. Cross-reference the design document produced in
ticket 002. No integration with any existing module.

### Files to create

- `clasi/worktree.py`
- `tests/clasi/test_worktree_stubs.py` (optional)

### Files to modify

None.

### Documentation updates

None beyond the module's own docstrings.

### Testing Plan

- Run `uv run pytest` to confirm no regressions.
- If the optional smoke test is written, it should pass by asserting
  `NotImplementedError` is raised on call.

## Testing

- **Existing tests to run**: `uv run pytest`
- **New tests to write**: optional smoke test (see acceptance criteria)
- **Verification command**: `uv run pytest`
