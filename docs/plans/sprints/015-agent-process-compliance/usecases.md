---
status: planning
sprint: "015"
---

# Sprint 015 Use Cases

## SUC-015-001: Agent Consults Process Before Writing Code
Parent: UC-007, UC-009

- **Actor**: AI agent (any)
- **Preconditions**: Agent receives a request involving code changes.
- **Main Flow**:
  1. Agent reads AGENTS.md and encounters the mandatory `get_se_overview()`
     gate at the top of the CLASI block.
  2. Agent calls `get_se_overview()` before doing anything else.
  3. Agent encounters the bold STOP gate and either:
     a. Identifies the active sprint and ticket, then proceeds within the
        process, or
     b. Confirms the stakeholder said "out of process" and proceeds without
        a sprint.
  4. Agent does NOT start writing code without completing step 3.
- **Postconditions**: Agent is operating within the SE process (or has
  explicit OOP authorization) before any code is written.
- **Acceptance Criteria**:
  - [ ] agents-section.md contains mandatory `get_se_overview()` gate
  - [ ] agents-section.md contains STOP gate with OOP escape hatch
  - [ ] Pre-flight check rule present in agents-section.md

## SUC-015-002: Agent Uses CLASI Skill Over Generic Tool
Parent: UC-007

- **Actor**: AI agent (any)
- **Preconditions**: Agent needs to perform a process activity (create TODO,
  close branch, finish sprint).
- **Main Flow**:
  1. Agent encounters a task that maps to a process activity.
  2. Agent checks `list_skills()` to see if CLASI has a specific skill.
  3. If a CLASI skill exists, agent uses it instead of a generic tool.
- **Postconditions**: CLASI skills are used for all process activities.
- **Acceptance Criteria**:
  - [ ] CLASI-first routing rule present in agents-section.md

## SUC-015-003: Agent Reports Blocker Instead of Improvising
Parent: UC-008

- **Actor**: AI agent (any)
- **Preconditions**: A required MCP tool or process step is unavailable.
- **Main Flow**:
  1. Agent attempts to use a required tool and it fails.
  2. Agent stops and reports the failure to the stakeholder.
  3. Agent does NOT create substitute artifacts or workarounds.
- **Postconditions**: Stakeholder is aware of the blocker. No rogue artifacts.
- **Acceptance Criteria**:
  - [ ] Stop-and-report rule present in agents-section.md

## SUC-015-004: Sprint State Validated Before Execution
Parent: UC-010

- **Actor**: AI agent or MCP tool
- **Preconditions**: Sprint has tickets, about to start execution.
- **Main Flow**:
  1. Agent calls `review_sprint_pre_execution(sprint_id)`.
  2. Tool validates branch, directory, planning docs, ticket state.
  3. Returns structured JSON with `passed` and `issues[]`.
  4. Agent fixes issues and re-runs until `passed: true`.
- **Postconditions**: Sprint is in valid state before execution.
- **Acceptance Criteria**:
  - [ ] `review_sprint_pre_execution` MCP tool exists
  - [ ] Returns structured JSON with actionable fix instructions
  - [ ] Validates planning doc status, ticket existence, branch

## SUC-015-005: Sprint State Validated Before Close
Parent: UC-013

- **Actor**: AI agent or MCP tool
- **Preconditions**: All tickets implemented, sprint ready to close.
- **Main Flow**:
  1. Agent calls `review_sprint_pre_close(sprint_id)`.
  2. Tool validates all tickets done, planning docs correct, no placeholders.
  3. Returns structured JSON with `passed` and `issues[]`.
  4. Agent fixes issues and re-runs until `passed: true`.
- **Postconditions**: Sprint is in valid state before closure.
- **Acceptance Criteria**:
  - [ ] `review_sprint_pre_close` MCP tool exists
  - [ ] Returns structured JSON with actionable fix instructions
  - [ ] Validates ticket completion, doc status, no template placeholders

## SUC-015-006: Quick Fix Via /oop
Parent: UC-007

- **Actor**: Stakeholder + AI agent
- **Preconditions**: A small change is needed (typo, config tweak, one-liner).
- **Main Flow**:
  1. Stakeholder invokes `/oop` or says "out of process."
  2. Agent skips SE ceremony — no sprint, tickets, or gates.
  3. Agent reads code, makes the change, runs tests, commits to master.
- **Postconditions**: Change is made quickly without process overhead.
- **Acceptance Criteria**:
  - [ ] `/oop` skill definition exists
  - [ ] Skill instructs agent to skip all SE ceremony
  - [ ] Skill instructs agent to run tests before committing

## SUC-015-007: Stakeholder Uses Narrative Mode in Project Initiation
Parent: UC-009

- **Actor**: Stakeholder
- **Preconditions**: Project initiation interview is in progress.
- **Main Flow**:
  1. Agent presents interview options including "Start an open narrative."
  2. Stakeholder speaks freely about their project.
  3. Agent synthesizes narrative into structured documents.
  4. Agent follows up with clarifying questions.
- **Postconditions**: Project overview documents produced from free-form input.
- **Acceptance Criteria**:
  - [ ] `project-initiation` skill offers narrative mode option
  - [ ] Agent synthesizes narrative into structured output
