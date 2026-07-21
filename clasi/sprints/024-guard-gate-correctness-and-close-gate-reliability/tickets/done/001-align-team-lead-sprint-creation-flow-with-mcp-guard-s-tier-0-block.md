---
id: '001'
title: Align team-lead sprint-creation flow with mcp-guard's tier-0 block
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Align team-lead sprint-creation flow with mcp-guard's tier-0 block

## Description

The team-lead agent doc (`.claude/agents/team-lead/agent.md`) instructs a
direct `create_sprint` call in its "Sprint Planning Only" scenario. The
mcp-guard hook blocks `create_sprint` at tier 0 (team-lead's tier), so every
team-lead session that follows the documented flow hits a guard denial.

Fix per the issue's Option A: the team-lead does not call `create_sprint`
directly. Instead it dispatches sprint-planner (which runs at a tier the
guard permits to call `create_sprint`) with the sprint title and issue
references. Sprint-planner calls `create_sprint` and reports the new sprint
id back in its final response. Team-lead then recovers that sprint id from
the report and calls `link_sprint_issues(sprint_id, [...])` itself.

Note: the "Execute Issues Through a Sprint" scenario in the same doc was
already fixed for this contradiction in a prior out-of-process session. This
ticket fixes the one remaining scenario — "Sprint Planning Only" — which
still has the old direct `create_sprint` instruction.

## Acceptance Criteria

- [x] `.claude/agents/team-lead/agent.md`'s "Sprint Planning Only" scenario
      no longer instructs a direct `create_sprint` call; it instructs
      dispatching sprint-planner with title and issue references, then
      recovering the sprint id from the planner's report.
- [x] The doc explicitly instructs team-lead to call `link_sprint_issues`
      itself after recovering the sprint id (matching the pattern already
      used in "Execute Issues Through a Sprint").
- [x] Walking this flow live as team-lead produces no `CLASI ROLE
      VIOLATION` denial at any step. (Verified by manual trace against
      `handle_mcp_guard`, per the ticket's own testing plan: no step in
      the rewritten scenario calls `create_sprint`, `create_ticket`, or
      any other tier-0-blocked MCP tool directly — the only direct MCP
      call is `link_sprint_issues`, which is not guarded. A full live
      walkthrough requires an actual stakeholder-driven team-lead session
      dispatching sprint-planner, which is outside a doc-only ticket's
      scope to execute.)
- [x] A guard test with a real captured tier-0 payload still asserts
      `create_sprint` is denied for team-lead — this ticket aligns the doc
      to the guard, not the reverse. If such a test does not already
      exist, add one; if it exists, confirm it still passes unmodified.
      (No such test existed; added
      `TestMcpGuardBlocksCreateSprintAtTierZero` in
      `tests/unit/test_hook_handlers.py`, using the fully-prefixed
      `mcp__clasi__create_sprint` tool name — the real string matched by
      `.claude/settings.json`'s mcp-guard matcher — asserting tier-0 denial
      and a tier-1 allow regression control. Both pass.)
- [x] No other scenario in the agent doc still instructs a direct
      `create_sprint`, `create_ticket`, or other tier-0-blocked MCP call
      (spot-check the full doc, not just the one scenario named above).
      (Confirmed via grep: the only remaining occurrences are the already
      guard-aligned "never call `create_sprint` directly" instruction in
      "Execute Issues Through a Sprint" and a factual note about
      `create_ticket`'s auto-link behavior — neither instructs a direct
      blocked call.)

## Implementation Plan

**Approach**: This is a documentation-only fix (Trivial/small per the
issue's own scope) targeting one file. Read the current "Sprint Planning
Only" scenario text, read the already-fixed "Execute Issues Through a
Sprint" scenario as the pattern to mirror, and rewrite the former to match
the latter's dispatch-then-link structure.

**Files to modify**:
- `.claude/agents/team-lead/agent.md` — rewrite the "Sprint Planning Only"
  scenario's steps.

**Testing plan**:
- No code changes, so no new unit tests are required for the doc edit
  itself.
- Confirm (or add, if missing) a guard-level test using a real captured
  tier-0 `create_sprint` payload that asserts the guard still denies it —
  this is the regression check that the doc fix must not be paired with a
  guard loosening.
- Manually trace the new doc instructions against `handle_mcp_guard` to
  confirm no step in the rewritten scenario calls a tier-0-blocked tool
  directly.

**Documentation updates**:
- `.claude/agents/team-lead/agent.md` is itself the documentation being
  updated; no other doc references this scenario.
