---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 007 Use Cases

## SUC-001: MCP server fails fast on import error
Parent: (project-level server reliability)

- **Actor**: MCP server process / operator
- **Preconditions**: CLASI is installed in a venv that predates the
  sprint/todo/artifact submodule split; the server process starts.
- **Main Flow**:
  1. Server `run()` attempts to import `artifact_tools` (which now does
     eager top-level imports of `clasi.sprint`, `clasi.todo`, etc.).
  2. Import fails immediately at startup.
  3. Preflight check in `run()` catches the error and prints a clear banner
     to stderr before registering any tools.
  4. Server exits with a non-zero code.
- **Postconditions**: The operator sees a clear error identifying the missing
  module; no tools are silently broken.
- **Acceptance Criteria**:
  - [ ] `list_sprints` does not fail silently mid-session due to stale imports.
  - [ ] `get_version` returns `metadata_version` and `source_path` fields.
  - [ ] Preflight abort message names the failing module.

## SUC-002: Close sprint on a non-Python project
Parent: (project-level close-sprint reliability)

- **Actor**: Developer closing a sprint in a JavaScript or Java project
- **Preconditions**: All tickets are done; `close_sprint` is called with
  `test_command=""` or `test_command="npm test"`.
- **Main Flow**:
  1. Caller passes `test_command=""` (skip tests) or `test_command="npm test"`.
  2. `_close_sprint_full` uses the provided command; `uv run pytest` is not
     invoked.
  3. Sprint archive, version bump, and git operations complete normally.
- **Postconditions**: Sprint is closed without spurious pytest failures.
- **Acceptance Criteria**:
  - [ ] `test_command=""` causes the tests step to be skipped.
  - [ ] `test_command="npm test"` causes `npm test` to run instead of pytest.
  - [ ] `test_command=None` (default) still runs `uv run pytest`.
  - [ ] close-sprint skill docs document the parameter.

## SUC-003: clasi init produces language-neutral rules
Parent: (project-level init reliability)

- **Actor**: Developer running `clasi init` on a non-Python project
- **Preconditions**: Project has no `pyproject.toml`; developer runs `clasi init`.
- **Main Flow**:
  1. `clasi init` writes `source-code.md` and `git-commits.md` rules to
     `.claude/rules/`.
  2. Neither file mentions `uv run pytest`.
  3. `clasi init` creates `docs/clasi/log/.gitignore` suppressing `*.log`.
- **Postconditions**: Rules are usable by any project type; logs don't surface
  in `git status`.
- **Acceptance Criteria**:
  - [ ] `source-code.md` rule contains no `uv run pytest` reference.
  - [ ] `git-commits.md` rule contains no `uv run pytest` reference.
  - [ ] `docs/clasi/log/.gitignore` is created with content suppressing logs.
