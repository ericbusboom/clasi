---
name: project-initiation
description: Guides a stakeholder through a project initiation interview and produces a project overview document
---

# Project Initiation Skill

This skill creates a project overview document through a guided interview
with the stakeholder, using the product-manager agent.

## Agent Used

**product-manager**

## Inputs

- Stakeholder narration describing what they want to build

## Process

1. **Choose interview mode**: Present the stakeholder with options using
   `AskUserQuestion`:
   - "Answer structured questions" — the agent asks targeted questions
     one at a time to build the overview
   - "Start an open narrative" — the stakeholder speaks freely about
     their project, then the agent synthesizes and follows up

2. **Capture input**:

   **If structured mode**: Ask 4-6 targeted questions using
   `AskUserQuestion`, covering: what the project does, who it's for,
   key constraints, main scenarios, and out of scope.

   **If narrative mode**: Let the stakeholder speak freely. Listen to
   the full narration without interrupting. Then:
   a. Synthesize the narration into the overview document structure.
   b. Identify gaps — topics the narration didn't cover.
   c. Ask 2-3 follow-up questions via `AskUserQuestion` to fill gaps.

3. **Ask clarifying questions** (structured mode only): Present 2-4
   targeted questions using `AskUserQuestion` to fill gaps. Focus on:
   - Problem statement and target users (if unclear)
   - Key constraints (timeline, technology, budget)
   - High-level requirements (key scenarios)
   - Out of scope

3. **Create overview document**: Call `create_overview` MCP tool to create
   `docs/clasi/overview.md` with the template, then fill in each section
   using the narration and answers.

4. **Link into IDE instructions**: After creating the overview:
   - Copy or link it to `.claude/rules/project-overview.md` so Claude Code
     sees it as project context
   - Copy or link it to `.github/copilot/instructions/project-overview.md`
     for GitHub Copilot

5. **Stakeholder review**: Present the completed overview to the stakeholder.
   Use `AskUserQuestion`:
   - "Approve overview" (recommended)
   - "Request changes"

   If the stakeholder requests changes, revise and re-present. Only proceed
   when approved.

## Output

- `docs/clasi/overview.md` — The project overview document
- `.claude/rules/project-overview.md` — IDE-visible copy
- `.github/copilot/instructions/project-overview.md` — IDE-visible copy

## Notes

- This skill is for project initiation only. For detailed requirements on
  complex projects, use the **elicit-requirements** skill instead.
- After the overview is approved, use **plan-sprint** to begin the first
  sprint.
