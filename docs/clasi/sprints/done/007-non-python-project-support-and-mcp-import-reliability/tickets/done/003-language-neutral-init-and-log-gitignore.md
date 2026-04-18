---
id: '003'
title: Language-neutral init and log .gitignore
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
todo: hardcoded-pytest-blocks-non-python-projects.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Language-neutral init and log .gitignore

## Description

Rules installed by `clasi init` embed `uv run pytest` references in
`source-code.md` (step 3: "Run tests after changes") and `git-commits.md`
(step 1: "All tests pass (`uv run pytest`)"). These strings teach the AI
incorrect behavior for non-Python projects.

Additionally, `clasi init` does not create a `.gitignore` in the log directory,
causing `mcp-server.log` and similar files to surface in `git status` for every
project type.

This ticket removes the `uv run pytest` references from the `RULES` dict in
`init_command.py` and adds log `.gitignore` creation to `run_init`.

## Acceptance Criteria

- [ ] `RULES["source-code.md"]` in `init_command.py` contains no reference
  to `uv run pytest`. The test step is replaced with a language-neutral
  instruction (e.g., "Run the project's test suite").
- [ ] `RULES["git-commits.md"]` in `init_command.py` contains no reference
  to `uv run pytest`. The tests-pass step is replaced with a language-neutral
  instruction.
- [ ] `run_init` creates `<project_root>/docs/clasi/log/` (with
  `mkdir(parents=True, exist_ok=True)`) and writes a `.gitignore` file
  containing at minimum `*.log` to suppress log files.
- [ ] The `.gitignore` creation is idempotent (safe to re-run `clasi init`).
- [ ] All existing tests continue to pass.
- [ ] New unit tests verify rule content and `.gitignore` creation.

## Implementation Plan

### Approach

1. Read `init_command.py` lines 40–111 (the `RULES` dict) and lines 333+
   (`run_init`).
2. In `RULES["source-code.md"]`, replace the step
   `3. Run tests after changes: \`uv run pytest\`.` with
   `3. Run the project's test suite to verify changes.`
3. In `RULES["git-commits.md"]`, replace
   `1. All tests pass (\`uv run pytest\`).` with
   `1. All tests pass (run the project's test suite).`
4. In `run_init`, after the existing log directory setup (or in the init
   sequence), add code to write `docs/clasi/log/.gitignore` with content:
   ```
   # Suppress MCP server and hook logs
   *.log
   ```
5. Update the init output (click.echo) to report the `.gitignore` as created
   or unchanged (idempotent).

### Files to modify

- `clasi/init_command.py` — update `RULES` dict; add `.gitignore` creation in
  `run_init`

### Files to create

None (the `.gitignore` is created at runtime by `clasi init`, not in source).

## Testing

- **Existing tests to run**: `uv run pytest tests/` — verify no regressions.
- **New tests to write** (in `tests/unit/test_init_command.py` or equivalent):
  - `test_source_code_rule_no_pytest`: assert `RULES["source-code.md"]` does
    not contain `uv run pytest`.
  - `test_git_commits_rule_no_pytest`: assert `RULES["git-commits.md"]` does
    not contain `uv run pytest`.
  - `test_init_creates_log_gitignore`: run `run_init` against a temp directory;
    assert `docs/clasi/log/.gitignore` exists and contains `*.log`.
  - `test_init_log_gitignore_idempotent`: run `run_init` twice; assert no error
    and `.gitignore` still exists with correct content.
- **Verification command**: `uv run pytest`
