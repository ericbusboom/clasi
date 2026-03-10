---
status: approved
---

# Sprint 016 Use Cases

## SUC-016-001: Create Sprint Copies Architecture
Parent: N/A

- **Actor**: Agent (via `create_sprint` MCP tool)
- **Preconditions**: A previous architecture document exists in
  `docs/plans/architecture/` or an archived sprint
- **Main Flow**:
  1. Agent calls `create_sprint(title)`
  2. Tool finds the most recent `architecture-NNN.md` in `docs/plans/architecture/`
  3. Tool copies it into the new sprint directory as `architecture.md`
  4. If no previous architecture exists, tool creates from template
- **Postconditions**: Sprint directory contains `architecture.md`
- **Acceptance Criteria**:
  - [ ] `create_sprint` copies previous architecture doc
  - [ ] Falls back to template when no previous exists
  - [ ] `technical-plan.md` is no longer created

## SUC-016-002: Sprint Review Validates Architecture
Parent: N/A

- **Actor**: Agent (via `review_sprint_pre_execution` MCP tool)
- **Preconditions**: Sprint exists with planning documents
- **Main Flow**:
  1. Agent calls `review_sprint_pre_execution(sprint_id)`
  2. Tool checks `architecture.md` exists, has non-draft status, has real content
  3. Tool no longer checks for `technical-plan.md`
- **Postconditions**: Review result reflects architecture.md validation
- **Acceptance Criteria**:
  - [ ] Pre-execution review checks `architecture.md`
  - [ ] Pre-close review checks `architecture.md`
  - [ ] No references to `technical-plan.md` in review tools

## SUC-016-003: Sprint Close Versions Architecture
Parent: N/A

- **Actor**: Agent (via close-sprint process)
- **Preconditions**: Sprint is complete, architecture.md exists in sprint dir
- **Main Flow**:
  1. Agent follows close-sprint skill
  2. Sprint's `architecture.md` is copied to
     `docs/plans/architecture/architecture-NNN.md`
  3. Previous versions are moved to `docs/plans/architecture/done/`
- **Postconditions**: Architecture directory has latest version at top level
- **Acceptance Criteria**:
  - [ ] Close-sprint skill includes architecture versioning steps
  - [ ] Instructions describe the `done/` convention
