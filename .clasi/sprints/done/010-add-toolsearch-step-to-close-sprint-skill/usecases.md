---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010 Use Cases

## SUC-001: Agent closes sprint without parameter-drop failure

- **Actor**: CLASI agent (team-lead or programmer) following the close-sprint skill
- **Preconditions**: All sprint tickets are done; the agent is about to call `close_sprint`
- **Main Flow**:
  1. Agent loads the close-sprint skill.
  2. Skill instructs agent to call `ToolSearch` with `select:mcp__clasi__close_sprint`.
  3. The tool schema is returned and the agent now has the full parameter specification.
  4. Agent calls `close_sprint(sprint_id=..., branch_name=..., ...)` with all required parameters.
  5. `close_sprint` executes successfully — merges branch, archives sprint, bumps version.
- **Postconditions**: Sprint is closed, branch merged, version tagged; no `Field required` error.
- **Acceptance Criteria**:
  - [ ] `close.md` contains a ToolSearch step immediately before the `close_sprint` call block.
  - [ ] The ToolSearch query is `select:mcp__clasi__close_sprint`.
  - [ ] The step explains why it is required (deferred-tool schema loading).
