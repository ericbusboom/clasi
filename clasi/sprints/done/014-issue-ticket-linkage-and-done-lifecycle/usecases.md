---
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 014 Use Cases

## SUC-001: Issue auto-linked to ticket via sprint.md issues field

- **Actor**: Sprint-planner agent (via `create_ticket` MCP tool)
- **Preconditions**: Sprint has `issues:` list in its `sprint.md` frontmatter (populated by `link_sprint_issues`); no explicit `issue=` parameter is passed to `create_ticket`.
- **Main Flow**:
  1. Sprint-planner calls `create_ticket(sprint_id, title)` without an `issue=` argument.
  2. `create_ticket` reads the sprint's `issues:` frontmatter field.
  3. The issue filename(s) found are used to auto-link the ticket.
  4. Each referenced issue file is moved to `<sprint>/issues/` with `status: in-progress`.
- **Postconditions**: Ticket frontmatter contains `issue:` back-reference; issue file is in `<sprint>/issues/` with `status: in-progress`.
- **Acceptance Criteria**:
  - [ ] `create_ticket` reads `issues:` field when `issue=None` (not `todos:`).
  - [ ] Falls back to `todos:` for legacy sprints that predate `link_sprint_issues`.
  - [ ] Issue file is physically moved and its frontmatter updated.

## SUC-002: Sprint closes successfully with unresolved issues present

- **Actor**: Team-lead agent (via `close_sprint` MCP tool)
- **Preconditions**: Sprint is in a closeable state; at least one linked issue remains `in-progress` (was not completed during the sprint).
- **Main Flow**:
  1. Team-lead calls `close_sprint(sprint_id)`.
  2. `_close_sprint_full` sweeps issues: resolved ones are moved to `done/`.
  3. Unresolved issues are collected but do NOT block the close.
  4. Sprint closes successfully; result includes `unresolved_issues` list.
- **Postconditions**: Sprint is closed; `unresolved_issues` are listed in the result for mop-up by the team-lead; no error is returned.
- **Acceptance Criteria**:
  - [ ] `_close_sprint_full` does not return an error when unresolved issues are present.
  - [ ] Result JSON includes `unresolved_issues` key with filenames.
  - [ ] Behavior matches `_close_sprint_legacy` path for unresolved issues.

## SUC-003: Agent instructions guide linkage at every lifecycle step

- **Actor**: Agents using CLASI skills (sprint-roadmap, plan-sprint, create-tickets, team-lead, close-sprint)
- **Preconditions**: Agent is following the documented skill/agent instructions.
- **Main Flow**:
  1. During roadmap creation, agent calls `link_sprint_issues` to associate claimed issues with the sprint.
  2. During detail planning, agent calls `link_sprint_issues` explicitly (not manual frontmatter writes).
  3. During ticket creation, agent passes `issue=` to `create_ticket` and uses `add_issue_ref` for multi-ticket issues.
  4. Team-lead confirms resolved issues landed in `<sprint>/issues/done/` after close and addresses `unresolved_issues`.
  5. Close-sprint skill documents the auto-sweep behavior and non-blocking unresolved report.
- **Postconditions**: Issues are bidirectionally linked in sprint frontmatter and ticket frontmatter; resolved issues are swept at close.
- **Acceptance Criteria**:
  - [ ] `sprint-roadmap` SKILL.md instructs calling `link_sprint_issues`.
  - [ ] `plan-sprint` SKILL.md instructs calling `link_sprint_issues` (not manual writes).
  - [ ] `create-tickets` SKILL.md reinforces `issue:` back-refs on every ticket.
  - [ ] `team-lead/agent.md` includes issue lifecycle responsibility section.
  - [ ] `close-sprint` SKILL.md documents auto-sweep and non-blocking unresolved report.
