---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 020 Use Cases

## SUC-001: Commit at Known-Good Test State
Parent: none (modification to existing flow)

- **Actor**: Agent making commits during ticket execution
- **Preconditions**: Agent has made code changes and intends to commit
- **Main Flow**:
  1. Agent runs full test suite
  2. If tests pass, agent commits with conventional message
  3. If tests fail, agent fixes failures before committing
  4. Exception: on feature branch, agent may commit with `WIP:` prefix
     and documented failing tests
  5. During TDD: commit after green phase (before refactor), commit
     again after refactor
- **Postconditions**: Commit represents a known-good test state (or
  explicitly documented WIP)
- **Acceptance Criteria**:
  - [ ] git-workflow instruction specifies "run tests before committing"
  - [ ] git-workflow instruction specifies WIP exception for feature branches
  - [ ] tdd-cycle skill specifies commit at green phase

## SUC-002: Pre-Merge Test Verification
Parent: none (modification to existing flow)

- **Actor**: Agent closing a sprint
- **Preconditions**: All tickets done, sprint branch ready to merge
- **Main Flow**:
  1. Agent begins close-sprint process
  2. Before merging to main, agent runs full test suite on sprint branch
  3. If tests fail, agent reports failure and stops (does not merge)
  4. If tests pass, agent proceeds with merge
- **Postconditions**: Main branch always has passing tests after merge
- **Acceptance Criteria**:
  - [ ] close-sprint skill includes explicit test-pass gate before merge
  - [ ] Failure at this gate blocks the merge
