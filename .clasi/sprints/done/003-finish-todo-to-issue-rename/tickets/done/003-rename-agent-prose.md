---
id: '003'
title: Rename agent instruction prose from todo to issue
status: done
use-cases:
- SUC-003
depends-on:
- '002'
issue: finish-the-todo-issue-rename.md
---

## Description

Update three agent instruction files that use "TODO" as the CLASI artifact
noun. Agents read these files at runtime; keeping them consistent with the
live vocabulary prevents agents from using stale terminology in their output.

Files in scope (exact locations from the issue audit):
- `clasi/plugin/agents/sprint-planner/plan-sprint.md:56-57`
- `clasi/plugin/agents/sprint-planner/create-tickets.md:44-46`
- `clasi/plugin/agents/team-lead/agent.md:42-44`

## Acceptance Criteria

- [x] `plan-sprint.md:56-57`: "For each TODO claimed by this sprint" → "For each issue claimed by this sprint"
- [x] `create-tickets.md:44-46`: "Propagate TODO and GitHub issue references" → "Propagate issue and GitHub issue references"; "set the ticket's `todo` frontmatter field to the TODO filename" → updated to use `issue` field terminology
- [x] `agent.md:42-44`: "If TODOs exist, read them and produce impact assessments" → "If issues exist, read them and produce impact assessments"
- [x] No other lines in these files are modified
- [x] Full test suite passes (no agent-prose tests exist, but suite should remain green)

## Implementation Plan

### Approach

Read each file. Locate the exact line numbers from the audit. Replace only
the "TODO" (artifact noun) occurrences. Be careful in `create-tickets.md`:
the phrase "GitHub issue" must remain unchanged — only the CLASI-artifact
"TODO" references are renamed.

### Files to Modify

- `clasi/plugin/agents/sprint-planner/plan-sprint.md`
- `clasi/plugin/agents/sprint-planner/create-tickets.md`
- `clasi/plugin/agents/team-lead/agent.md`

### Testing Plan

- Run `pytest tests/unit/` — no test coverage for agent prose, but confirm
  suite stays green.
- Read the modified lines back to confirm "GitHub issue" is intact in
  `create-tickets.md` and only CLASI-artifact "TODO" references were changed.

### Documentation Updates

These files are themselves documentation / instruction artifacts.
