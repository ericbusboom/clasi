# E2E Tests

End-to-end tests that validate the full CLASI software engineering
process by having it build a real application from a spec.

## Purpose

These tests verify that the entire CLASI SE lifecycle works correctly:
project initiation, sprint planning, ticket execution, sprint closing,
and version tagging. A team-lead subagent is dispatched to implement a
guessing-game CLI application across 4 sprints, and a verification
script checks that all artifacts and the application itself are correct.

## Prerequisites

- Python 3.10+
- CLASI package installed (`pip install -e .` or `uv pip install -e .`)
- Claude Code CLI installed and configured (`claude`)
- Sufficient API credits (dispatches multiple subagents across 4 sprints)

## Files

| File | Description |
|------|-------------|
| `guessing-game-spec.md` | Application spec used as test input. Describes a CLI with 3 guessing games and a 4-sprint implementation plan. |
| `run_e2e.py` | Test harness. Creates a temp project, runs `clasi init`, copies the spec, initializes git, and dispatches a team-lead subagent. |
| `verify.py` | Verification script. Takes a completed project directory and checks application functionality, sprint artifacts, ticket completion, dispatch logs, and the project's own test suite. |

## How to Run

1. **Run the harness** to build the project:

   ```bash
   python tests/e2e/run_e2e.py
   ```

   This creates a temporary directory, initializes CLASI, and dispatches
   a team-lead subagent. The process takes significant time (dispatches
   multiple subagents across 4 sprints). When complete, it prints the
   temp directory path.

2. **Note the temp directory** printed at the end, e.g.:
   ```
   Project directory: /tmp/clasi-e2e-abc123
   ```

3. **Verify the results**:

   ```bash
   python tests/e2e/verify.py /tmp/clasi-e2e-abc123
   ```

   This checks that the application works, all 4 sprints completed, all
   tickets are done, dispatch logs exist, and the project's tests pass.

## Adding New E2E Tests

To add a new E2E scenario:

1. **Create a spec file** in this directory (e.g., `my-app-spec.md`).
   Include a sprint plan describing how the implementation should be
   broken up.

2. **Update `run_e2e.py`** or create a new harness script that copies
   your spec and dispatches a subagent with appropriate instructions.

3. **Update `verify.py`** or create a new verification script with
   checks specific to your spec (application behavior, expected sprint
   count, etc.).

4. Keep verification checks independent of each other where possible,
   so partial failures are clearly reported.

## Cost and Timing

E2E tests dispatch real Claude subagents and consume API tokens. A full
run (4 sprints with planning, execution, and closing) can take 30-60
minutes and use significant API credits. These tests are not intended
for CI on every commit. Run them manually when validating process
changes or before major releases.
