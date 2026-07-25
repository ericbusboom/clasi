---
status: done
sprint: '025'
tickets:
- 025-007
---

# team-lead agent doc contradicts mcp-guard: create_sprint instruction is guard-blocked

## Description

`.claude/agents/team-lead/agent.md` instructs the team-lead to create
sprints directly in two places: "Execute Issues Through a Sprint" step 2
("**Create the sprint.** Call `create_sprint(title=<title>)`") and
"Sprint Planning Only" step 1 ("Create the sprint"). But the `mcp-guard`
PreToolUse hook (matcher `mcp__clasi__create_ticket|mcp__clasi__create_sprint`
in `.claude/settings.json`) blocks tier-0 calls with:

    CLASI ROLE VIOLATION: team-lead cannot call mcp__clasi__create_sprint
    directly. Dispatch to sprint-planner agent to create planning artifacts.

Observed live on 2026-07-17: the team-lead followed its role doc verbatim
and was denied. Every team-lead session that follows the documented flow
hits this wall, burns a turn, and has to infer the workaround (fold
sprint creation into the sprint-planner dispatch).

The role doc's step 3 also says to call `link_sprint_issues` "immediately
after `create_sprint`" — which assumes the team-lead observed the new
sprint id from a call it can no longer make; with creation delegated, the
team-lead must recover the id from the sprint-planner's report first.

## Cause

The mcp-guard tightened sprint/ticket creation to tier 1 without the
team-lead agent doc being updated to match.

## Proposed fix

Pick one side and align both:

- **Option A (match the guard — likely intended)**: update
  `.claude/agents/team-lead/agent.md` so the team-lead dispatches the
  sprint-planner to create the sprint (passing the title), then performs
  `link_sprint_issues` after the planner reports the sprint id. Update
  both scenarios and the "Issue Lifecycle Responsibility" section.
- **Option B (match the doc)**: remove `mcp__clasi__create_sprint` from
  the mcp-guard matcher so the team-lead can create the empty roadmap
  shell itself (creation writes only a template sprint.md; content
  authoring stays with the sprint-planner either way).

## Verification

- Walk the "Execute Issues Through a Sprint" scenario as team-lead in a
  live session: no step in the agent doc produces a guard denial.
- If Option A: a guard test with a real captured tier-0 payload asserts
  `create_sprint` is still denied.

## Related

- Same family as `role-guard-blocks-plan-mode-plans-dir.md` (guards and
  documented workflows drifting apart; gates discovered mid-flow).
