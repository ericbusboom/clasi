---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 002 Use Cases

## SUC-001: Add issue reference to a ticket post-creation

- **Actor**: Sprint-planner agent
- **Preconditions**: A ticket exists in `tickets/`; the target issue file exists in `.clasi/issues/` or `<sprint>/issues/`.
- **Main Flow**:
  1. Planner calls `add_issue_ref(ticket_path, issue_filename)`.
  2. Tool appends `issue_filename` to the ticket's `issue:` frontmatter (converts string → list if needed).
  3. Tool appends the ticket ID to the issue's `tickets:` frontmatter via `Issue.add_ticket_ref`.
  4. Tool returns the updated frontmatter of both files.
- **Postconditions**: The ticket's `issue:` field contains `issue_filename`; the issue's `tickets:` field contains the ticket ID. Both are idempotent on repeat calls.
- **Acceptance Criteria**:
  - [ ] Calling `add_issue_ref` on a ticket with `issue: ""` sets `issue: <filename>`.
  - [ ] Calling `add_issue_ref` on a ticket that already has one issue ref converts to a list `[existing, new]`.
  - [ ] Calling `add_issue_ref` twice with the same pair is a no-op (no duplicates).
  - [ ] The issue's `tickets:` frontmatter gains the ticket ID.
  - [ ] End-state matches `create_ticket(todo=filename)` for a single-issue ticket.

## SUC-002: All sprint tickets for an issue carry the issue back-reference

- **Actor**: Sprint-planner agent
- **Preconditions**: A sprint has multiple tickets that together implement one source issue.
- **Main Flow**:
  1. Planner creates ticket 001 via `create_ticket(sprint_id, title, todo=issue_filename)`.
  2. Planner creates tickets 002–N via `create_ticket(sprint_id, title)`, then calls `add_issue_ref(ticket_path, issue_filename)` for each.
  3. `create-tickets` skill guidance requires this step for any ticket that does work toward an issue.
- **Postconditions**: Every ticket working toward the issue has `issue: <filename>` in frontmatter; the issue's `tickets:` list contains all ticket IDs.
- **Acceptance Criteria**:
  - [ ] After planning, `ticket.issue_ref` is non-None for all tickets implementing the issue.
  - [ ] The issue's `tickets:` frontmatter lists all ticket IDs (no gaps).
  - [ ] `create-tickets` skill SKILL.md files explicitly require `add_issue_ref` for multi-ticket issues.

## SUC-003: Issue auto-completes when its last ticket is done, regardless of which ticket is moved

- **Actor**: Programmer agent calling `move_ticket_to_done`
- **Preconditions**: A sprint has tickets T1–T4 all implementing issue I. T1 has `issue: I` in frontmatter; T2–T4 do not (legacy state or missed propagation).
- **Main Flow**:
  1. Programmer moves T1 to done. T2–T4 still open → no completion.
  2. Programmer moves T2, T3 to done. Each move runs the sweep; issue is still open (T4 pending).
  3. Programmer moves T4 to done. Sweep finds all of I's `tickets:` are done → issue moves to `issues/done/`.
- **Postconditions**: Issue is in `<sprint>/issues/done/` with `status: done`, regardless of whether T4 had an `issue:` frontmatter ref.
- **Acceptance Criteria**:
  - [ ] After the last ticket completing an issue is moved to done, the issue is physically relocated to `issues/done/`.
  - [ ] The sweep fires on every `move_ticket_to_done` call, not only when the moved ticket has `issue:` ref.
  - [ ] `completes_issue: false` on any sprint ticket still suppresses auto-completion.
  - [ ] Idempotent: if the issue is already in `done/`, no error.
  - [ ] Simulate sprint 001 scenario: T1 has ref, T2–T4 don't; after last move, issue is done.

## SUC-004: Shared sweep helper used by both move-to-done and close-sprint

- **Actor**: System (internal)
- **Preconditions**: `move_ticket_to_done` and `_close_sprint_full` both need to sweep in-progress sprint issues and auto-complete done ones.
- **Main Flow**:
  1. Both callers call `_sweep_done_issues(sprint)`.
  2. Helper scans all in-progress issues associated with `sprint` (sprint-scoped `issues/` and pending-pool issues with matching `sprint:` field).
  3. For each, checks if all `tickets:` entries are done; if so, calls `issue.move_to_done()`.
  4. Returns list of completed issue filenames.
- **Postconditions**: In-progress issues whose tickets are all done are moved to `issues/done/`. Deferred issues (any ticket with `completes_issue: false`) are left in place.
- **Acceptance Criteria**:
  - [ ] `_sweep_done_issues` is a module-level helper in `artifact_tools.py`.
  - [ ] `move_ticket_to_done` calls `_sweep_done_issues` (replaces the current guarded block).
  - [ ] `_close_sprint_full` reuses `_sweep_done_issues` (or an equivalent extracted path).
  - [ ] Both callers return the list of completed issues in their JSON output.

## SUC-005: Sprint roadmap phase establishes bidirectional sprint↔issue links automatically

- **Actor**: Sprint-planner agent calling `create_sprint` or `insert_sprint`
- **Preconditions**: The planner provides issue filenames at sprint creation time, or writes them to `sprint.md`'s `issues:` frontmatter during roadmap planning.
- **Main Flow**:
  1. Planner edits `sprint.md` frontmatter to add `issues: [filename1, filename2]` during roadmap phase.
  2. Either at creation time (if `issues:` is passed to `create_sprint`) or via a new `link_sprint_issues(sprint_id, issue_filenames)` tool call, the back-references are written to each issue file: `sprint: <sprint_id>`.
  3. From any issue, `sprint:` frontmatter points to the implementing sprint. From sprint.md, `issues:` lists the issues.
- **Postconditions**: `sprint.md` has `issues:` list; each referenced issue has `sprint: <id>` back-ref.
- **Acceptance Criteria**:
  - [ ] `create_sprint` template includes an empty `issues: []` field in sprint.md frontmatter.
  - [ ] A `link_sprint_issues(sprint_id, issue_filenames)` MCP tool (or equivalent) writes `sprint: <id>` back-refs on each referenced issue.
  - [ ] Calling `link_sprint_issues` twice is idempotent.
  - [ ] The `sprint-roadmap` skill guidance is updated to call `link_sprint_issues` after editing `issues:` in sprint.md.
