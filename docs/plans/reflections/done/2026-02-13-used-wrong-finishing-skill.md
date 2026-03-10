---
date: 2026-02-13
sprint: '011'
category: ignored-instruction
---

# Used finishing-a-development-branch Instead of close-sprint

## What Happened

After completing all 3 tickets in sprint 011, the agent invoked the
`finishing-a-development-branch` superpowers skill to wrap up the work.
This skill presented generic options (merge locally, create PR, keep
as-is, discard) and the agent auto-approved "Push and create a Pull
Request", creating PR #6 on GitHub.

## What Should Have Happened

The agent should have used the CLASI `close-sprint` skill, which is the
process-defined way to close a completed sprint. The close-sprint skill:

1. Verifies all tickets are done
2. Confirms with the stakeholder
3. Advances the sprint phase to `closing`
4. Runs final validation
5. Merges the sprint branch into main directly
6. Archives the sprint via `close_sprint` MCP tool
7. Tags a version
8. Deletes the sprint branch

The CLASI process merges directly to main — it does not use pull requests
as an intermediate step.

## Root Cause

**Ignored instruction.** The `.claude/rules/clasi-se-process.md` rule
clearly states that the CLASI SE process is the default for all code
changes and that work is organized into sprints. The `close-sprint` skill
exists specifically for this purpose. The agent chose the superpowers
`finishing-a-development-branch` skill because it pattern-matched on
"branch work is done, need to finish" without checking whether the CLASI
process had its own completion workflow.

The `using-superpowers` skill's priority rules say "process skills first"
but the agent treated a generic superpowers skill as a process skill when
a domain-specific CLASI skill (`close-sprint`) was available.

## Proposed Fix

The `clasi-se-process.md` rule should explicitly mention that sprint
closing uses the `close-sprint` skill, not generic branch-finishing
workflows. Add a section like:

```markdown
## Sprint Completion

When all tickets in a sprint are done, use the `close-sprint` CLASI skill
(not the `finishing-a-development-branch` superpowers skill). The CLASI
process merges directly to main — do not create pull requests for sprint
branches unless the stakeholder explicitly requests one.
```
