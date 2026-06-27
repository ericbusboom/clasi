---
id: "006"
title: "Update plugin prompts to new default paths"
status: open
use-cases:
- SUC-006
depends-on: []
github-issue: ""
issue: ""
# completes_issue: Controls whether linked issues are archived when this ticket
# is moved to done. Default: true (archive when all referencing tickets are done).
# Set to false (scalar) to suppress archival for ALL linked issues on this ticket.
# Set to a mapping {filename.md: false} to suppress archival per issue filename.
# Use false for tickets that partially address a multi-sprint umbrella issue.
completes_issue: true
# exception: Written by a lower agent when it cannot proceed (see architecture §exception-protocol).
# exception:
#   thrown_by: "programmer"          # "programmer" | "sprint-planner"
#   thrown_at: "2026-05-07T14:23:00Z"
#   attempted: |
#     Description of what was attempted before giving up.
#   conflict: "architecture-update.md §3 — reason the agent is blocked"
#   surface: "internal"              # "user-visible" | "internal"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update plugin prompts to new default paths

## Description

Agent prompt and skill markdown files under `clasi/plugin/` (and their mirror
copies under `.claude/`) reference the old `.clasi/` artifact locations. After
this sprint changes the defaults, those literals will mislead agents about where
files live. This ticket updates all such references to match the new defaults.

Substitutions (these are the only four that change):
- `.clasi/issues` → `clasi/issues`
- `.clasi/sprints` → `clasi/sprints`
- `.clasi/reflections` → `clasi/reflections`
- `.clasi/architecture` → `docs/architecture`

Do NOT change:
- `.clasi/log` (log stays hidden)
- `.clasi/.clasi.db` (db stays hidden)
- `.clasi/design/` (design_dir default is already `docs/design`; these
  references may already point there)
- References like `.clasi/oop`, `.clasi/config.yaml`, `.mcp.json` (fixed anchors)

This ticket is independent of tickets 001–005 (no code dependency) and can
run in parallel, but must be committed before the sprint is closed.

## Acceptance Criteria

- [ ] `grep -r "\.clasi/issues" clasi/plugin/ .claude/` returns no results
      (except comments explaining the migration).
- [ ] `grep -r "\.clasi/sprints" clasi/plugin/ .claude/` returns no results.
- [ ] `grep -r "\.clasi/reflections" clasi/plugin/ .claude/` returns no results.
- [ ] `grep -r "\.clasi/architecture" clasi/plugin/ .claude/` returns no results.
- [ ] `grep -r "\.clasi/log" clasi/plugin/ .claude/` result count is unchanged
      (these references are correct and must NOT be changed).
- [ ] `uv run pytest` passes (markdown changes should not affect tests).

## Implementation Plan

### Files to Modify

Run the following audit to get the exact file list before editing:
```
grep -rl "\.clasi/\(issues\|sprints\|reflections\|architecture\)" \
  clasi/plugin/ .claude/
```

Known files from initial audit (verify the list before editing):
- `clasi/plugin/instructions/software-engineering.md`
- `clasi/plugin/instructions/subagent-protocol.md`
- `clasi/plugin/agents/sprint-planner/agent.md`
- `clasi/plugin/agents/sprint-planner/plan-sprint.md`
- `clasi/plugin/agents/sprint-planner/create-tickets.md`
- `clasi/plugin/agents/programmer/agent.md`
- `clasi/plugin/agents/team-lead/project-status.md`
- `clasi/plugin/rules/scold-detection.md`
- `clasi/plugin/rules/use-mcp-for-sprint-queries.md`
- `clasi/plugin/skills/sprint-roadmap/SKILL.md`
- `clasi/plugin/skills/consolidate-architecture/SKILL.md`
- `.claude/agents/sprint-planner/agent.md`
- `.claude/agents/sprint-planner/plan-sprint.md`
- `.claude/agents/sprint-planner/create-tickets.md`
- `.claude/agents/programmer/agent.md`
- `.claude/agents/team-lead/project-status.md`
- `.claude/rules/clasi-artifacts.md`
- `.claude/rules/todo-dir.md`

### Implementation Steps

1. Run the audit grep to confirm the full file list.
2. For each file, apply the four substitutions above using search-and-replace.
3. Re-run the audit greps to confirm zero residual matches.
4. Run `uv run pytest` to confirm no test regressions.

### Note on this repo's behavior

Because this repo uses the config-pin from ticket 004 (`.clasi/` paths
explicit in config.yaml), agents running in this repo will still correctly
find files at `.clasi/issues` etc. The prompt literal change is cosmetically
forward-looking (matching the new default), not a breaking change for repos
still at the old layout.

### Testing Plan

No new tests. Verification:
- Audit grep returns zero results for the four changed patterns.
- `uv run pytest` green.

Run: `uv run pytest -x`
