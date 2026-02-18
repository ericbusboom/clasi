---
status: draft
---

# Sprint 014 Use Cases

## SUC-001: Architect Produces Versioned Architecture Document
Parent: UC-001

- **Actor**: Architect agent
- **Preconditions**: Brief and use cases exist; instructions/architectural-quality.md exists
- **Main Flow**:
  1. Architect reads brief, use cases, and (if updating) current architecture version
  2. Architect follows 7-step process from quality guide
  3. Architect produces `docs/plans/architecture/architecture-NNN.md`
  4. Architect produces sprint `technical-plan.md` with version references
- **Postconditions**: New architecture version exists; sprint technical plan references from/to versions
- **Acceptance Criteria**:
  - [x] Architect agent definition references versioned documents
  - [x] Agent has two modes: initial architecture and sprint update

## SUC-002: Architecture Reviewer Evaluates Quality
Parent: UC-002

- **Actor**: Architecture-reviewer agent
- **Preconditions**: Proposed architecture version and sprint technical plan exist
- **Main Flow**:
  1. Reviewer reads current and proposed architecture versions
  2. Reviewer reads sprint technical plan
  3. Reviewer reads architectural quality guide
  4. Reviewer evaluates against 7 criteria (version consistency, codebase alignment, design quality, anti-patterns, risks, missing considerations, design rationale)
  5. Reviewer produces structured review with Design Quality Assessment
- **Postconditions**: Review verdict produced (APPROVE / APPROVE WITH CHANGES / REVISE)
- **Acceptance Criteria**:
  - [x] Reviewer agent references architectural-quality.md
  - [x] Review output includes Design Quality Assessment section

## SUC-003: SE Process References Architecture Versioning
Parent: UC-003

- **Actor**: All agents following the SE process
- **Preconditions**: software-engineering.md is the process reference
- **Main Flow**:
  1. Agent reads software-engineering.md for process guidance
  2. Instructions reference architecture directory and versioning workflow
  3. Sprint planning includes architecture version production
  4. Sprint technical plan template includes version fields
- **Postconditions**: All agents understand the versioned architecture workflow
- **Acceptance Criteria**:
  - [x] software-engineering.md references architecture directory
  - [x] Sprint technical plan template includes version fields
