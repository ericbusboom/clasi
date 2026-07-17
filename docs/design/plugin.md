---
source_paths:
- /Volumes/Proj/proj/ai-projects/clasi/src/clasi/plugin
readme_path: /Volumes/Proj/proj/ai-projects/clasi/src/clasi/plugin/README.md
---
# clasi.plugin

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`plugin/` is CLASI's packaged content root: the canonical, versioned copies of every agent definition, skill, hook config, and path-scoped rule/instruction that `clasi.platforms` installers copy or symlink into a target repository. It is a subsystem in the sense that matters here even though it holds no `.py` code of its own (it is entirely markdown/JSON/YAML content) — its boundary is "the source of truth for installable CLASI content," distinct from the platform-specific mechanics of *how* that content gets installed (that boundary belongs to `clasi.platforms`).

## 2. Orientation

Five content directories, each mirroring a distinct install target:

- `agents/` — per-agent-tier definition directories (`team-lead`, `sprint-planner`, `programmer`, plus a retired `old/`), each holding that agent's role prose.
- `skills/` — one directory per CLASI skill (`plan-sprint`, `execute-sprint`, `bootstrap-design`, `architecture-authoring`, etc.) — the full population of skills listed in the `list_skills` MCP tool.
- `instructions/` — cross-cutting guidance documents (`coding-standards.md`, `git-workflow.md`, `testing.md`, `software-engineering.md`, etc.) plus a nested `languages/` directory for language-specific instruction files.
- `rules/` — the five canonical path-scoped rule bodies (mirrors `_rules.py`'s content, packaged as standalone files for platforms that consume rules as files rather than inline text).
- `hooks/hooks.json` — the Claude Code hook event wiring installed into a target repo's `.claude/settings.json`.

## 3. Constraints and Invariants

- **This directory is content, not code that runs in-process:** nothing here is imported by CLASI's own Python modules at runtime; it is read as files (copied or symlinked) by the `clasi.platforms` installers and served as text by `tools/process_tools.py`'s `get_skill_definition`/`get_agent_definition`/`get_instruction` MCP tools. Do not add import-time coupling from `plugin/` content into other packages.
- **Content here must stay in sync with what `process_tools.py`'s `list_skills`/`list_agents`/`list_instructions` enumerate:** those tools glob this directory directly, so adding a new skill/agent/instruction here is sufficient to make it discoverable — no separate registration step exists, but a missing frontmatter `description` field will surface as an empty description in the listing rather than an error.

## 4. Design

Each skill directory under `skills/` follows the same shape: a `SKILL.md` with YAML frontmatter (`name`, `description`) and a markdown body of instructions an agent loads and follows in place of its default approach. Agent definitions under `agents/` follow the tier structure documented in `agent.py`'s docstring (`Agent` base class; `MainController`/team-lead is tier 0). `docker-expert.zip` and `web_app_estimation_rubric.md` under `skills/` are non-standard entries (a packaged archive and a loose reference doc respectively) rather than `SKILL.md`-shaped directories — carried along as-is rather than restructured by this bootstrap run.

## 5. Interfaces

### Exposes
- **Skill content** (`skills/<name>/SKILL.md`), consumed via `get_skill_definition` and `list_skills` (MCP) and copied/symlinked into a target repo's `.claude/skills/` or platform equivalent by `clasi.platforms` installers.
- **Agent content** (`agents/<tier>/`), consumed via `get_agent_definition`/`list_agents` and by `clasi.agent.Agent`'s definition loading.
- **Instruction content** (`instructions/*.md`, `instructions/languages/*.md`), consumed via `get_instruction`/`list_instructions`/`get_language_instruction`.
- **Rule bodies** (`rules/*.md`) and **hook wiring** (`hooks/hooks.json`), consumed by the platform installers at install time.

### Consumes
- Nothing — this is a leaf content directory with no dependency on other CLASI subsystems; it is read by, not dependent on, `clasi.platforms` and `tools/process_tools.py`.

## 6. Open Questions / Known Limitations

- `agents/old/` appears to hold a retired agent definition kept for reference; whether it should be removed or is intentionally retained is not resolved by this bootstrap run.
- `skills/docker-expert.zip` and `skills/web_app_estimation_rubric.md` don't follow the `SKILL.md`-per-directory convention every other entry follows; left as-is since restructuring them is out of this ticket's scope.
