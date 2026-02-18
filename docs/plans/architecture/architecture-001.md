---
version: "001"
status: current
sprint: null
description: Initial baseline — retroactive description of the system as it exists at sprint 014
---

# Architecture 001: CLASI System Baseline

This document describes the CLASI (Claude Agent Skills Instructions) system
as it exists today. It is a retroactive baseline, not a design document —
no architectural changes are being proposed.

## Architecture Overview

CLASI is a Python package that provides a structured software engineering
process for AI-assisted development. It consists of three subsystems:

1. **CLI** — Command-line entry points for initialization, MCP server
   startup, and TODO file management.
2. **MCP Server** — A FastMCP-based server exposing 29 tools over stdio for
   AI agents to query process content and manage project artifacts.
3. **Bundled Content** — Markdown definitions for agents, skills, and
   instructions that define the SE process.

```
CLI (cli.py) → init_command.py     # clasi init
             → mcp_server.py       # clasi mcp
             → todo_split.py       # clasi todo-split

MCP Server (mcp_server.py)
  ├── process_tools.py  (10 read-only tools → serve content)
  └── artifact_tools.py (19 read-write tools → manage project artifacts)

Shared Modules:
  ├── frontmatter.py    (YAML frontmatter I/O)
  ├── templates.py      (artifact templates + slugify)
  ├── state_db.py       (SQLite sprint lifecycle state machine)
  └── versioning.py     (date-based version tagging)
```

### Dependency Map

```
cli → init_command (lazy)
cli → mcp_server (lazy)
cli → todo_split (lazy)

mcp_server → process_tools (side-effect import)
mcp_server → artifact_tools (side-effect import)

process_tools → mcp_server (server singleton, content_path)
process_tools → frontmatter (read_document)

artifact_tools → mcp_server (server singleton)
artifact_tools → frontmatter (read/write)
artifact_tools → state_db (all functions)
artifact_tools → templates (all templates + slugify)
artifact_tools → versioning (lazy, at sprint close)

todo_split → templates (slugify)
```

Leaf modules with no internal dependencies: `frontmatter`, `templates`,
`state_db`, `versioning`, `init_command`.

## Technology Stack

| Attribute | Value | Justification |
|-----------|-------|---------------|
| Language | Python >=3.10 | Target users are Claude Code / AI agent environments that have Python |
| CLI framework | Click >=8.0 | Lightweight, composable subcommands |
| MCP framework | FastMCP (mcp >=1.0) | Standard protocol for AI agent tool access |
| YAML parsing | PyYAML >=6.0 | Frontmatter I/O for markdown artifacts |
| State storage | SQLite (stdlib) | Zero-dependency, file-based, embedded in project |
| Build system | setuptools >=61.0 | Standard Python packaging |
| Version format | `<major>.<YYYYMMDD>.<build>` | Date-based, auto-incrementing |
| Test framework | pytest + pytest-cov | Standard, with 85% branch coverage threshold |

## Component Design

### Component: CLI (`cli.py`)

**Purpose**: Routes user commands to the appropriate subsystem.

**Boundary**: Accepts command-line arguments, delegates to implementation
modules. Does not contain business logic.

**Interface**:
- `clasi init [target]` — Initialize a repo for CLASI
- `clasi mcp` — Run the MCP server on stdio
- `clasi todo-split [todo_dir]` — Split multi-heading TODO files

**Use cases served**: Project initialization, server startup, TODO management.

### Component: Init Command (`init_command.py`)

**Purpose**: Installs the CLASI SE process into a target repository with
minimal footprint.

**Boundary**: Reads/writes files in the target directory. Does not interact
with the MCP server or state database.

**Interface**:
- `run_init(target: str)` — Orchestrates all init steps

**What it installs**:
1. `.claude/skills/se/SKILL.md` — Single `/se` skill dispatcher
2. `AGENTS.md` — Appends/updates a delimited CLASI section
3. `.mcp.json` — Merges MCP server config
4. `.vscode/mcp.json` — VS Code-format MCP config
5. `.claude/settings.local.json` — Adds MCP permission

**Invariants**: All operations are idempotent. Existing content outside
the CLASI markers is preserved.

### Component: MCP Server (`mcp_server.py`)

**Purpose**: Creates and runs the FastMCP server instance that all tools
register against.

**Boundary**: Owns the server singleton and content path resolution.
Does not define any tools itself.

**Interface**:
- `server` — FastMCP singleton (used by process_tools and artifact_tools)
- `content_path(*parts)` — Resolves paths to bundled content
- `run_server()` — Starts stdio transport

**Invariants**: Tool registration happens via import side effects when
`run_server()` imports the tool modules.

### Component: Process Tools (`process_tools.py`)

**Purpose**: Serves bundled SE process content (agents, skills, instructions)
to AI agents via read-only MCP tools.

**Boundary**: Reads from the installed package's content directories. Does
not write to the filesystem or modify project state.

**Interface** (10 MCP tools):
- Content listing: `list_agents`, `list_skills`, `list_instructions`, `list_language_instructions`
- Content retrieval: `get_agent_definition`, `get_skill_definition`, `get_instruction`, `get_language_instruction`
- Composite: `get_se_overview`, `get_activity_guide`, `get_use_case_coverage`, `get_version`

### Component: Artifact Tools (`artifact_tools.py`)

**Purpose**: Manages project artifacts (sprints, tickets, TODOs, overviews)
through read-write MCP tools.

**Boundary**: Reads/writes files in the project's `docs/plans/` directory
and interacts with the state database. Does not serve bundled content.

**Interface** (19 MCP tools):
- Sprint CRUD: `create_sprint`, `insert_sprint`, `list_sprints`, `get_sprint_status`, `close_sprint`
- Ticket CRUD: `create_ticket`, `list_tickets`, `update_ticket_status`, `move_ticket_to_done`
- State management: `get_sprint_phase`, `advance_sprint_phase`, `record_gate_result`, `acquire_execution_lock`, `release_execution_lock`
- Other: `create_overview`, `list_todos`, `move_todo_to_done`, `create_github_issue`, `read_artifact_frontmatter`, `write_artifact_frontmatter`, `tag_version`

### Component: State Database (`state_db.py`)

**Purpose**: Enforces the sprint lifecycle state machine using SQLite.

**Boundary**: Pure data-access layer. No MCP decorators, no filesystem
operations beyond the database file.

**Interface**:
- `PHASES` — Ordered list: `planning-docs` > `architecture-review` > `stakeholder-review` > `ticketing` > `executing` > `closing` > `done`
- `register_sprint`, `get_sprint_state`, `advance_phase`, `record_gate`, `acquire_lock`, `release_lock`, `rename_sprint`

**Invariants**:
- Phase transitions are linear and validated
- Gates must be `passed` before advancing past review phases
- Execution lock is singleton (only one sprint at a time)

### Component: Frontmatter (`frontmatter.py`)

**Purpose**: Reads and writes YAML frontmatter in markdown files.

**Boundary**: Operates on individual files. Understands `---` delimiters
and YAML parsing/serialization.

**Interface**:
- `read_document(path)` → `(dict, str)` — Returns (frontmatter, body)
- `read_frontmatter(path)` → `dict`
- `write_frontmatter(path, data)` — Replaces/creates frontmatter, preserves body

### Component: Templates (`templates.py`)

**Purpose**: Provides string templates for creating sprint, ticket, and
overview markdown files.

**Boundary**: Pure data (template strings) plus the `slugify()` utility.
No I/O.

**Interface**:
- `slugify(title)` → `str`
- Template constants: `SPRINT_TEMPLATE`, `SPRINT_USECASES_TEMPLATE`, `SPRINT_TECHNICAL_PLAN_TEMPLATE`, `TICKET_TEMPLATE`, `OVERVIEW_TEMPLATE`

### Component: Versioning (`versioning.py`)

**Purpose**: Computes date-based versions from git tags and updates version
files.

**Boundary**: Reads git tags via subprocess, writes to pyproject.toml or
package.json.

**Interface**:
- `compute_next_version(major=0)` → `str`
- `detect_version_file(project_root)` → `(Path, str) | None`
- `update_version_file(path, file_type, version)`
- `create_version_tag(version)`

### Component: TODO Split (`todo_split.py`)

**Purpose**: Splits markdown files with multiple level-1 headings into
individual files.

**Boundary**: Operates on the `docs/plans/todo/` directory.

**Interface**:
- `split_todo_files(todo_dir)` → `list[str]`

### Component: Bundled Content (`agents/`, `skills/`, `instructions/`)

**Purpose**: Defines the SE process through markdown files with YAML
frontmatter.

**Boundary**: Static content shipped with the package. Served by
`process_tools.py` via `content_path()`.

**Content inventory**:
- 9 agent definitions (architect, architecture-reviewer, code-reviewer, documentation-expert, product-manager, project-manager, python-expert, requirements-analyst, technical-lead)
- 16 skill definitions (auto-approve, close-sprint, create-technical-plan, create-tickets, elicit-requirements, execute-ticket, generate-documentation, ghtodo, next, plan-sprint, project-initiation, project-status, python-code-review, report, self-reflect, todo)
- 5 instruction files (architectural-quality, coding-standards, git-workflow, software-engineering, testing)
- 1 language instruction (python)

## Data Model

### Sprint Lifecycle (SQLite)

**`sprints` table**:
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | Sprint ID (e.g., "014") |
| slug | TEXT | Filesystem slug |
| phase | TEXT | Current lifecycle phase |
| branch | TEXT | Git branch name |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |

**`sprint_gates` table**:
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| sprint_id | TEXT FK | References sprints.id |
| gate_name | TEXT | `architecture_review` or `stakeholder_approval` |
| result | TEXT | `passed` or `failed` |
| recorded_at | TEXT | ISO timestamp |
| notes | TEXT | Optional review notes |

**`execution_locks` table** (singleton):
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Always 1 (CHECK constraint) |
| sprint_id | TEXT FK | Sprint holding the lock |
| acquired_at | TEXT | ISO timestamp |

### Markdown Artifacts

All markdown artifacts use YAML frontmatter for metadata:

- **Sprint**: `{id, title, status, branch, use-cases}`
- **Ticket**: `{id, title, status, use-cases, depends-on}`
- **Technical Plan**: `{status, from-architecture-version, to-architecture-version}`
- **TODO**: `{status}`

## Security Considerations

- The MCP server runs as a local subprocess (stdio transport) — no network
  exposure.
- The state database is a local SQLite file with no authentication.
- `init_command.py` preserves existing file content and only modifies
  delimited sections.
- GitHub issue creation uses the `GITHUB_TOKEN` environment variable when
  available, falling back to `gh` CLI.

## Design Rationale

### DR-001: MCP Server Architecture

**Decision**: Serve process content and artifact management through an MCP
server rather than file-based skill stubs.

**Context**: The original approach wrote individual skill files to the target
project's `.claude/skills/` directory. This required init to manage many
files and created maintenance burden when skills changed.

**Alternatives**: (1) File-based skill stubs (original approach), (2) Single
monolithic AGENTS.md, (3) MCP server.

**Why MCP**: Skills and agents can be updated by upgrading the package
without re-running init. The MCP protocol is the standard interface for AI
agent tool access. Single `/se` dispatcher stub is the only file init needs
to write.

**Consequences**: Requires MCP server to be running for AI agents to access
process content. Adds `mcp` as a dependency.

### DR-002: SQLite State Machine

**Decision**: Use SQLite for sprint lifecycle state rather than file-based
status tracking.

**Context**: Sprint phases, gates, and execution locks require atomic
operations and constraint enforcement that file-based approaches cannot
guarantee.

**Alternatives**: (1) Frontmatter-only status tracking, (2) JSON state file,
(3) SQLite.

**Why SQLite**: Atomic transactions, constraint enforcement (singleton lock,
unique gates), no additional dependencies (stdlib). The `.clasi.db` file is
gitignored as local state.

**Consequences**: State is local to each clone. Sprint phase must be
re-registered if the database is lost.

### DR-003: Date-Based Versioning

**Decision**: Use `<major>.<YYYYMMDD>.<build>` version format.

**Context**: Traditional semver doesn't suit a process tool where changes
are frequent and the distinction between patch/minor/major is unclear.

**Alternatives**: (1) Semver, (2) CalVer (YYYY.MM.DD), (3) Custom date-based.

**Why this format**: Clear date signal, auto-incrementing build number
avoids conflicts, major version reserved for breaking changes.

## Open Questions

None — this is a retroactive baseline of the existing system.
