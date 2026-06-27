---
status: in-progress
sprint: '014'
tickets:
- 014-001
---

# Issues not moved to done & front matter not updated for sprint/ticket linkage

## Problem

Users complete sprints, but the issues those sprints resolved never show up in
`done/`, and issue front matter never records which sprint/ticket handled them.
This is tied to reported trouble closing tickets/sprints in VS Code.

## Root cause

The issue → sprint → ticket → done chain is fully built and works — but only
fires if issues actually get *linked*. Both symptoms share one root cause:
issues are never linked in the first place. With no `sprint:`/`tickets:` front
matter, the issue shows no sprint membership AND `_sweep_done_issues` skips it
(it requires a non-empty `tickets` list at `artifact_tools.py:184`), so it
never moves to `done/`.

Three concrete defects:

1. **Skill/agent docs never tell the agent to link.** `sprint-roadmap`,
   `plan-sprint`, and `team-lead` don't instruct calling `link_sprint_issues` /
   `create_ticket(issue=)` / `add_issue_ref`. The tools exist (added in sprint
   002) but nothing invokes them.
2. **Field-name bug** at `clasi/tools/artifact_tools.py:612`: `create_ticket`
   auto-links by reading the sprint's `todos` field, but `link_sprint_issues`
   writes `issues:`. So even a correctly-linked roadmap never auto-attaches
   issues to tickets.
3. **VS Code close-sprint failure**: `_close_sprint_full` (the git path used in
   VS Code) hard-fails on any unresolved linked issue
   (`artifact_tools.py:1256-1276`), while `_close_sprint_legacy` already leaves
   them behind non-blocking. The two paths diverged.

## Decisions confirmed with stakeholder

- **Keep** the current physical-move design: `create_ticket(issue=)` moves the
  issue into `<sprint>/issues/`, and it lands in `<sprint>/issues/done/` when
  resolved. Un-ticketed pending issues stay in `.clasi/issues/`.
- At sprint close: **sweep resolved issues to done, leave unresolved ones
  behind, and do not block the close** — report them for mop-up.

## Proposed fix

### A. Code

- **A1.** Fix `create_ticket` auto-link field mismatch
  (`clasi/tools/artifact_tools.py:612`): read `issues` first, fall back to
  `todos` for legacy sprints.
- **A2.** Make `_close_sprint_full` non-blocking on unresolved issues
  (`clasi/tools/artifact_tools.py:1256-1276`): mirror the legacy path — collect
  `unresolved_issues`, add to the success result, continue. Both close paths
  should behave identically.

### B. Docs / skills (the actual root cause — agents must invoke linkage)

- **B1.** `sprint-roadmap` SKILL.md (~45-46): instruct calling
  `link_sprint_issues(sprint_id, [filenames])` for every issue claimed.
- **B2.** `plan-sprint.md` (~53-57): call `link_sprint_issues` instead of manual
  `write_artifact_frontmatter`.
- **B3.** `create-tickets.md`: already correct (passes `issue=`, uses
  `add_issue_ref`); verify and lightly reinforce the back-ref requirement.
- **B4.** `team-lead` agent.md: add an "Issue lifecycle" responsibility — link
  at roadmap, ensure tickets carry `issue:` back-refs, and after close confirm
  resolved issues landed in `<sprint>/issues/done/` and mop up any
  `unresolved_issues`.
- **B5.** `close-sprint` SKILL.md (~56-70): document the auto-sweep and the
  non-blocking `unresolved_issues` report; instruct mopping up afterward.

## Verification

- Unit tests: `pytest tests/unit/test_sweep_done_issues.py
  tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py
  tests/unit/test_mcp_server.py -q`. Add cases for A1 (auto-link from sprint.md
  `issues:`) and A2 (close returns `unresolved_issues` instead of erroring).
- End-to-end via MCP tools in a scratch sprint: create issue →
  `link_sprint_issues` → `create_ticket(issue=)` → `move_ticket_to_done` →
  confirm issue swept to `<sprint>/issues/done/` with `status: done`;
  `close_sprint` with an unresolved issue → confirms it closes and reports
  `unresolved_issues`.
- Full suite: `pytest -q`.
