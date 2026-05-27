# CLASI

An MCP server that gives Claude Code a structured software engineering
process. It provides agents, skills, and instructions
that guide an AI assistant through the full lifecycle of a project: from
requirements through architecture, sprint planning, implementation, and
release.

## Philosophy

> "It is good to have an end to journey toward; but it is the journey that matters, in the end."
>
> — Ursula K. Le Guin, *The Wave in the Mind* (2004)

CLASI is built on the belief that a reliable process is what makes
good outcomes repeatable. The journey — planning, reviewing, iterating —
is the work.

## Installation

Install with [pipx](https://pipx.pypa.io/) directly from GitHub:

```bash
pipx install git+https://github.com/ericbusboom/clasi.git
```

This puts the `clasi` command on your PATH. To update later:

```bash
pipx upgrade clasi
```

For development, clone and install in editable mode:

```bash
git clone https://github.com/ericbusboom/clasi.git
cd clasi
pipx install -e .
```

## Initializing a Project

In any git repository, run:

```bash
clasi init
```

This creates:

| Path | Purpose |
|------|---------|
| `.claude/rules/*.md` | Always-on instructions loaded by Claude Code |
| `.claude/skills/*/SKILL.md` | Slash-command stubs (`/next`, `/issue`, `/status`, `/project-initiation`) |
| `.claude/settings.local.json` | MCP permission allowlist |
| `.mcp.json` | MCP server configuration pointing to `clasi mcp` |

After init, open the project in Claude Code.
The MCP server starts automatically when the AI connects.

## Issues vs Tickets

Two distinct concepts govern how work is tracked:

- An **issue** is a proposed change to the system — an idea, bug report,
  enhancement request, or task captured before sprint planning. Issues live
  in `.clasi/issues/`. They are the raw material that sprint planning draws
  from. A single issue may spawn one or more tickets, or be deferred
  indefinitely.

- A **ticket** is a concrete implementation step within a sprint. Tickets
  live in `.clasi/sprints/<sprint-id>/tickets/`. A ticket is derived from
  (and often closes) an issue, but it is scoped to what can be done in a
  single sprint and carries acceptance criteria, a plan, and a status that
  the SE process enforces.

In short: issues propose; tickets implement.

## Typical Workflow

A project moves through four stages. You can drive the whole process with
the `/next` slash command, which inspects the current state and runs
whatever comes next.

### 1. Project Initiation

Start a new project by telling the agent what you want to build.
Use `/project-initiation` or just `/next` on an empty repo.

The agent interviews you, asks clarifying questions, and produces
`.clasi/design/overview.md` — a one-page summary of the problem, scope,
constraints, and high-level use cases.

### 2. Sprint Planning

When the overview is ready, `/next` creates a sprint. Each sprint gets:

- **Sprint document** — goals, scope, branch name
- **Use cases** — detailed scenarios for this sprint
- **Architecture document** — components, design decisions, sprint changes (authored before tickets are created and archived as historical record at sprint close)

The plan goes through an architecture review gate and a stakeholder
approval gate before any code is written.

### 3. Ticket Execution

After approval, the sprint's architecture document is broken into numbered
tickets with dependency ordering. The agent executes them one by one:
plan, implement, test, commit.

You can watch it work or step away. Use `/status` at any time to see
where things stand.

### 4. Sprint Close

When all tickets are done, the agent merges the sprint branch to main,
tags a version, and archives the sprint to `.clasi/sprints/done/`.
Then `/next` picks up the next sprint or reports that the project is
complete.

## Slash Commands

| Command | What it does |
|---------|-------------|
| `/next` | Determine the next process step and execute it |
| `/status` | Report current project state, progress, and next actions |
| `/issue <description>` | Capture an idea as an issue file in `.clasi/issues/` |
| `/project-initiation` | Start a new project with a guided interview |

## Codex Integration

CLASI supports [OpenAI Codex](https://openai.com/codex) in addition to Claude Code.

### Installing for Codex

```bash
clasi init --codex
```

Or install for both Claude Code and Codex at once:

```bash
clasi init --claude --codex
```

### Files Written by `clasi init --codex`

| Path | Purpose |
|------|---------|
| `AGENTS.md` | Root marker file with the CLASI entry-point sentence (marker-managed CLASI section) |
| `.codex/config.toml` | Codex config with `[mcp_servers.clasi]` and `codex_hooks = true` |
| `.codex/hooks.json` | Stop hook that calls `clasi hook codex-plan-to-issue` (correct wrapper schema per the [Codex hooks spec](https://developers.openai.com/codex/hooks)); `codex-plan-to-todo` is a deprecated alias |
| `.codex/agents/team-lead.toml` | Sub-agent definition for the team-lead role |
| `.codex/agents/sprint-planner.toml` | Sub-agent definition for the sprint-planner role |
| `.codex/agents/programmer.toml` | Sub-agent definition for the programmer role |
| `.agents/skills/<name>/SKILL.md` | 26 skill workflow files (cross-tool standard — usable by any agent) |
| `.clasi/AGENTS.md` | Nested rule file: SE process rules for agents working in `.clasi/` |
| `clasi/AGENTS.md` | Nested rule file: source-code rules for agents working in `clasi/` |

### Sub-Agents

CLASI installs three Codex sub-agent definitions under `.codex/agents/`:
`team-lead`, `sprint-planner`, and `programmer`. These correspond to the
CLASI SE process roles and can be invoked as Codex sub-agents from within
a session.

### Stop Hook Firing Limitation

> **Note**: As of April 2026, Codex fires Stop hooks only from
> `~/.codex/hooks.json`, not from a repo-local `.codex/hooks.json`
> ([openai/codex#17532](https://github.com/openai/codex/issues/17532)).
> To enable plan-to-issue capture, copy `.codex/hooks.json` to
> `~/.codex/hooks.json` after install:
>
> ```bash
> cp .codex/hooks.json ~/.codex/hooks.json
> ```

### Removing Codex Integration

```bash
clasi uninstall --codex
```

This removes only CLASI-managed files and entries — the CLASI marker block
in `AGENTS.md`, `[mcp_servers.clasi]` from `.codex/config.toml`, the CLASI
Stop hook from `.codex/hooks.json`, the `.codex/agents/<name>.toml` sub-agent
files, the `.agents/skills/` skill files, and the nested `.clasi/AGENTS.md`
and `clasi/AGENTS.md` rule files. User-added content is preserved.

To remove only the Claude integration:

```bash
clasi uninstall --claude
```

---

## GitHub Copilot Integration

CLASI supports [GitHub Copilot](https://github.com/features/copilot) as a
third AI platform.

### Installing for Copilot

```bash
clasi init --copilot
```

Or install for all three platforms at once:

```bash
clasi init --claude --codex --copilot
```

### Files Written by `clasi init --copilot`

| Path | Purpose |
|------|---------|
| `.github/copilot-instructions.md` | Global Copilot instructions (marker-managed CLASI block) |
| `.github/instructions/*.instructions.md` | Path-scoped rules with `applyTo:` frontmatter |
| `.github/agents/team-lead.agent.md` | Sub-agent definition for the team-lead role |
| `.github/agents/sprint-planner.agent.md` | Sub-agent definition for the sprint-planner role |
| `.github/agents/programmer.agent.md` | Sub-agent definition for the programmer role |
| `.github/skills/` | Symlink to `.agents/skills/` (see canonical-symlink pattern below) |
| `.vscode/mcp.json` | VS Code MCP configuration with `servers.clasi` entry |

### Cloud Coding Agent MCP (manual step required)

After running `clasi init --copilot`, the VS Code MCP config is written
automatically. However, Copilot's **Cloud Coding Agent** reads MCP settings
from GitHub Settings, not from `.vscode/mcp.json`. To enable MCP for cloud
sessions:

1. Go to `https://github.com/settings/copilot` (or your org's settings page).
2. Under **Model Context Protocol (MCP) Servers**, click **Add MCP server**.
3. Paste the JSON snippet printed by `clasi init --copilot` at the end of the
   install output.

This step is not automatable from the CLI — it requires a browser login to
GitHub. The local VS Code integration works without it.

### Removing Copilot Integration

```bash
clasi uninstall --copilot
```

---

## Canonical-Symlink Pattern

CLASI writes skill files **once** to `.agents/skills/` and creates platform-
specific aliases via symlinks. This eliminates content duplication across tools
and ensures all platforms always see the same skill content without manual
synchronization.

```
.agents/skills/<name>/SKILL.md   ← canonical (single source of truth)
.claude/skills/<name>/SKILL.md   → symlink to canonical (Claude Code)
.github/skills/                  → directory symlink to .agents/skills/ (Copilot)
AGENTS.md                        ← canonical instruction file
CLAUDE.md                        → symlink to AGENTS.md (Claude Code shim)
```

### The `--copy` flag

In environments where symlinks are unavailable (Windows without Developer
Mode, some CI sandboxes), use `--copy` to write regular file copies instead:

```bash
clasi init --claude --codex --copilot --copy
```

With `--copy`, all aliases become independent file copies. Content will
drift if skills are updated later — re-run `clasi init` to refresh them.

### The `--migrate` flag

If a project was initialized before sprint 013 (when direct copies were
used instead of symlinks), `--migrate` converts legacy copies to symlinks:

```bash
clasi init --claude --migrate
```

The migrator content-matches each alias against its canonical before
converting. If content has diverged, the file is flagged as a conflict and
skipped — you can resolve it manually or force-overwrite with a fresh install.

---

## How It Works

CLASI is an MCP (Model Context Protocol) server. When Claude Code
connects, the server exposes tools that the AI calls to read process
definitions and manage artifacts:

- **Agents** — role definitions (`team-lead`, `sprint-planner`, `programmer`)
  that shape the AI's behavior for specific tasks. See `docs/design/overview.md`
  for the full agent architecture.
- **Skills** — step-by-step workflows (plan a sprint, execute a ticket, close
  a sprint) that the AI follows
- **Instructions** — coding standards, git workflow rules, and testing
  guidelines loaded on demand
- **Artifact tools** — create sprints, create tickets, track status, manage
  the `.clasi/` directory structure

The AI reads these definitions at runtime via MCP tool calls. The slash
command stubs installed by `clasi init` are thin wrappers that tell the
AI to fetch the real instructions from the server.

## Project Structure (for contributors)

```
claude_agent_skills/
├── agents/           # Agent role definitions (.md)
├── skills/           # Skill workflow definitions (.md)
├── instructions/     # Coding standards and guidelines (.md)
│   └── languages/    # Language-specific instructions
├── rules/            # Always-on rules installed to .claude/rules/
├── artifact_tools.py # Sprint, ticket, and planning MCP tools
├── process_tools.py  # Agent, skill, and instruction MCP tools
├── mcp_server.py     # MCP server entry point
├── init_command.py   # `clasi init` implementation
├── versioning.py     # Version tagging utilities
└── cli.py            # CLI dispatcher
```

## License

MIT
