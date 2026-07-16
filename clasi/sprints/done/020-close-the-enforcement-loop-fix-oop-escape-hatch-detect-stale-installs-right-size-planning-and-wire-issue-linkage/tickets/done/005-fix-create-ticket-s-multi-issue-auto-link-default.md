---
id: '005'
title: Fix create_ticket's multi-issue auto-link default
status: done
use-cases:
- SUC-005
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

- [x] Creating a ticket with no `issue=` on a sprint linked to 2+ issues
      results in an empty `issue:` frontmatter field (or an explicit,
      clear error if option 2 is chosen) — never "all sprint issues."
- [x] Neither issue's `tickets:` backlink gains the ticket in that case.
- [x] Regression: a single-issue sprint still auto-links exactly that one
      issue when `issue=` is omitted, unchanged from current behavior.
- [x] Real fixture: test against an actual multi-issue sprint directory
      structure (e.g. reuse or model this very sprint's own 9-issue
      linkage), not a synthetic minimal stand-in.
- [x] `create_ticket`'s docstring updated to state the new default
      explicitly.
- [x] The `create-tickets` skill doc updated to instruct planners to pass
      `issue=` per ticket on any multi-issue sprint (reinforces, doesn't
      replace, the code fix).

## Resolution Notes

**Option chosen: Option 1** (don't auto-link when the sprint has 2+
linked issues; auto-link only fires in the unambiguous single-issue
case, otherwise `issue:` is left empty).

**Why 1 over 2**: Option 2 (error on omission with 2+ issues) would break
every existing caller and test that creates a ticket with no `issue=` on
a multi-issue sprint, turning a silent-wrong default into a hard failure
mode that has to be handled at every call site. Option 1 is strictly less
disruptive: single-issue sprints (the common case) are completely
unaffected, and multi-issue sprints simply get an empty `issue:` field
instead of a wrong one — a state the codebase already treats as normal
(see `test_no_todos_field_no_auto_link`). The cost of omission is now
"you must remember to link it," not "the tool throws," which matches how
`add_issue_ref` already works as an explicit, opt-in backfill path.
Silence-on-ambiguity plus a loud docstring/skill-doc callout was judged
sufficient given the accompanying doc updates (below) that make the
skip visible to a planner following the workflow.

**Code change**: `create_ticket` in `src/clasi/tools/artifact_tools.py`
now only takes the auto-link branch when
`len(sprint_issues) == 1`, instead of any truthy list.

**Docs updated for coherence with ticket 004**: Yes — ticket 004 wired
`link_sprint_issues` into the sprint-planner/team-lead workflows on the
premise that linking at the sprint level was sufficient for
`create_ticket`'s auto-link to "just work" downstream, without
distinguishing issue count. That premise is now wrong for 2+ issues.
Updated:
- `src/clasi/plugin/agents/sprint-planner/create-tickets.md` (Process
  steps 2 and the issue-lifecycle note) — now states auto-link only
  fires for exactly one linked issue and instructs passing `issue=`
  explicitly on multi-issue sprints.
- `src/clasi/plugin/agents/sprint-planner/agent.md` (Roadmap Mode step 2,
  Detail Mode Phase 1 step 2, Phase 4 step 13) — same correction in all
  three places that previously implied unconditional auto-link.
- `src/clasi/plugin/agents/team-lead/agent.md` (issue-linking step in
  "Start New Sprint from Issues", and the "Issue Lifecycle
  Responsibility" section) — same correction.
- `src/clasi/plugin/skills/create-tickets/SKILL.md` — added a
  "Multi-issue sprints — pass `issue=` explicitly" note.

`.claude/` is gitignored/generated; canonical sources above were edited
and `.claude/` regenerated via `clasi install --claude` to verify parity
(diffed identical), then the regenerated tree discarded since it isn't
tracked (aside from one pre-existing, out-of-scope legacy-tracked file
under `.claude/agents/team-lead/agent.md` that was reverted rather than
touched, per this ticket's scope).

**Also fixed a pre-existing test that encoded the bug**:
`tests/unit/test_issue_lifecycle.py::TestDocumentedLinkageSequenceProducesNonEmptyIssues::test_two_issues_linked_at_roadmap_time_appear_in_sprint_frontmatter`
(added by ticket 020-004) asserted that two tickets created without
`issue=` on a 2-issue sprint would both receive non-empty `issue:` via
auto-link — i.e., it asserted the exact bug this ticket fixes. Updated
it to create tickets with explicit `issue=` per the corrected docs, and
added a new test in the same class,
`test_omitting_issue_on_multi_issue_sprint_leaves_issue_field_empty`,
covering the omitted-`issue=` case directly.

**New/changed tests**:
- `tests/system/test_artifact_tools.py::TestCreateTicket::test_no_auto_link_when_sprint_has_multiple_issues`
  — real fixture (two genuine pending-pool issue files linked via
  `link_sprint_issues`, the actual production linkage path), asserts
  empty `issue:` and no backlink contamination.
- `tests/system/test_artifact_tools.py::TestCreateTicket::test_auto_links_single_sprint_issue_when_no_issue_param`
  — renamed/renarrowed regression test confirming the single-issue case
  is unchanged.
- `tests/unit/test_issue_lifecycle.py` — the two changes described above.

**Revert-check**: confirmed both ways. With the fix reverted (`git
stash` on `artifact_tools.py` only), both
`test_no_auto_link_when_sprint_has_multiple_issues` and
`test_omitting_issue_on_multi_issue_sprint_leaves_issue_field_empty`
fail with the exact old-bug symptom (`issue:` populated with
`['issue-a.md', 'issue-b.md']` instead of empty). With the fix restored,
all tests pass.

**Test results**: Full suite `uv run pytest --no-cov -q` — 2560 passed
(2558 baseline + 2 net new), 0 failures.

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
