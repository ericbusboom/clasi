---
id: "001"
title: "Fix create_ticket auto-link to read issues: field"
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: "ericbusboom/clasi#12"
issue:
  - issue-done-and-linkage-front-matter-not-updated.md
  - gh-12-ensure-all-tickets-that-implment-a-todo-are-linked.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix create_ticket auto-link to read issues: field

## Description

`create_ticket` in `clasi/tools/artifact_tools.py` auto-links a ticket to sprint
issues when no explicit `issue=` parameter is passed. The auto-link currently reads
the sprint's `todos:` frontmatter field. However, `link_sprint_issues` writes
`issues:` — so even a correctly-linked sprint never auto-attaches issues to new
tickets, because the field name doesn't match.

Fix: in the auto-link block (find `create_ticket` and the line that reads
`frontmatter.get("todos")`), read `issues:` first; fall back to `todos:` when
`issues:` is absent or empty, for legacy sprint compatibility.

## Acceptance Criteria

- [ ] When `create_ticket(sprint_id, title)` is called with no `issue=` argument and the sprint's `sprint.md` has `issues: [some-issue.md]`, the ticket is auto-linked to `some-issue.md`.
- [ ] When `issues:` is absent or empty but `todos:` is present, the ticket is auto-linked via `todos:` (legacy fallback preserved).
- [ ] When both `issues:` and `todos:` are absent, no auto-link occurs (existing behavior preserved).
- [ ] The issue file is physically moved to `<sprint>/issues/` and its frontmatter updated to `status: in-progress` as before.

## Implementation Plan

### Approach

Locate the auto-link block inside the `create_ticket` function. Do not rely on
line numbers — locate by function name and the string `frontmatter.get("todos")`.

Change the single-field read to a priority read:

```python
# Before:
sprint_issues = sprint.sprint_doc.frontmatter.get("todos")

# After:
sprint_issues = (
    sprint.sprint_doc.frontmatter.get("issues")
    or sprint.sprint_doc.frontmatter.get("todos")
)
```

The rest of the auto-link logic — the `isinstance(sprint_issues, list)` guard,
the assignment to `issue`, and the downstream `issue_list` processing — is
unchanged.

### Files to Modify

- `clasi/tools/artifact_tools.py` — the auto-link block inside `create_ticket`.
  Locate by: function `def create_ticket(` and comment `# Auto-link to sprint issues`.

### Testing Plan

- Run existing suite after the change:
  `pytest tests/unit/test_sweep_done_issues.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_mcp_server.py -q`
- New test cases are added in ticket 003.

### Documentation Updates

None for this ticket. Plugin doc changes are in tickets 004 and 005.
