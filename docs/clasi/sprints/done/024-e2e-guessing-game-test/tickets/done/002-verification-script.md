---
id: "002"
title: "Verification script (verify.py)"
status: done
use-cases: [SUC-002]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verification script (verify.py)

## Description

Create `tests/e2e/verify.py`, a standalone verification script that
takes a project directory (output of `run_e2e.py`) and validates that
both the application and the CLASI process artifacts are correct.

The script must accept a project directory path as a command-line
argument and perform these checks:

### 1. Application Functionality

- The guessing game package exists (`guessing_game/` or equivalent)
- `python -m guessing_game` starts without import errors
- The main menu displays expected options (1, 2, 3, q)
- Each game responds to input (correct guess yields success message,
  wrong guess yields retry or failure message)
- Use `subprocess` with stdin/stdout pipes to test interactively

### 2. Sprint Artifacts

- 4 sprint directories exist under `docs/clasi/sprints/done/`
- Each sprint's `sprint.md` has `status: done` in frontmatter
- Sprint topics align with the spec's sprint plan (menu, number game,
  color game, city game)

### 3. Ticket Completion

- Each sprint has a `tickets/done/` directory
- All ticket files in `tickets/done/` have `status: done` in frontmatter
- All acceptance criteria checkboxes are checked (`- [x]`)

### 4. Dispatch Logs

- `docs/clasi/log/` directory exists
- At least one log file exists per sprint
- Log files are non-empty (contain actual prompt content)

### 5. Test Suite

- Run `pytest` (or `uv run pytest`) in the project directory
- Verify it exits with code 0 (all tests pass)

### Output Format

Print a summary table:

```
=== E2E Verification Results ===
[PASS] Application starts
[PASS] Menu displays correctly
[PASS] Game 1 works
[PASS] Game 2 works
[PASS] Game 3 works
[PASS] 4 sprints completed
[PASS] All tickets done
[PASS] Dispatch logs exist
[PASS] Project tests pass

9/9 checks passed
```

Exit with code 0 if all checks pass, non-zero otherwise.

The script should be importable as a module (exposing a `verify(project_dir)`
function) and runnable as `python tests/e2e/verify.py <dir>`.

## Acceptance Criteria

- [x] `tests/e2e/verify.py` exists and accepts a project directory argument
- [x] Checks application functionality (starts, menu, each game)
- [x] Checks 4 sprint directories exist in `done/` with correct status
- [x] Checks all tickets are in `done/` directories with done status
- [x] Checks dispatch logs exist and contain content
- [x] Runs the project's test suite and checks exit code
- [x] Prints a pass/fail summary with counts
- [x] Exit code reflects overall result (0 = all pass)
- [x] Importable as a module (`verify(project_dir)` function)

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (this IS the verification infrastructure)
- **Verification command**: `python tests/e2e/verify.py <project-dir>` (requires a completed project)
