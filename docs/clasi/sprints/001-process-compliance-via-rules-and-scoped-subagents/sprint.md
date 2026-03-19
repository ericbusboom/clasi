---
id: "001"
title: "Process Compliance via Rules and Scoped Subagents"
status: planning
branch: sprint/001-process-compliance-via-rules-and-scoped-subagents
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001: Process Compliance via Rules and Scoped Subagents

## Goals

Attack the persistent process-compliance problem from two new angles:
path-scoped `.claude/rules/` files that inject reminders at the point
of action, and directory-scoped subagent dispatch that restricts what
each subagent can touch.

## Problem

12 reflections over 5 weeks document the same failure: agents ignore
the CLASI SE process. Two prior hardening sprints (015, 017) tried
instructional fixes — prose directives, inline CLAUDE.md, template
reminders. All failed because instructions load once at session start
and fade from context by the time the agent makes decisions.

See `process-compliance-enforcement.md` (included in this sprint
directory) for the full analysis, timeline, and prior-attempt table.

## Solution

Three-part approach:

1. **Path-scoped rules** (`.claude/rules/*.md`) — Short, targeted
   instructions that fire when the agent accesses files in specific
   directories. Four rules covering planning artifacts, source code,
   TODOs, and git commits.

2. **Directory-scoped subagents** — Extend the dispatch-subagent skill
   so each subagent receives an explicit working-directory constraint.
   The controller validates that the subagent only modified files in
   its allowed directory. Post-dispatch validation catches violations.

3. **Init integration** — `clasi init` creates the rules files alongside
   other artifacts, so every CLASI project gets them automatically.

## Success Criteria

- Four rules files installed in `.claude/rules/`
- `clasi init` creates rules (idempotent)
- dispatch-subagent skill includes directory scope parameter
- Controller validates subagent output stays in scope
- Unit tests for init rules creation

## Scope

### In Scope

- Create `.claude/rules/` files: clasi-artifacts, source-code, todo-dir,
  git-commits
- Modify `init_command.py` to install rules
- Modify `dispatch-subagent` skill with directory scope
- Modify `subagent-protocol` instruction with scope validation
- Update architecture document with subagent structure diagram
- Unit tests for rules installation

### Out of Scope

- Blocking hooks (PreToolUse that returns non-zero) — research needed
- MCP server session state tracking
- Changes to the state database
- Intercepting generic tools (TodoWrite)

## Test Strategy

- Unit tests for `init_command.py` rules creation and idempotency
- Verify rules files have correct `paths` frontmatter
- `uv run pytest` for regressions

## Architecture Notes

The architecture document for this sprint focuses on the subagent
structure: how subagents are dispatched, scoped, validated, and how
rules provide directory-level enforcement. This is a significant
update to the architecture doc.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **#001 — Restructure agent directories into tier hierarchy**
   Move flat agents/ into three-tier hierarchy. Move agent-specific
   skills/instructions into agent directories. 34 file moves.

2. **#002 — Update process_tools.py for directory tree** (depends: #001)
   Update MCP tools to walk nested agent directories. New
   `get_agent_context()` tool. Update list/get for agents and skills.

3. **#003 — Write new agent definitions** (depends: #001)
   Create 5 new agent.md files (sprint-planner, sprint-executor,
   ad-hoc-executor, todo-worker, sprint-reviewer). Refactor
   main-controller and code-monkey.

4. **#004 — Create path-scoped rules and init integration**
   Four `.claude/rules/` files + `_create_rules()` in init_command.py.

5. **#005 — Update dispatch-subagent with scope and logging** (depends: #003, #006)
   Add scope_directory to dispatch prompt. Log full prompts to
   docs/clasi/log/.

6. **#006 — Create log directory structure and format**
   Establish docs/clasi/log/ structure. Logging utility for
   sprint/ticket/adhoc dispatch logs with full prompt text.
