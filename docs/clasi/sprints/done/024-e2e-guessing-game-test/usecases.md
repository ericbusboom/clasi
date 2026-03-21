---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024 Use Cases

## Track 1: E2E Test Infrastructure

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
  5. Script dispatches a team-lead subagent via the Agent tool
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

## Track 2: Process Improvements

## SUC-003: Delegate to Subordinate Agent with Appropriate Boundaries
Parent: none (process improvement)

- **Actor**: Team-lead agent
- **Preconditions**: Team-lead has a task that requires delegation to a
  subordinate agent (todo-worker or sprint planner)
- **Main Flow**:
  1. Team-lead identifies a task requiring delegation (TODO creation or
     sprint planning)
  2. Team-lead formulates a dispatch containing high-level goals and
     references (raw stakeholder text for TODOs, goals and TODO paths
     for sprint planning)
  3. Team-lead dispatches to the subordinate agent without pre-formatting
     or pre-digesting the content
  4. Subordinate agent receives the raw/high-level input and applies its
     own expertise to structure the output (TODO formatting, ticket
     decomposition)
  5. Subordinate agent produces properly structured artifacts
- **Postconditions**: Subordinate agents exercise their full capabilities
  rather than acting as transcription agents. The team-lead decides WHAT
  needs to happen; subordinate agents decide HOW to structure it.
- **Acceptance Criteria**:
  - [ ] Team-lead agent definition instructs raw-text delegation to todo-worker
  - [ ] Team-lead agent definition instructs goal-oriented delegation to sprint planner
  - [ ] Todo-worker agent definition states it receives raw input and owns all formatting
  - [ ] Sprint-planner agent definition states it owns ticket decomposition and scoping
  - [ ] Delegation instructions are coherent across both boundaries

## SUC-004: Track TODO Progress Through Sprint Lifecycle
Parent: none (process improvement)

- **Actor**: Stakeholder reviewing project status
- **Preconditions**: A TODO exists in `docs/clasi/todo/` with
  `status: pending`
- **Main Flow**:
  1. Sprint planner creates a ticket that addresses the TODO, providing
     the TODO filename to `create_ticket`
  2. `create_ticket` automatically updates the TODO frontmatter: sets
     `status: in-progress`, adds `sprint` and `tickets` fields
  3. The ticket's frontmatter includes a `todo` field pointing back to
     the source TODO filename(s)
  4. Stakeholder runs `list_todos` and sees which TODOs are in-progress,
     which sprint they belong to, and which tickets address them
  5. When the sprint closes, `close_sprint` moves linked TODOs to
     `done/` with `status: done`
- **Postconditions**: Full bidirectional traceability exists between
  TODOs, sprints, and tickets throughout the lifecycle. TODOs remain
  visible in the active directory while work is in progress.
- **Acceptance Criteria**:
  - [ ] `create_ticket` with `todo` parameter updates TODO frontmatter automatically
  - [ ] Ticket frontmatter includes `todo` field with source TODO filename(s)
  - [ ] `list_todos` shows sprint/ticket linkage for in-progress TODOs
  - [ ] `close_sprint` moves linked TODOs to done
  - [ ] TODOs stay in `todo/` (not `done/`) while their sprint is active

## SUC-005: Architecture Update Without Full Rewrite
Parent: none (process improvement)

- **Actor**: Architect agent during sprint planning
- **Preconditions**: A sprint is in the architecture-review phase
- **Main Flow**:
  1. `create_sprint` generates a lightweight `architecture-update.md`
     template instead of copying the full architecture document
  2. Architect agent writes a focused update describing what changed,
     why, and the impact on existing components
  3. When the sprint closes, `close_sprint` copies the update to
     `docs/clasi/architecture/architecture-update-NNN.md`
  4. When needed, the stakeholder triggers the consolidation skill to
     merge the base architecture plus accumulated updates into a new
     consolidated architecture document
- **Postconditions**: Architecture is maintained through incremental
  updates rather than expensive full rewrites. On-demand consolidation
  produces a complete view when needed.
- **Acceptance Criteria**:
  - [ ] `create_sprint` produces architecture-update template instead of full copy
  - [ ] Architect writes focused updates, not full rewrites
  - [ ] `close_sprint` archives the update to the architecture directory
  - [ ] Consolidation skill merges base + updates into a new consolidated doc
