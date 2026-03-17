---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 019 Use Cases

## SUC-001: TDD During Ticket Implementation
Parent: none (new capability)

- **Actor**: Agent executing a ticket
- **Preconditions**: Ticket is in-progress, implementation phase
- **Main Flow**:
  1. Agent reads ticket acceptance criteria
  2. Agent writes a failing test that captures the first criterion
  3. Agent runs test, confirms failure, records failure message
  4. Agent writes minimal production code to pass the test
  5. Agent runs test, confirms pass
  6. Agent refactors if needed, keeping tests green
  7. Repeats for remaining criteria
- **Postconditions**: All acceptance criteria have corresponding tests,
  all tests pass, code is refactored
- **Acceptance Criteria**:
  - [ ] TDD cycle skill defines red-green-refactor as an available workflow
  - [ ] Skill requires recording the failure message before writing code
  - [ ] Skill includes guidance for when tests pass unexpectedly

## SUC-002: Structured Debugging When Tests Fail
Parent: none (new capability)

- **Actor**: Agent encountering test failures during implementation
- **Preconditions**: A test that should pass is failing, or a previously
  passing test has broken
- **Main Flow**:
  1. Agent recognizes debugging trigger (test failure, broken acceptance
     criteria, two consecutive failed fix attempts)
  2. Agent invokes systematic debugging skill
  3. Phase 1: Collect evidence (error messages, stack traces, recent changes)
  4. Phase 2: Analyze patterns (working vs broken state, what changed)
  5. Phase 3: Form hypothesis, design confirming test, run test
  6. Phase 4: Fix root cause, verify fix, verify no regressions
  7. If three attempts fail, escalate to stakeholder
- **Postconditions**: Root cause identified and fixed, or escalation
  documented
- **Acceptance Criteria**:
  - [ ] Debugging skill defines four phases
  - [ ] Three-attempt cap enforced with escalation
  - [ ] Agent must document evidence and hypotheses

## SUC-003: Execute-Ticket Integration
Parent: none (modification to existing flow)

- **Actor**: Agent executing a ticket via execute-ticket skill
- **Preconditions**: Ticket selected for implementation
- **Main Flow**:
  1. Agent begins implementation phase of execute-ticket
  2. execute-ticket references tdd-cycle skill as an available option
  3. If tests fail or implementation hits problems, execute-ticket
     references systematic-debugging skill
  4. Agent follows referenced skill workflow
- **Postconditions**: Ticket implementation can optionally use TDD,
  debugging follows structured protocol
- **Acceptance Criteria**:
  - [ ] execute-ticket implementation step references tdd-cycle as option
  - [ ] execute-ticket includes debugging trigger conditions
  - [ ] testing instruction references TDD as available method
