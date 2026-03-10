---
name: next
description: Determine the next process step and execute it
---

# Next Step Skill

This skill determines what needs to happen next in the SE process
and begins executing it.

## Process

1. Run the **project-status** skill to understand current state.
2. Based on the current stage, determine the next action:
   - No brief → Start requirements elicitation
   - Brief but no use cases → Continue requirements
   - Use cases but no architecture → Start architecture
   - Architecture exists, no sprint → Plan a sprint
   - Active sprint with todo tickets → Execute next ticket
   - All tickets done → Close the sprint
3. Begin executing the determined next action using the appropriate
   skill and agent.

## Output

Announce what was determined as the next step, then begin execution.
