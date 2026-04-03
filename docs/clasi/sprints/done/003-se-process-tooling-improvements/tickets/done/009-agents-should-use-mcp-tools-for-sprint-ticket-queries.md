---
id: 009
title: Agents should use MCP tools for sprint/ticket queries
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: agents-should-prefer-mcp-tools-over-filesystem.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Agents should use MCP tools for sprint/ticket queries

## Description

The sprint-planner agent was observed using Glob and Bash `ls` to locate ticket
files instead of calling `list_tickets(sprint_id=...)`. The Glob missed tickets
stored in the `done/` subdirectory, leading to incorrect state reads and
unnecessary fallback commands.

The MCP tools (`list_tickets`, `list_sprints`, `get_sprint_status`,
`get_sprint_phase`) already handle these edge cases correctly — they search both
`tickets/` and `tickets/done/`, consult the state database, and return
normalized results. The agents just weren't told to use them.

This ticket adds an explicit rule to the sprint-planner and programmer agent
definitions prohibiting filesystem exploration of the sprint directory tree, and
directing agents to use MCP tools as the authoritative source of truth for
sprint and ticket state. The rule should be added as a shared file in
`clasi/plugin/rules/` and referenced (or simply present via Claude Code's rules
loading) in both agent contexts.

## Acceptance Criteria

- [x] A shared rule file exists at `clasi/plugin/rules/use-mcp-for-sprint-queries.md`
      that explicitly states: use `list_tickets`, `list_sprints`,
      `get_sprint_status`, and `get_sprint_phase` for sprint/ticket queries; do
      not use Glob, Bash, or `ls` to explore `docs/clasi/sprints/`
- [x] `clasi/plugin/agents/sprint-planner/agent.md` Rules section references or
      restates the MCP-over-filesystem rule
- [x] `clasi/plugin/agents/programmer/agent.md` Rules section references or
      restates the MCP-over-filesystem rule
- [x] `uv run pytest` passes

## Implementation Plan

### Approach

Add a new shared rule file and update both agent definitions. No source code
changes required — this is documentation/agent-definition work only.

### Files to Create

- `clasi/plugin/rules/use-mcp-for-sprint-queries.md` — shared rule stating that
  MCP tools are the source of truth for sprint and ticket state, listing the
  four tools to use, and prohibiting Glob/Bash/ls exploration of the sprint
  directory tree. Follow the style of existing rule files in that directory
  (e.g., `clasi-se-process.md`).

### Files to Modify

- `clasi/plugin/agents/sprint-planner/agent.md` — add a Rules section (or
  extend the existing one if present) with an entry: "Use MCP tools — not Glob,
  Bash, or ls — to query sprint and ticket state. See
  `clasi/plugin/rules/use-mcp-for-sprint-queries.md`."
- `clasi/plugin/agents/programmer/agent.md` — same addition to its Rules
  section (the programmer needs to check ticket status during implementation).

### Testing Plan

- This ticket contains no source code changes, so there are no new unit tests.
- Verify `uv run pytest` continues to pass to catch any accidental file
  corruption.
- Manual review: confirm the rule file clearly states the prohibited actions and
  the MCP alternatives, and that both agent files reference or restate the rule.

### Documentation Updates

The rule file itself is the documentation artifact. No other docs need updating.
