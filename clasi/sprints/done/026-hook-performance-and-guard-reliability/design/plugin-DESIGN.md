# clasi.plugin

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`plugin/` is CLASI's packaged content root: the canonical, versioned copies of every agent definition, skill, hook config, and path-scoped rule/instruction that `clasi.platforms` installers copy or symlink into a target repository. It is a subsystem in the sense that matters here even though it holds no `.py` code of its own (it is entirely markdown/JSON/YAML content) — its boundary is "the source of truth for installable CLASI content," distinct from the platform-specific mechanics of *how* that content gets installed (that boundary belongs to `clasi.platforms`).

## 2. Orientation

Five content directories, each mirroring a distinct install target:

- `agents/` — per-agent-tier definition directories (`team-lead`, `sprint-planner`, `programmer`, plus a retired `old/`), each holding that agent's role prose. As of sprint 026, `agents/programmer/*` states explicitly that the test suite must run in the foreground (never `run_in_background: true`) and is scoped to the ticket, not the full suite — a sub-agent that backgrounds a long test run has no reliable way to be resumed when it completes, so it must stay alive to see the result itself.
- `skills/` — one directory per CLASI skill (`plan-sprint`, `execute-sprint`, `bootstrap-design`, `architecture-authoring`, etc.) — the full population of skills listed in the `list_skills` MCP tool. As of sprint 026, `project-initiation/SKILL.md` (and sibling docs that referenced the same literal: `instructions/software-engineering.md`, `agents/sprint-planner/plan-sprint.md`, `agents/sprint-planner/agent.md`, `agents/team-lead/project-status.md`, `skills/sprint-roadmap/SKILL.md`, `skills/project-status/SKILL.md`, `skills/architecture-authoring/SKILL.md`) resolve the project's configured `design_dir` instead of hardcoding `.clasi/design/` — the hardcoded path was wrong even for default-config projects, since `Project.design_dir` already defaults to `docs/design/`. `execute-sprint`'s skill content also now states that it owns the single full-test-suite run before sprint close, replacing the prior per-ticket redundant full-suite convention.
- `instructions/` — cross-cutting guidance documents (`coding-standards.md`, `git-workflow.md`, `testing.md`, `software-engineering.md`, etc.) plus a nested `languages/` directory for language-specific instruction files.
- `rules/` — the five canonical path-scoped rule bodies (mirrors `_rules.py`'s content, packaged as standalone files for platforms that consume rules as files rather than inline text).
- `hooks/hooks.json` — the Claude Code hook event wiring installed into a target repo's `.claude/settings.json`. As of sprint 026, this no longer registers `commit-check` (`PostToolUse`/`Bash` — read `os.environ["TOOL_INPUT"]`, which Claude Code never sets on this event, and had produced zero log lines across 2,447 recorded hook events), `TaskCreated`, or `TaskCompleted` (also never observed firing). Every remaining registration carries an explicit `timeout`, where none did before.

## 3. Constraints and Invariants

- **This directory is content, not code that runs in-process:** nothing here is imported by CLASI's own Python modules at runtime; it is read as files (copied or symlinked) by the `clasi.platforms` installers and served as text by `tools/process_tools.py`'s `get_skill_definition`/`get_agent_definition`/`get_instruction` MCP tools. Do not add import-time coupling from `plugin/` content into other packages.
- **Content here must stay in sync with what `process_tools.py`'s `list_skills`/`list_agents`/`list_instructions` enumerate:** those tools glob this directory directly, so adding a new skill/agent/instruction here is sufficient to make it discoverable — no separate registration step exists, but a missing frontmatter `description` field will surface as an empty description in the listing rather than an error.
- **Instructional content must resolve configured paths, never hardcode a default:** a skill or agent doc that names a literal path (e.g. `.clasi/design/`) instead of describing how to resolve `Project`'s corresponding property silently breaks for any project that has reconfigured that path via `.clasi/config.yaml`'s `paths:` map — and, as sprint 026 found, can be wrong even for a project using the default, if the hardcoded literal and the actual default have drifted apart.

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
