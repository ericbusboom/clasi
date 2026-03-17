---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 022 Use Cases

## SUC-001: Dispatch Subagent for Implementation
Parent: none (new capability)

- **Actor**: Controller agent (project-manager or execute-ticket)
- **Preconditions**: Ticket is in-progress, implementation plan exists
- **Main Flow**:
  1. Controller reads ticket plan, identifies files to modify/create
  2. Controller curates context: relevant source files, ticket
     description, acceptance criteria, applicable architecture decisions,
     coding standards, testing instructions
  3. Controller composes subagent prompt with curated context
  4. Controller dispatches subagent via Agent tool
  5. Subagent implements code in isolated context
  6. Controller receives subagent result
  7. Controller reviews result (triggers two-stage review)
  8. If issues found, controller dispatches again with feedback
- **Postconditions**: Implementation completed by isolated subagent
- **Acceptance Criteria**:
  - [ ] Dispatch skill defines context curation rules
  - [ ] Subagent receives only relevant context
  - [ ] Controller never writes code directly
  - [ ] Iteration loop with feedback defined

## SUC-002: Two-Stage Code Review
Parent: none (new capability)

- **Actor**: Code-reviewer agent
- **Preconditions**: Implementation subagent has completed, changes exist
- **Main Flow**:
  1. Code-reviewer receives implementation output
  2. Phase 1 — Correctness: Review against ticket acceptance criteria
     and sprint architecture. Binary pass/fail for each criterion.
  3. If Phase 1 fails: return specific failures, skip Phase 2
  4. Phase 2 — Quality: Review against coding standards, architectural
     quality, project conventions. Rank issues by severity.
  5. Produce review checklist artifact
- **Postconditions**: Structured review with correctness and quality
  separated
- **Acceptance Criteria**:
  - [ ] Phase 1 checks every acceptance criterion
  - [ ] Phase 1 failure short-circuits Phase 2
  - [ ] Phase 2 issues ranked by severity
  - [ ] Review checklist artifact produced

## SUC-003: Context Curation Protocol
Parent: none (new instruction)

- **Actor**: Any agent dispatching a subagent
- **Preconditions**: Task identified for subagent delegation
- **Main Flow**:
  1. Agent identifies task scope and required context
  2. Agent applies include rules: source files, ticket, criteria,
     architecture, coding standards
  3. Agent applies exclude rules: conversation history, other tickets,
     debug logs, full file listings
  4. Agent composes prompt with curated context
- **Postconditions**: Subagent receives minimal, relevant context
- **Acceptance Criteria**:
  - [ ] Include/exclude rules documented in instruction
  - [ ] Examples provided for common scenarios
  - [ ] Instruction referenced by dispatch skill
