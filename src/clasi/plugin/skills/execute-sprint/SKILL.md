---
name: execute-sprint
description: Executes sprint tickets — dispatches programmer agents in dependency order, in parallel worktrees when the sprint opts in, otherwise serially
---

Executes all tickets in an active sprint by dispatching programmer agents in dependency order — in parallel via git worktrees when the sprint's `worktree` flag is set, otherwise serially on the sprint branch — then closes the sprint.

## Instructions

Load from: `clasi/schemas/se-process/instructions/execution.md`
