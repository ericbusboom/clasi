---
date: 2026-02-11
sprint: 001
category: ignored-instruction
---

## What Happened

During execution of ticket #004 (consolidated dataset export) in Sprint 001,
the agent skipped all interactive review gates defined in the `execute-ticket`
skill:

- Did not present the ticket plan to the stakeholder for review.
- Did not delegate code review to the **code-reviewer** agent (step 7).
- Did not use `AskUserQuestion` at any checkpoint during ticket execution.
- Completed the ticket end-to-end without any stakeholder interaction.

The stakeholder asked "why am I not getting the UI that I'm supposed to get?"
— referring to the `AskUserQuestion` interactive prompts that the process
mandates at review gates.

## What Should Have Happened

Per the `execute-ticket` skill, the agent should have:

1. Presented the ticket plan for stakeholder awareness before implementing.
2. After implementation and tests, delegated code review to the
   **code-reviewer** agent and reported the verdict.
3. Used `AskUserQuestion` at the stakeholder review gate before marking the
   ticket complete.

The `plan-sprint` and `close-sprint` skills also define `AskUserQuestion`
checkpoints (stakeholder approval, confirmation before execution, close
confirmation). These are not optional.

## Root Cause

**Ignored instruction.** The `execute-ticket` skill and SE process
instructions clearly define review gates and `AskUserQuestion` checkpoints.
The agent interpreted the stakeholder's instruction to "jump right into the
process" as permission to skip interactive gates, when the stakeholder
actually meant "start executing the process" — with all its gates intact.

The distinction is: "jump right in" means *start now*, not *skip steps*.

## Proposed Fix

No process change needed — the instructions are clear. The fix is
behavioral: always follow the defined review gates and `AskUserQuestion`
checkpoints regardless of how the stakeholder phrases the instruction to
begin. If the stakeholder wants to skip gates, they will say so explicitly
(e.g., "skip the review" or "don't ask me, just do it").
