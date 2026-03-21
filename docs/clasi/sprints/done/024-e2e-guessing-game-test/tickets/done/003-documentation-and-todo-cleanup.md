---
id: "003"
title: "Documentation and TODO cleanup"
status: done
use-cases: [SUC-001, SUC-002]
depends-on: ["001", "002"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Documentation and TODO cleanup

## Description

Create documentation for the `tests/e2e/` directory and clean up the
originating TODO item.

### 1. README.md for tests/e2e/

Create `tests/e2e/README.md` covering:

- **Purpose**: What the e2e tests validate (full CLASI SE process)
- **Prerequisites**: What must be installed (CLASI package, Claude Code
  CLI, Python 3.10+)
- **Files**: Description of each file in the directory
  - `guessing-game-spec.md` -- the application spec used as test input
  - `run_e2e.py` -- test harness that builds the project
  - `verify.py` -- verification script that checks results
- **How to run**: Step-by-step instructions
  1. Run the harness: `python tests/e2e/run_e2e.py`
  2. Note the temp directory path printed
  3. Verify: `python tests/e2e/verify.py <temp-dir>`
- **Adding new e2e tests**: Guidelines for creating additional specs
  and verification checks
- **Cost and timing**: Note that e2e tests dispatch real subagents and
  are expensive (time and API tokens); not intended for CI on every
  commit

### 2. TODO Cleanup

Create `docs/clasi/todo/e2e-guessing-game-test.md` with the standard
TODO frontmatter (status: done, sprint: "024") and move it to
`docs/clasi/todo/done/` to record that this TODO has been addressed.

## Acceptance Criteria

- [x] `tests/e2e/README.md` exists with purpose, prerequisites, file descriptions, usage instructions
- [x] README explains how to add new e2e tests
- [x] README notes cost/timing considerations
- [x] TODO file `docs/clasi/todo/done/e2e-guessing-game-test.md` exists with done status
- [x] TODO frontmatter references sprint 024

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (documentation-only ticket)
- **Verification command**: Review README content manually
