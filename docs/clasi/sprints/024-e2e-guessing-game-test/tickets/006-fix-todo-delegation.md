---
id: "006"
title: "Fix TODO delegation"
status: todo
use-cases: []
depends-on: []
todo: "fix-todo-delegation.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix TODO delegation

## Description

Fix the TODO creation delegation so the team-lead passes raw stakeholder
input to the todo-worker agent instead of pre-formatting it. Currently
the team-lead rewrites stakeholder input into structured TODO format
before handing it off, which defeats the purpose of having a todo-worker.

### Changes

1. **Team-lead agent definition** -- Update instructions to state: when
   creating a TODO, pass the stakeholder's raw words to the todo-worker
   agent. Do not pre-format or pre-structure the content. The dispatch
   message should contain the stakeholder's original text, not a
   rewritten version.

2. **Todo-worker agent definition** -- Update instructions to make clear
   that it receives raw, unstructured stakeholder input and is
   responsible for all structuring, formatting, and YAML frontmatter
   generation. The todo-worker interprets the raw text and produces a
   proper TODO file.

3. **Dispatch protocol** -- Update the dispatch-subagent skill or
   subagent-protocol if needed so the team-lead's dispatch to the
   todo-worker looks like: "Create a TODO from this stakeholder input:
   [raw text]" -- not "Create a TODO with this title, this problem,
   this solution."

## Acceptance Criteria

- [ ] Team-lead agent definition explicitly instructs passing raw stakeholder text to todo-worker
- [ ] Team-lead agent definition explicitly prohibits pre-formatting TODO content
- [ ] Todo-worker agent definition states it receives raw input and is responsible for all formatting
- [ ] Todo-worker agent definition includes responsibility for YAML frontmatter generation
- [ ] Dispatch protocol (skill or subagent-protocol) supports raw-text delegation pattern
- [ ] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: None (this is agent definition/protocol changes)
- **Manual verification**: Ask the team-lead to create a TODO from conversational input and verify it dispatches raw text to the todo-worker
