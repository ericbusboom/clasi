---
id: 008
title: OOP skill should close TODOs after implementation
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: oop-skill-should-close-todos.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# OOP skill should close TODOs after implementation

## Description

The `oop` skill in `clasi/plugin/skills/oop/SKILL.md` describes a quick,
ceremony-free change process. It currently ends at "commit directly to master."
When the change addresses a TODO, there is no instruction to close that TODO via
`move_todo_to_done`. The ticket-based workflow handles this automatically (the
ticket's done step triggers TODO closure), but OOP bypasses tickets entirely,
leaving TODOs open after the work is complete.

Add a step to the OOP skill's Process section: after committing, if the work
addressed a TODO, call `move_todo_to_done` to close it. This makes TODO closure a
structural part of the OOP process, not something the agent must remember
separately.

## Acceptance Criteria

- [x] `clasi/plugin/skills/oop/SKILL.md` includes a step after the commit step
      instructing the agent to call `move_todo_to_done` if the work addressed a
      TODO
- [x] The new step is clear about when it applies (only when a TODO was the
      origin of the work)
- [x] `uv run pytest` passes with no failures

## Implementation Plan

### Approach

Edit `clasi/plugin/skills/oop/SKILL.md`. In the Process section, add a step
after step 4 (commit to master). The new step should read approximately:

> 5. If the work addressed a TODO, call `move_todo_to_done` with the TODO
>    filename to close it.

Keep the wording tight and conditional — only when a TODO was the starting point.
Do not add ceremony for cases where no TODO exists.

### Files to Modify

- `clasi/plugin/skills/oop/SKILL.md` — add step 5 to the Process section

### Testing Plan

- Run `uv run pytest` to confirm no regressions.
- No new tests are needed — this is a documentation-only change to a skill file.

### Documentation Updates

The change is entirely within the skill definition file itself.
