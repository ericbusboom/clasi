---
status: done
sprint: '003'
tickets:
- 003-001
---

# Consolidate redundant agent definitions and skill process descriptions

Three related issues with how agent instructions are organized:

## 1. Duplicated process between sprint-planner agent and plan-sprint skill

The sprint-planner workflow is described in three places that overlap and can drift:
- `plugin/agents/sprint-planner/agent.md` — 5-phase workflow (the canonical source
  that `clasi init` copies to target projects)
- `clasi/agents/domain-controllers/sprint-planner/agent.md` — another 5-phase
  workflow (used by the contracts system)
- `clasi/agents/domain-controllers/sprint-planner/plan-sprint.md` — roadmap +
  detail process (a more detailed version)

Additionally, `plugin/skills/plan-sprint/SKILL.md` (which `clasi init` installs to
`.claude/skills/plan-sprint/SKILL.md`) contains its own version of the roadmap +
detail process, overlapping with both the agent.md and the internal plan-sprint.md.

Pick one as the single source of truth and have the others reference it.

## 2. Three agent directory trees with different purposes

There are three locations for agent definitions:

- **`plugin/agents/`** (3 agents: team-lead, sprint-planner, programmer) — the
  canonical source. `clasi init` copies these into target projects' `.claude/agents/`.
- **`.claude/`** — output of `clasi init` for this repo. Not a source; ignore.
- **`clasi/agents/`** (13 agents in main-controller/domain-controllers/task-workers
  hierarchy) — used by `contracts.py` for contract validation. Contains 10 extra
  agents (architect, code-reviewer, sprint-executor, etc.) that don't exist in
  `plugin/agents/`.

The relationship between `plugin/agents/` and `clasi/agents/` is unclear. The extra
agents in `clasi/agents/` may be aspirational (planned but not yet wired up) or
vestigial. Either way, having two separate definitions for the same agent
(e.g., sprint-planner) in `plugin/agents/` and `clasi/agents/domain-controllers/`
guarantees drift.

## 3. Proposed resolution

Move `plugin/` into the `clasi` Python package as package data (e.g.,
`clasi/plugin/` or `clasi/package_data/`). This directory becomes the single source
of truth for all installable content: agents, skills, hooks, rules, templates.

- **`clasi/plugin/agents/`** — all agent definitions live here. Merge the useful
  content from `clasi/agents/` (contracts, extra agents) into this tree. Remove the
  separate `clasi/agents/` hierarchy.
- **`clasi init`** — copies from package data to the target project's `.claude/`.
  Already works this way via `_PLUGIN_DIR`; just needs the path updated.
- **`.claude/agents/` in this repo** — is just an install artifact, not a source.
  Add to `.gitignore` or regenerate via `clasi init` as needed. Don't edit directly.
- **`plugin/` at repo root** — remove after migration. It's a leftover from before
  the package was properly structured.
- **Process descriptions** — keep in one place per agent (the agent.md in package
  data), not duplicated across agent.md and skill files.
- **Audit the 10 extra agents** in `clasi/agents/` (architect, code-reviewer,
  sprint-executor, etc.) — keep if used by contracts or MCP dispatch, remove if
  vestigial.
