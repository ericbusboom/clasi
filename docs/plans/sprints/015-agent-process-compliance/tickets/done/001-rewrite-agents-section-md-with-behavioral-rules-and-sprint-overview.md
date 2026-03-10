---
id: '001'
title: Rewrite agents-section.md with behavioral rules and sprint overview
status: done
use-cases:
- SUC-015-001
- SUC-015-002
- SUC-015-003
depends-on: []
---

# Rewrite agents-section.md with behavioral rules and sprint overview

## Description

Complete the agents-section.md template with the behavioral rules and sprint
overview identified in the reflection analysis. Two changes are already applied
(mandatory `get_se_overview()` gate and STOP gate with OOP escape). This ticket
adds the remaining sections.

**File**: `claude_agent_skills/init/agents-section.md`

### Changes

1. **Pre-flight check rule** (new section after the STOP gate): Before writing
   any code, confirm you have an active sprint and ticket. If not, enter the SE
   process to get one. Only exception: stakeholder said "out of process."

2. **CLASI-first routing rule** (new section): Before using any generic tool
   for a process activity (TODOs, branch finishing, reviews), check
   `list_skills()` for a CLASI-specific skill. CLASI skills take priority.

3. **Stop-and-report rule** (new section): When a required MCP tool or process
   step is unavailable, stop and report to the stakeholder. Do not create
   substitute artifacts or workarounds that bypass the process.

4. **Sprint process overview** (new section under ### Process): Numbered
   checklist of the sprint lifecycle with specific MCP tool references at each
   step, covering: create sprint → write docs → architecture review →
   stakeholder review → create tickets → execute tickets → close sprint.

## Acceptance Criteria

- [x] Pre-flight check rule present in agents-section.md
- [x] CLASI-first routing rule present in agents-section.md
- [x] Stop-and-report rule present in agents-section.md
- [x] Sprint process overview with MCP tool references present
- [x] All rules are phrased as hard gates, not suggestions
- [x] OOP escape hatch is referenced where appropriate

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: None (documentation change)
- **Verification command**: `uv run pytest`
