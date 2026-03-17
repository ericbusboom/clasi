---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 018 Use Cases

## SUC-001: Import GitHub Issues as TODOs
Parent: none (new capability)

- **Actor**: Agent (on behalf of stakeholder)
- **Preconditions**:
  - `gh` CLI is installed and authenticated
  - User has access to the target repository
- **Main Flow**:
  1. User asks agent to import issues from a GitHub repo (or the current repo)
  2. Agent verifies `gh` CLI access to the repo using `gh issue list --limit 1`
  3. If access fails, agent reports the error and tells the user how to fix it
     (e.g., `gh auth login`, `gh auth status`)
  4. Agent fetches open issues via `list_github_issues` MCP tool
  5. If >5 issues are returned, agent pauses and presents the list to the user,
     asking them to confirm import-all, select specific issues, or filter by label
  6. For each selected issue, agent creates a TODO file in `docs/plans/todo/`
     with `github-issue: owner/repo#N` in the frontmatter
  7. Agent confirms what was imported
- **Postconditions**: TODO files exist with `github-issue` references
- **Acceptance Criteria**:
  - [ ] `gh` access is verified before listing issues
  - [ ] Access failure produces a helpful error message
  - [ ] >5 issues triggers a confirmation gate
  - [ ] TODOs include `github-issue` field in frontmatter
  - [ ] Issue title becomes TODO heading, issue body becomes description

## SUC-002: Carry Issue Reference Through Lifecycle
Parent: none (new capability)

- **Actor**: Agent executing the SE process
- **Preconditions**:
  - A TODO exists with a `github-issue` frontmatter field
  - A sprint is being planned that incorporates this TODO
- **Main Flow**:
  1. During sprint planning, agent selects a TODO with a `github-issue` field
  2. When creating a ticket from this TODO, the `github-issue` field is copied
     to the ticket's frontmatter
  3. When writing the sprint doc, agent collects all `github-issue` references
     from the sprint's tickets and lists them in a `## GitHub Issues` section
- **Postconditions**: Sprint doc contains a complete list of linked GitHub issues
- **Acceptance Criteria**:
  - [ ] Ticket frontmatter includes `github-issue` when created from a linked TODO
  - [ ] Sprint doc's `## GitHub Issues` section lists all linked issues
  - [ ] References use the `owner/repo#N` format consistently

## SUC-003: Close Linked Issues on Sprint Close
Parent: none (new capability)

- **Actor**: Agent closing a sprint
- **Preconditions**:
  - Sprint has tickets with `github-issue` references
  - Sprint doc has a `## GitHub Issues` section
  - `gh` CLI is authenticated
- **Main Flow**:
  1. Agent begins the close-sprint process
  2. Before merging, agent reads the sprint doc's `## GitHub Issues` section
  3. For each listed issue, agent calls `close_github_issue` MCP tool
  4. If closing fails for any issue, agent reports the failure but continues
     closing other issues and the sprint itself
  5. Agent includes the closed issues in the sprint completion summary
- **Postconditions**: All linked GitHub issues are closed (best-effort)
- **Acceptance Criteria**:
  - [ ] Close-sprint reads GitHub issues from sprint doc
  - [ ] Each linked issue is closed via `gh issue close`
  - [ ] Failures are reported but don't block sprint closure
  - [ ] Sprint completion summary lists which issues were closed
