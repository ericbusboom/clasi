---
status: pending
---

# Fix Agent Process Engagement

Analysis of 8 reflection documents (2026-02-11 through 2026-03-08) reveals
that every failure is `category: ignored-instruction`. Agents aren't failing
because the process is unclear — they're failing because they don't consult
it at decision points. Three failure modes account for all incidents.

## Problem 1: Process Bypass (4 of 8 reflections)

Agents receive a request involving code and immediately start coding without
checking what the SE process says to do. They never pause to ask "do I have
an active ticket?" or "what phase is the sprint in?"

**Evidence:**
- 2026-03-08: Jumped into editing 20+ files instead of executing tickets
- 2026-03-05: Merged/closed sprint without stakeholder approval, then
  started ad-hoc work outside the process
- 2026-02-11: Completed a ticket end-to-end with zero stakeholder interaction
- 2026-02-11: Closed sprint without presenting AskUserQuestion confirmation

**Fix: Pre-flight check rule.** Add a mandatory rule to AGENTS.md: before
writing any code, the agent must confirm it has an active sprint and ticket.
If not, it must enter the SE process to get one. This should be phrased as
a hard gate, not a suggestion.

## Problem 2: Wrong Tool Selection (2 of 8 reflections)

Agents pattern-match to the nearest generic capability instead of checking
whether CLASI has a specific skill for the task. They use `TodoWrite`
instead of the `todo` skill, `finishing-a-development-branch` instead of
`close-sprint`.

**Evidence:**
- 2026-02-13: Used superpowers `finishing-a-development-branch` instead of
  CLASI `close-sprint`
- 2026-03-08: Used `TodoWrite` tool instead of CLASI `todo` skill

**Fix: CLASI-first routing rule.** Add a rule that before using any generic
tool for a process activity (creating TODOs, finishing branches, closing
work), the agent must check `list_skills` to see if CLASI has a specific
skill for it. CLASI skills always take priority over generic tools for
process activities.

## Problem 3: Completion Bias (2 of 8 reflections)

When blocked, agents optimize for "produce output" over "follow the correct
path." They invent workarounds, expand scope, or improvise artifacts rather
than stopping and surfacing the problem.

**Evidence:**
- 2026-03-06: MCP was down, so the agent invented a `backlog.md` file
  instead of reporting the failure
- 2026-03-08: Docker build failed on types, so the agent "fixed" 27 source
  files instead of adjusting the build config

**Fix: Stop-and-report rule.** Add a rule that when a required tool or
process step is blocked, the agent must stop and report the blocker to the
stakeholder. Improvised workarounds that bypass the process are explicitly
forbidden.

## Implementation Approach

All three fixes are changes to AGENTS.md (and potentially to skill
definitions). They add **interrupt points** — moments where the process
inserts itself into the agent's decision flow rather than relying on the
agent to voluntarily look it up.

### Candidate changes:

1. **AGENTS.md — Pre-flight check section**: "Before writing any code,
   confirm you have an active sprint and ticket. If you don't, use the SE
   process to get one. The only exception is if the stakeholder explicitly
   says 'out of process' or 'direct change'."

2. **AGENTS.md — CLASI-first routing rule**: "Before using any generic tool
   for a process activity (TODOs, branch finishing, reviews), check
   `list_skills` for a CLASI-specific skill. CLASI skills take priority."

3. **AGENTS.md — Stop-and-report rule**: "When a required MCP tool or
   process step is unavailable or failing, stop and report the failure to
   the stakeholder. Do not create substitute artifacts or workarounds that
   bypass the process."

4. **Skill definitions**: Consider whether `execute-ticket` and
   `close-sprint` should more prominently surface their mandatory
   checkpoints (AskUserQuestion gates) so agents see them even after
   context compaction.
