---
id: '002'
title: Issue-Ticket Linkage
status: planning-docs
branch: sprint/002-issue-ticket-linkage
use-cases: []
issues:
- propagate-issue-refs-across-sprint-tickets.md
- auto-completion-fragility-in-move-ticket-to-done.md
- sprint-todo-bidirectional-links.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 002: Issue-Ticket Linkage

## Goal

Make the issue-ticket relationship bidirectional and reliably auto-completable. Three interlocking problems were observed during sprint 001: only the first ticket in a multi-ticket sprint received the `issue:` frontmatter back-reference; the auto-completion guard in `move_ticket_to_done` short-circuits when the moved ticket lacks that reference; and no roadmap-phase mechanism existed to link sprints to the issues they implement. This sprint fixes all three surfaces — the structural propagation fix, the completion-logic safety-net fix, and the roadmap bidirectional link — together, because they touch the same models (`create_ticket`, `move_ticket_to_done`, sprint frontmatter, the Issue model).

## Issues in scope

- `issues/propagate-issue-refs-across-sprint-tickets.md` — add `add_issue_ref(ticket_path, issue_filename)` MCP tool so all tickets working toward an issue carry the `issue:` back-reference, and update the `create-tickets` skill to require it.
- `issues/auto-completion-fragility-in-move-ticket-to-done.md` — fix the completion guard in `move_ticket_to_done` to scan all in-progress sprint issues after every ticket move, not just when the moved ticket itself has an `issue:` ref.
- `issues/sprint-todo-bidirectional-links.md` — establish bidirectional sprint↔issue links during the roadmap phase: `sprint.md` frontmatter gains an `issues:` list; each issue gains a `sprint:` back-reference.

## Out of scope

- Changing the `issue:` frontmatter format itself (remains string-or-list).
- Auto-detecting which tickets touch an issue from static code analysis.
- Performance optimization of the per-move issue scan (O(n_issues) is acceptable for sprints with fewer than 20 issues).
- Changes to the `issue:` frontmatter schema or the Issue model's back-reference structure beyond what is needed for bidirectional linking.

## Notes / open questions

None. All three issues have clear approaches and the implementation surfaces are well understood from the sprint 001 post-mortem.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Extract _sweep_done_issues shared helper | — |
| 002 | Add add_issue_ref MCP tool | 001 |
| 003 | Fix move_ticket_to_done auto-completion guard | 001 |
| 004 | Add link_sprint_issues MCP tool and update sprint template | — |
| 005 | Update create-tickets skill guidance for multi-ticket issue propagation | 002 |

Tickets execute serially in the order listed.
