---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001 Use Cases

## SUC-001: Path-Scoped Rules Fire at Decision Points
Parent: none (new capability)

- **Actor**: Agent accessing files in a CLASI-managed directory
- **Preconditions**: Project initialized with `clasi init`, rules
  installed in `.claude/rules/`
- **Main Flow**:
  1. Agent begins to read or modify a file under `docs/clasi/`
  2. Claude Code loads `.claude/rules/clasi-artifacts.md` (path match)
  3. Agent sees the rule: "Confirm you have an active sprint or OOP"
  4. Agent checks sprint status before proceeding
  5. If no sprint and no OOP directive, agent stops and asks
- **Postconditions**: Agent has verified process state before modifying
  planning artifacts
- **Acceptance Criteria**:
  - [ ] Rules files exist in `.claude/rules/` with correct paths frontmatter
  - [ ] Rules are short (3-5 sentences) and actionable
  - [ ] Rules cover: planning artifacts, source code, TODOs, git commits
  - [ ] `clasi init` creates rules (idempotent)

## SUC-002: Directory-Scoped Subagent Dispatch
Parent: none (new capability)

- **Actor**: Controller agent dispatching a subagent for a task
- **Preconditions**: Task identified, dispatch-subagent skill loaded
- **Main Flow**:
  1. Controller determines the task scope (e.g., "create TODO files")
  2. Controller identifies the allowed directory (e.g., `docs/clasi/todo/`)
  3. Controller includes directory constraint in the subagent prompt:
     "You may only create or modify files under `docs/clasi/todo/`"
  4. Subagent executes the task within the constrained directory
  5. Controller reviews the subagent's output
  6. Controller validates: did the subagent only modify files in the
     allowed directory? If not, reject and re-dispatch with feedback.
- **Postconditions**: Subagent's changes are confined to the expected
  directory; controller has validated the scope
- **Acceptance Criteria**:
  - [ ] dispatch-subagent skill accepts a `scope_directory` parameter
  - [ ] Subagent prompt includes explicit directory constraint
  - [ ] Controller validates output file paths against scope
  - [ ] Scope violation triggers rejection + re-dispatch

## SUC-003: Rules Installed by clasi init
Parent: none (modification to existing flow)

- **Actor**: Developer running `clasi init`
- **Preconditions**: Target project exists
- **Main Flow**:
  1. Developer runs `clasi init <project-dir>`
  2. Init creates `.claude/rules/` directory
  3. Init writes rule files with correct paths frontmatter
  4. Running init again does not duplicate or overwrite customized rules
- **Postconditions**: Rules exist and are ready for Claude Code to load
- **Acceptance Criteria**:
  - [ ] `clasi init` creates `.claude/rules/` with four rule files
  - [ ] Re-running init is idempotent (same content = no change)
  - [ ] Existing custom rules in `.claude/rules/` are preserved
