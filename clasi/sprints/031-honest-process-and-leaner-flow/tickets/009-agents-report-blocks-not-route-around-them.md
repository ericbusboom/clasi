---
id: 009
title: Agents report blocks, not route around them
status: open
use-cases:
- SUC-009
depends-on:
- '007'
github-issue: ''
issue: agents-must-report-blocks-not-route-around-them.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Agents report blocks, not route around them

## Description

Stakeholder observation (Eric, 2026-08-20): a dispatched agent hit a
role-guard block and worked around it (a Bash heredoc, since role-guard
matches only `Edit|Write|MultiEdit`) rather than handing it back. The
outcome was benign, but the method is what generalizes — "the value of a
guardrail is that it stops things; an agent that treats a block as an
obstacle to route around removes that value." This is sharpened by
role-guard's own porousness: a Bash heredoc bypasses it entirely, so the
gates depend on agents *choosing* to respect them.

**Depends on ticket 007 (soft — file-overlap ordering)**: both tickets
edit agent definitions (`programmer/agent.md`, `sprint-planner/agent.md`,
`team-lead/agent.md`). No logic dependency.

## Acceptance Criteria

- [ ] The stop/report/wait rule (stop; report what was attempted, the
      exact violation text, and the agent's own belief about the correct
      resolution; wait for the dispatcher) is stated **once**, in
      whichever of `.claude/rules/` or the agent definitions is the more
      natural canonical home given ticket 007's consolidation —
      referenced, not restated, from the programmer and sprint-planner
      agent definitions.
- [ ] The specific forbidden bypasses are named explicitly: Bash
      heredoc, `sed -i`, redirection, `git apply`, or any tool that
      dodges the role-guard matcher.
- [ ] The one legitimate exception (a deliberately invoked, reported
      `clasi oop on --reason '...'`) is stated — using it silently is
      still the same failure.
- [ ] Dispatch prompts/templates state that reporting a block is a
      *successful* dispatch outcome, not a failure.
- [ ] The role-guard/mcp-guard matcher's own coverage gap (Bash heredoc
      bypassing `Edit|Write|MultiEdit`) is **not** touched by this
      ticket — it is a norm fix, not a guard-code fix; note this
      explicitly in whatever doc states the norm so a future reader
      doesn't assume the gap is closed.

## Implementation Plan

**Approach**: write the rule once, wire references from the two agent
definitions, done — no code change.

**Files to modify**:
- One canonical home for the rule (a `.claude/rules/` file, or folded
  into whichever agent-definition consolidation ticket 007 already
  performed — confirm ticket 007's resulting structure before choosing,
  to avoid creating a second near-duplicate copy)
- `src/clasi/plugin/agents/programmer/agent.md` (and `.claude/agents/
  programmer/agent.md` if it's a separate installed copy)
- `src/clasi/plugin/agents/sprint-planner/agent.md` (and its installed
  copy, if separate)

**Do not modify**: role-guard/mcp-guard matcher code (explicitly out of
scope — see Acceptance Criteria's last bullet).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it — this ticket is
  literally about that norm, so model it precisely while implementing
  it.** Do not route around a block with a Bash heredoc, `sed`,
  redirection, or any mechanism that avoids the tool the guard is
  watching. Reporting a block is a successful outcome of this ticket,
  not a failure.

## Testing

- **Existing tests to run**: none specific to this doc-only change; run
  a lint/link-check if the project has one for cross-references.
- **New tests to write**: none — this is prose content with no testable
  behavior.
- **Verification command**:
  `uv run pytest tests/system/test_process_tools.py -v` (sanity check
  that agent-definition files still parse/load correctly via
  `get_agent_definition`).
