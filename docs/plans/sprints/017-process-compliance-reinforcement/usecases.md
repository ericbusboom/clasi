---
status: draft
---

# Sprint 017 Use Cases

## SUC-017-001: Init writes CLASI block into CLAUDE.md
Parent: UC-003 (Project Initialization)

- **Actor**: Developer running `clasi init`
- **Preconditions**: Target directory exists; may or may not have CLAUDE.md
- **Main Flow**:
  1. Developer runs `clasi init <target>`
  2. If CLAUDE.md does not exist, create it with the full CLASI block
  3. If CLAUDE.md exists and has CLASI markers, replace the section
  4. If CLAUDE.md exists without markers, append the CLASI block
  5. Do not create or modify AGENTS.md
- **Postconditions**: CLAUDE.md contains the CLASI block inline; no
  AGENTS.md changes
- **Acceptance Criteria**:
  - [ ] Fresh init creates CLAUDE.md with CLASI block (no @AGENTS.md)
  - [ ] Re-init updates existing CLASI section in CLAUDE.md
  - [ ] AGENTS.md is not created or modified by init

## SUC-017-002: Document templates include process reminder
Parent: UC-001 (Sprint Management)

- **Actor**: Agent reading a sprint document, ticket, or architecture doc
- **Preconditions**: Document was created from a CLASI template
- **Main Flow**:
  1. Agent opens a planning document during sprint work
  2. Agent encounters the process reminder line
  3. Agent is prompted to consult the SE process before making changes
- **Postconditions**: Agent has been reminded to follow the SE process
- **Acceptance Criteria**:
  - [ ] sprint.md template contains the reminder
  - [ ] sprint-architecture.md template contains the reminder
  - [ ] ticket.md template contains the reminder
  - [ ] sprint-usecases.md template contains the reminder
