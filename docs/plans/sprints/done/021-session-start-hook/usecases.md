---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 021 Use Cases

## SUC-001: Automatic SE Process Loading
Parent: none (new capability)

- **Actor**: Claude Code session (automated)
- **Preconditions**: Project has been initialized with `clasi init`,
  hook configuration exists
- **Main Flow**:
  1. User starts a new Claude Code session in the project
  2. Session-start hook fires before agent processes user input
  3. Hook outputs a message instructing the agent to call `get_se_overview()`
  4. Agent loads the SE process
- **Postconditions**: Agent has SE process context before any work begins
- **Acceptance Criteria**:
  - [ ] Hook fires at session start
  - [ ] Agent receives SE process loading instruction
  - [ ] Works without user intervention

## SUC-002: Hook Installation During Init
Parent: none (modification to existing flow)

- **Actor**: User running `clasi init`
- **Preconditions**: Target project exists
- **Main Flow**:
  1. User runs `clasi init <project-dir>`
  2. Init creates hook configuration alongside other artifacts
  3. Hook is ready for next Claude Code session
  4. Running init again does not duplicate the hook
- **Postconditions**: Hook configuration exists and is idempotent
- **Acceptance Criteria**:
  - [ ] `clasi init` creates hook configuration
  - [ ] Re-running init does not duplicate hook
  - [ ] Hook configuration is correct format for Claude Code
