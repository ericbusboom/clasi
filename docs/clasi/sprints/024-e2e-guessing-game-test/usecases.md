---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024 Use Cases

## SUC-001: Run E2E Test
Parent: none (new capability)

- **Actor**: Developer or CI system
- **Preconditions**: CLASI is installed (`pip install -e .` or equivalent),
  Claude Code CLI is available, MCP server can be started
- **Main Flow**:
  1. Developer invokes `run_e2e.py`
  2. Script creates a temporary project directory
  3. Script runs `clasi init` to install the SE process into the temp project
  4. Script copies `guessing-game-spec.md` into the temp project
  5. Script dispatches a main-controller subagent via the Agent tool
  6. The subagent receives the spec and instructions to implement it
     across 4 sprints (menu, number game, color game, city game)
  7. The subagent executes the full CLASI SE process: planning, ticketing,
     executing, and closing each sprint
  8. Script captures the subagent result and reports success or failure
  9. Script prints the temp project path for subsequent verification
- **Postconditions**: A temporary project directory exists containing a
  fully implemented guessing game built through the CLASI SE process,
  with all sprint artifacts (sprint docs, tickets, architecture, logs)
- **Acceptance Criteria**:
  - [ ] Temp directory is created and isolated from the main repo
  - [ ] `clasi init` runs successfully in the temp directory
  - [ ] Guessing game spec is copied into the temp project
  - [ ] Main-controller subagent is dispatched with correct context
  - [ ] Script reports success/failure and the temp project path

## SUC-002: Verify Completed Project
Parent: none (new capability)

- **Actor**: Developer or CI system (post-SUC-001)
- **Preconditions**: A project directory exists that was built through
  the CLASI SE process (output of SUC-001 or equivalent)
- **Main Flow**:
  1. Developer invokes `verify.py <project-dir>`
  2. Script checks that the guessing game application works:
     - `python -m guessing_game` starts without error
     - Menu displays expected options
     - Each game responds correctly to input
  3. Script checks CLASI process artifacts:
     - 4 sprint directories exist in `docs/clasi/sprints/done/`
     - Each sprint has `sprint.md` with `status: done`
     - All tickets are in `tickets/done/` subdirectories
     - Ticket frontmatter shows `status: done`
  4. Script checks dispatch logs:
     - `docs/clasi/log/` directory exists
     - Log files contain non-empty content
  5. Script runs the project's test suite (`pytest`) and checks it passes
  6. Script prints a summary of all checks (pass/fail per check)
- **Postconditions**: All verification checks pass, confirming the CLASI
  SE process produced a correct, tested application with complete artifacts
- **Acceptance Criteria**:
  - [ ] Game functionality is verified (starts, menus work, games respond)
  - [ ] 4 completed sprints are found with correct status
  - [ ] All tickets are in done directories with done status
  - [ ] Dispatch logs exist and contain content
  - [ ] Project test suite passes
  - [ ] Summary report shows pass/fail per check
