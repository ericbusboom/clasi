---
status: pending
type: bug
source: e2e-test-run-003
clasi_version: 0.20260715.2
tags:
- issues
- linkage
- lifecycle
- e2e
---

# Issue-to-sprint linkage never fires: all issues fields remain empty

## Description

Sprint 014 implemented the full issue→sprint→ticket→done lifecycle: issues should be bidirectionally linked to sprints via frontmatter, and swept to `done/` at close. But in practice, agents never invoke the linkage tools. All 4 sprints in the e2e test show `issues: []` — no issues were ever linked to any sprint.

## Evidence (e2e run 003)

All sprint.md frontmatter files show empty issue lists:

```
clasi/sprints/done/001-.../sprint.md:  issues: []
clasi/sprints/done/002-.../sprint.md:  issues: []
clasi/sprints/done/003-.../sprint.md:  issues: []
clasi/sprints/done/004-.../sprint.md:  issues: []
```

This is despite sprint 014 adding explicit instructions to `sprint-roadmap`, `plan-sprint`, `create-tickets`, `team-lead`, and `close-sprint` skill docs telling agents to call `link_sprint_issues`, `create_ticket(issue=)`, and `add_issue_ref`.

## Impact

- The `clasi/issues/` queue has no bidirectional linkage to sprints or tickets
- Issue lifecycle is incomplete: issues are created but never connected to the work that resolves them
- The chain exists architecturally (tools + skills + docs) but doesn't fire because agents aren't instructed — or aren't being prompted — at the right moments

## Related

- Sprint 014: issue-ticket linkage and done lifecycle
- `clasi/issues/done/e2e-test-plan-002-guessing-game.md` — observation #8