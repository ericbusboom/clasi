# CLASI

An MCP server that gives Claude Code a structured software engineering
process. It provides agents, skills, and instructions
that guide an AI assistant through the full lifecycle of a project: from
requirements through architecture, sprint planning, implementation, and
release.

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
| `.claude/skills/*/SKILL.md` | Slash-command stubs (`/next`, `/todo`, `/status`, `/project-initiation`) |
| `.claude/settings.local.json` | MCP permission allowlist |
| `.mcp.json` | MCP server configuration pointing to `clasi mcp` |

After init, open the project in Claude Code.
The MCP server starts automatically when the AI connects.

## Typical Workflow

A project moves through four stages. You can drive the whole process with
the `/next` slash command, which inspects the current state and runs
whatever comes next.

### 1. Project Initiation

Start a new project by telling the agent what you want to build.
Use `/project-initiation` or just `/next` on an empty repo.

The agent interviews you, asks clarifying questions, and produces
`docs/clasi/design/overview.md` — a one-page summary of the problem, scope,
constraints, and high-level use cases.

### 2. Sprint Planning

When the overview is ready, `/next` creates a sprint. Each sprint gets:

- **Sprint document** — goals, scope, branch name
- **Use cases** — detailed scenarios for this sprint
- **Architecture document** — components, design decisions, sprint changes

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
tags a version, and archives the sprint to `docs/clasi/sprints/done/`.
Then `/next` picks up the next sprint or reports that the project is
complete.

## Slash Commands

| Command | What it does |
|---------|-------------|
| `/next` | Determine the next process step and execute it |
| `/status` | Report current project state, progress, and next actions |
| `/todo <description>` | Capture an idea as a TODO file in `docs/clasi/todo/` |
| `/project-initiation` | Start a new project with a guided interview |

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
  the `docs/clasi/` directory structure

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
