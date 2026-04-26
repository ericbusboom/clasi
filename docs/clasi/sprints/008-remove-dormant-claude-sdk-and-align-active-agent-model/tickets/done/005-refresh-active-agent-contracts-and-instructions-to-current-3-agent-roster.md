---
id: "005"
title: "Refresh active agent contracts and instructions to current 3-agent roster"
status: done
use-cases: ["SUC-004"]
depends-on: ["004"]
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Refresh active agent contracts and instructions to current 3-agent roster

## Description

Active plugin files (`agent.md` and `contract.yaml` under `clasi/plugin/agents/team-lead/`
and `clasi/plugin/agents/sprint-planner/`) still reference old agent names as delegation
targets. Specifically:

- `team-lead/contract.yaml` has `delegates_to` entries for `project-manager`,
  `sprint-executor`, `ad-hoc-executor`, `todo-worker`, and possibly `project-architect` —
  agents that either live only in `old/` or no longer exist at all.
- `team-lead/agent.md` may instruct the agent to dispatch to old agent names.
- `sprint-planner/contract.yaml` may list `architect`, `architecture-reviewer`,
  `technical-lead` as delegation targets (the sprint-planner absorbs these roles inline).

After this ticket, all active plugin files reference only the current active roster:
`team-lead`, `sprint-planner`, `programmer`.

## Acceptance Criteria

- [x] `team-lead/contract.yaml` `delegates_to` lists only agents present in the active `clasi/plugin/agents/` directory (not `old/`).
- [x] `team-lead/agent.md` does not instruct dispatching to `project-manager`, `sprint-executor`, `ad-hoc-executor`, `todo-worker`, `code-monkey`, `technical-lead`, `architect`, `architecture-reviewer`, `code-reviewer`, or `project-architect` as targets.
- [x] `sprint-planner/contract.yaml` does not list `architect`, `architecture-reviewer`, or `technical-lead` in `delegates_to`.
- [x] `sprint-planner/agent.md` accurately reflects the inline role with no dispatch-to-old-sub-agent language.
- [x] `programmer/contract.yaml` and `programmer/agent.md` are verified to contain no stale agent name references (likely already clean).
- [x] `uv run pytest tests/unit/test_contracts.py` passes.
- [x] `grep -r "code-monkey\|sprint-executor\|ad-hoc-executor\|technical-lead\|project-manager\|code-reviewer" clasi/plugin/agents/ --include="*.md" --include="*.yaml" | grep -v old/` returns no matches as delegation targets.

## Implementation Plan

### Approach

1. Read `team-lead/contract.yaml`: update `delegates_to` section — keep only `sprint-planner`
   and `programmer`. Remove any entry for an agent not in the active directory.
2. Read `team-lead/agent.md`: scan for dispatch instructions naming old agents. Replace with
   current agent names or remove the instruction if the behavior is gone.
3. Read `sprint-planner/contract.yaml`: remove `delegates_to` entries for old sub-agents.
   A result of `delegates_to: []` is correct — sprint-planner is inline.
4. Read `sprint-planner/agent.md`: verify description accurately says "handles architecture,
   review, and ticket creation inline." Remove any lingering dispatch-to-sub-agent text.
5. Read and verify `programmer/contract.yaml` and `programmer/agent.md` — likely no changes.

### Files to Create / Modify

- **Edit**: `clasi/plugin/agents/team-lead/contract.yaml`
- **Edit**: `clasi/plugin/agents/team-lead/agent.md`
- **Edit**: `clasi/plugin/agents/sprint-planner/contract.yaml` (if changes needed)
- **Verify/Edit**: `clasi/plugin/agents/sprint-planner/agent.md`
- **Verify**: `clasi/plugin/agents/programmer/contract.yaml` and `agent.md`

### Testing Plan

- After edits, run the grep command in the acceptance criteria to confirm no stale targets.
- `uv run pytest tests/unit/test_contracts.py` — contract loading tests pass.
- The content-check test added in ticket 006 will provide ongoing regression coverage.

### Documentation Updates

The edits to `agent.md` and `contract.yaml` are the documentation update. No other changes.
