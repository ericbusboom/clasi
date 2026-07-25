---
id: '007'
title: Sync plugin-source team-lead agent doc off create_sprint
status: done
use-cases: []
depends-on: []
github-issue: ''
issue: team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sync plugin-source team-lead agent doc off create_sprint

## Description

Trivial, docs-only, independent of the design-overlay work above (no
architectural impact — see sprint.md Sizing Decision).
`src/clasi/plugin/agents/team-lead/agent.md` (the plugin-source copy)
still instructs the team-lead to call `create_sprint(title=<title>)`
directly in two places ("Execute Issues Through a Sprint" step 2 and
the "Sprint Planning Only" scenario step 1), but the `mcp-guard`
PreToolUse hook blocks tier-0 (team-lead) calls to
`mcp__clasi__create_sprint`, requiring dispatch to sprint-planner
instead. The **installed** copy,
`.claude/agents/team-lead/agent.md`, was already corrected — this
ticket mirrors that wording into the plugin-source copy so newly
installed/updated projects get the corrected instructions too.

**Note from planning**: diffing the installed vs. plugin-source copies
during architecture review found the installed doc has diverged well
beyond just the `create_sprint` fix (it now describes a roadmap/arc
multi-sprint model the plugin-source copy does not have). This ticket's
scope is narrowly the `create_sprint`-to-`sprint-planner`-dispatch
correction (the two places named in the issue file), not a full
reconciliation of every difference between the two files — a full
reconciliation is a larger, separate piece of work outside this
sprint's scope if the stakeholder wants it.

## Acceptance Criteria

- [x] `src/clasi/plugin/agents/team-lead/agent.md`'s "Execute Issues
      Through a Sprint" step 2 no longer instructs a direct
      `create_sprint` call; it instructs dispatching the sprint-planner
      agent to create the sprint (passing the title), matching the
      installed doc's corrected step 2-4 wording.
- [x] The "Sprint Planning Only" scenario's step 1 is corrected the same
      way.
- [x] Step 3's `link_sprint_issues` instruction is updated to recover
      the sprint id from the sprint-planner's report (since the
      team-lead can no longer observe it from a `create_sprint` call it
      didn't make) rather than assuming it was just created directly.
- [x] No remaining prose in the plugin-source `agent.md` instructs the
      team-lead to call `mcp__clasi__create_sprint` directly.
- [x] Walk the "Execute Issues Through a Sprint" scenario as written and
      confirm no step produces a guard denial (matches the issue's
      Verification section).

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "mcp_guard or role_guard or plugin"`
- **New tests to write**: none expected — this is a prose-only doc
  fix. If a guard test already exists asserting the denial behavior
  itself (from sprint 024 or earlier), no change is needed there; this
  ticket brings the doc in line with that already-tested guard
  behavior, it doesn't change the guard.
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
