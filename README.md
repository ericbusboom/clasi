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
`overview.md` in the project's configured design directory
(`paths.design` in `.clasi/config.yaml`, default `docs/design/`) — a
one-page summary of the problem, scope, constraints, and high-level
use cases.

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

## Codex / GitHub Copilot Integration (Archived)

CLASI previously supported [OpenAI Codex](https://openai.com/codex) and
[GitHub Copilot](https://github.com/features/copilot) alongside Claude
Code. As of sprint 032, both adapters were archived to the
`archive/codex-copilot-adapters` branch — neither was ever dogfooded in
this repo (Claude-only), both were reachable only via the explicit
`--codex`/`--copilot` flags, and the Codex adapter carried a live bug
where installing it after Claude overwrote Claude's resolved skill
content.

`--codex` and `--copilot` are still accepted by `clasi init`/`clasi
uninstall` for backward compatibility, but now exit with a clear error
pointing at the archive branch instead of installing anything or
silently no-op'ing. Plain `clasi init`/`clasi uninstall` (no platform
flag) are unaffected and continue to manage Claude support only. See
`src/clasi/platforms/DESIGN.md` for the full rationale.

---

## Canonical-Symlink Pattern

CLASI writes skill files **once** to `.agents/skills/` and creates platform-
specific aliases via symlinks. This eliminates content duplication across tools
and ensures all platforms always see the same skill content without manual
synchronization.

```
.agents/skills/<name>/SKILL.md   ← canonical (single source of truth)
.claude/skills/<name>/SKILL.md   → symlink to canonical (Claude Code)
AGENTS.md                        ← canonical instruction file
CLAUDE.md                        → symlink to AGENTS.md (Claude Code shim)
```

### The `--copy` flag

In environments where symlinks are unavailable (Windows without Developer
Mode, some CI sandboxes), use `--copy` to write regular file copies instead:

```bash
clasi init --claude --copy
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
