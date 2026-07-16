---
id: '005'
title: Fix create_ticket's multi-issue auto-link default
status: open
use-cases: [SUC-005]
depends-on: []
github-issue: ''
issue: create-ticket-auto-links-all-sprint-issues-to-every-ticket.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix create_ticket's multi-issue auto-link default

## Description

`create_ticket`'s auto-link convenience (`artifact_tools.py:586-589`)
links a ticket created without an explicit `issue=` to *all* of the
sprint's linked issues once there is more than one. Sprint 019 hit this
directly: tickets 002-006 (enforcement work only) were born referencing
an unrelated stray-file issue too, and that issue's `tickets:` backlink
accumulated them. Confirmed NOT a bug in `add_issue_ref` — it only appends
the filename it's given and is idempotent; the extra refs were already
present at ticket creation.

Sprint 020 itself (this sprint) has 9 linked issues and worked around the
bug by passing `issue=` explicitly to every `create_ticket` call — proving
the workaround but not fixing the default. Fix the default itself.

Preferred fix (per the issue, option 1): don't auto-link when the sprint
has more than one linked issue; leave `issue:` empty and require the
caller to pass it explicitly. Option 2 (error if omitted with 2+ issues)
is acceptable if it's judged clearer, but option 1 is less disruptive to
existing callers that pass no `issue=` on purpose for a single-issue
sprint.

## Acceptance Criteria

- [ ] Creating a ticket with no `issue=` on a sprint linked to 2+ issues
      results in an empty `issue:` frontmatter field (or an explicit,
      clear error if option 2 is chosen) — never "all sprint issues."
- [ ] Neither issue's `tickets:` backlink gains the ticket in that case.
- [ ] Regression: a single-issue sprint still auto-links exactly that one
      issue when `issue=` is omitted, unchanged from current behavior.
- [ ] Real fixture: test against an actual multi-issue sprint directory
      structure (e.g. reuse or model this very sprint's own 9-issue
      linkage), not a synthetic minimal stand-in.
- [ ] `create_ticket`'s docstring updated to state the new default
      explicitly.
- [ ] The `create-tickets` skill doc updated to instruct planners to pass
      `issue=` per ticket on any multi-issue sprint (reinforces, doesn't
      replace, the code fix).

## Implementation Plan

**Approach**: Modify the auto-link branch in `create_ticket`
(`src/clasi/tools/artifact_tools.py:586-589`) to check the count of the
sprint's linked issues before defaulting; only auto-link when exactly one
issue is linked.

**Files likely involved**: `src/clasi/tools/artifact_tools.py`,
`.claude/skills/create-tickets/` (and `src/clasi/plugin/skills/create-tickets/`
mirror), `tests/unit/test_artifact_tools.py` (or wherever `create_ticket`
is currently tested).

**Testing plan**: Real multi-issue sprint fixture (2+ issues, no
`issue=` passed) asserting empty `issue:` and no stray backlinks;
single-issue regression test; docstring/skill-doc content check.

**Documentation updates**: `create_ticket` docstring, `create-tickets`
skill doc.
