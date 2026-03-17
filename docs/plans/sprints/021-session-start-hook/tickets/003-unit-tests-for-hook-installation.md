---
id: "003"
title: "Unit tests for hook installation"
status: todo
use-cases: [SUC-002]
depends-on: ["002"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Unit tests for hook installation

## Description

Write unit tests for the hook installation logic added to
`init_command.py` in ticket 002. These tests validate that the hook is
correctly created, that the installation is idempotent, and that the
hook content matches the expected format.

Tests to write:

1. **Hook creation** — Run init on a fresh (temp) project directory.
   Verify the hook configuration file exists in the expected location
   and contains the expected content.
2. **Idempotency** — Run init twice on the same project directory.
   Verify the hook is not duplicated: the configuration file should be
   identical after both runs (same content, no repeated entries).
3. **Correct format** — Verify the hook content matches the format
   determined in ticket 001 (e.g., correct JSON schema, correct shell
   script syntax, correct trigger type).

Use `tmp_path` (pytest fixture) for isolated test directories. Mock
external dependencies if needed to keep tests fast and deterministic.

## Acceptance Criteria

- [ ] Unit tests exist for hook creation (hook file is created with correct content)
- [ ] Unit tests exist for idempotency (running init twice produces identical result)
- [ ] Unit tests exist for correct format (hook content matches expected structure)
- [ ] All tests pass: `uv run pytest`

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — no regressions)
- **New tests to write**: Tests for `init_command.py` hook installation (described above)
- **Verification command**: `uv run pytest`
