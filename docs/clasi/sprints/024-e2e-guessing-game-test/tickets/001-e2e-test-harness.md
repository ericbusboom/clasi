---
id: "001"
title: "E2E test harness (run_e2e.py)"
status: open
use-cases: [SUC-001]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E test harness (run_e2e.py)

## Description

Create `tests/e2e/run_e2e.py`, the end-to-end test harness that
validates the full CLASI SE process by having it build a real
application from a spec.

The script must:

1. **Create a temporary project directory** using Python's `tempfile`
   module. The directory should persist after the script exits so
   `verify.py` can inspect it.

2. **Initialize CLASI** by running `clasi init` in the temp directory.
   This installs `CLAUDE.md`, `.claude/` rules, `.mcp.json`, and all
   other init artifacts.

3. **Copy the spec** from `tests/e2e/guessing-game-spec.md` into the
   temp project (e.g., as `spec.md` or `guessing-game-spec.md` at the
   project root).

4. **Initialize git** in the temp directory (`git init`, initial
   commit) so the CLASI process can create branches and tags.

5. **Dispatch a main-controller subagent** via the Claude Code Agent
   tool. The subagent prompt must:
   - Reference the spec file
   - Instruct the agent to implement the spec following the CLASI SE
     process across 4 sprints (as defined in the spec's Sprint Plan)
   - Set the scope to the temp project directory

6. **Report results** -- print the temp directory path and whether
   the dispatch succeeded or failed.

The script should be runnable as `python tests/e2e/run_e2e.py` or
imported as a module. It should handle errors gracefully (e.g., if
`clasi init` fails, report and exit rather than proceeding).

Reference: `tests/e2e/guessing-game-spec.md` for the spec content.

## Acceptance Criteria

- [ ] `tests/e2e/run_e2e.py` exists and is executable
- [ ] Creates a temporary directory that persists after script exit
- [ ] Runs `clasi init` successfully in the temp directory
- [ ] Copies `guessing-game-spec.md` into the temp project
- [ ] Initializes a git repo with an initial commit
- [ ] Dispatches a main-controller subagent with the spec and 4-sprint instruction
- [ ] Prints the temp directory path for subsequent verification
- [ ] Handles errors gracefully with clear messages

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (this IS the test infrastructure)
- **Verification command**: `python tests/e2e/run_e2e.py` (manual, expensive)
