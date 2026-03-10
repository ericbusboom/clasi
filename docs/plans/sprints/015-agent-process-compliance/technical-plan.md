---
status: planning
from-architecture-version: "014"
to-architecture-version: "015"
---

# Sprint 015 Technical Plan

## Architecture Version

- **From version**: architecture-014
- **To version**: architecture-015 (adds sprint review tools to Artifact Tools)

## Architecture Overview

This sprint adds three new MCP tools to the Artifact Tools module and
modifies content files (agents-section.md, skill definitions, instructions).
The MCP server's tool surface grows but the architecture remains the same.

```
MCP Server
├── Process Tools (unchanged)
├── Artifact Tools
│   ├── existing tools (create_sprint, close_sprint, etc.)
│   └── NEW: review_sprint_pre_execution
│   └── NEW: review_sprint_pre_close
│   └── NEW: review_sprint_post_close
└── Shared Modules (unchanged)
```

Content changes (agents-section.md, skills, instructions) are delivered
through the existing Process Tools — no new delivery mechanism needed.

## Component Design

### Component: agents-section.md Template Rewrite

**Use Cases**: SUC-015-001, SUC-015-002, SUC-015-003

**File**: `claude_agent_skills/init/agents-section.md`

Changes (some already applied during out-of-process collaborative work):

1. **Mandatory gate** (lines 4–6, already done): "Before doing ANY work
   that involves code, you MUST call `get_se_overview()`."
2. **STOP gate with OOP escape** (lines 28–31, already done): "STOP. Call
   `get_se_overview()` if you haven't. Then follow the process or confirm
   OOP authorization."
3. **Pre-flight check** (new section): "Before writing code, confirm you
   have an active sprint and ticket. If not, enter the SE process."
4. **CLASI-first routing rule** (new section): "Before using any generic
   tool for a process activity, check `list_skills()` for a CLASI skill."
5. **Stop-and-report rule** (new section): "When a required tool is
   unavailable, stop and report. Do not improvise workarounds."
6. **Sprint process overview** (new section): Numbered checklist of the
   sprint lifecycle with specific MCP tool references at each step.

Also sync this project's `AGENTS.md` to match.

### Component: Sprint Review MCP Tools

**Use Cases**: SUC-015-004, SUC-015-005

**File**: `claude_agent_skills/artifact_tools.py`

Three new `@server.tool()` functions following the existing pattern.

#### `review_sprint_pre_execution(sprint_id: str) -> str`

Called before advancing to execution. Validates:
- On correct sprint branch
- Sprint directory exists with planning docs
- `sprint.md`, `technical-plan.md`, `usecases.md` exist with non-draft status
- Planning files have real content (not template defaults)
- Tickets exist and are in `todo` status

#### `review_sprint_pre_close(sprint_id: str) -> str`

Called before `close_sprint`. Validates:
- On correct sprint branch
- All tickets in `done` status and in `tickets/done/`
- Planning docs have correct status (not draft)
- No template placeholder content in planning files

#### `review_sprint_post_close(sprint_id: str) -> str`

Called after `close_sprint`. Validates:
- All tickets done and in `tickets/done/`
- Planning docs have correct final status
- Sprint directory archived to `sprints/done/`
- On master branch

**Return format** (all three):
```json
{
  "passed": false,
  "issues": [
    {
      "severity": "error",
      "check": "sprint_md_status",
      "message": "sprint.md still has status 'draft'",
      "fix": "Update sprint.md frontmatter status from 'draft' to 'active'",
      "path": "docs/plans/sprints/015-.../sprint.md"
    }
  ]
}
```

**Template detection**: Compare file content against the templates in
`claude_agent_skills/templates.py`. If a planning file's body (after
frontmatter) matches the template body, it's still a placeholder.

### Component: /oop Skill Definition

**Use Cases**: SUC-015-006

**File**: `claude_agent_skills/skills/oop.md` (new)

A simple skill definition that tells the agent:
- Skip all SE ceremony (no sprint, no tickets, no gates)
- Read the code, make the change, run the tests, commit to master
- For small, targeted changes only (typos, config tweaks, one-liners)

### Component: Narrative Mode in Project Initiation

**Use Cases**: SUC-015-007

**File**: `claude_agent_skills/skills/project-initiation.md`

Add a step early in the interview where the agent presents:
- "Answer structured questions" (current behavior)
- "Start an open narrative" (new option)

If narrative mode is chosen, the agent listens to free-form input, then
synthesizes it into the structured documents and follows up with
clarifying questions for gaps.

### Component: Mermaid Preference in Instructions

**Use Cases**: (quality-of-life)

**Files**:
- `claude_agent_skills/instructions/software-engineering.md`
- `claude_agent_skills/skills/create-technical-plan.md`
- `claude_agent_skills/skills/elicit-requirements.md`

Add guidance: "When illustrating system structure, data flow, or component
relationships, prefer Mermaid diagrams over ASCII art. Mermaid renders
natively in GitHub and most markdown viewers."

### Component: CLAUDE.md Linkage

**Use Cases**: SUC-015-001

**File**: `claude_agent_skills/init_command.py`

Ensure `clasi init` creates `CLAUDE.md` with an `@AGENTS.md` reference
when `CLAUDE.md` doesn't exist. This is likely already implemented — verify
and fix if not.

## Open Questions

(None — all design decisions resolved during stakeholder discussion.)
