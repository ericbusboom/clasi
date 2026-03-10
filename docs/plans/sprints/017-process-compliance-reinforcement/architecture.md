---
version: "017"
status: current
sprint: "017"
description: Architecture update for sprint 017 — inline CLASI into CLAUDE.md, add template reminders
---

# Architecture 017: Process Compliance Reinforcement

This document describes the CLASI (Claude Agent Skills Instructions) system
as it exists today, updated with sprint 017 changes.

## Architecture Overview

CLASI is a Python package that provides a structured software engineering
process for AI-assisted development. The system has three top-level
responsibilities:

1. **Process Content Delivery** — Serving the SE process definitions
   (agents, skills, instructions) to AI agents at runtime.
2. **Project Artifact Management** — Creating and maintaining planning
   artifacts (sprints, tickets, TODOs) in a project's repository.
3. **Project Initialization** — Installing the CLASI SE process into a new
   repository with minimal footprint.

These map to four runtime subsystems:

```
                        ┌─────────────────┐
                        │   CLI Layer     │
                        │ init │ mcp │ ts │
                        └──┬──────┬───────┘
                           │      │
                    Init Cmd    MCP Server
                                  │
                        ┌─────────┴──────────┐
                        │  Process Tools     │  read-only: content
                        ├────────────────────┤
                        │  Artifact Tools    │  read-write: artifacts
                        └─────────┬──────────┘
                                  │
                         Shared Modules
                  (frontmatter, templates, state_db, versioning)
```

Dependencies flow downward: CLI → implementation modules → shared modules.
The MCP Server is the central runtime component for AI agent access.

The system is designed to be **upgradeable without re-running init** — the
SE process content is served from the installed package, so upgrading the
package updates the process for all projects using it.

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

### CLI

**Purpose**: Routes user commands to the appropriate subsystem.

**Boundary**: Accepts command-line arguments and delegates to implementation
modules. Contains no business logic.

**Interactions**: Thin entry point that lazily loads `init_command`,
`mcp_server`, or `todo_split` depending on the invoked subcommand.

**Use cases served**: Project initialization, MCP server startup, TODO file
management.

### Init Command

**Purpose**: Installs the CLASI SE process into a target repository.

**Boundary**: Reads and writes files in the target directory only. Does not
interact with the MCP server or state database.

**Interactions**: Standalone — no runtime dependencies on other CLASI
modules. Writes artifacts into the target project: a skill dispatcher,
CLAUDE.md with the CLASI section inline, and MCP configuration files.

**Key invariant**: All operations are idempotent. Existing content outside
CLASI-delimited sections is preserved.

**Use cases served**: Project initialization.

### MCP Server

**Purpose**: Hosts the FastMCP server instance and resolves paths to
bundled content.

**Boundary**: Owns the server singleton and content path resolution. Does
not define any tools itself — tool registration happens via import side
effects at server startup.

**Interactions**: Imported by Process Tools and Artifact Tools to register
tools against the server singleton.

**Use cases served**: All AI agent interactions.

### Process Tools

**Purpose**: Serves the bundled SE process content (agents, skills,
instructions) to AI agents.

**Boundary**: Read-only access to the installed package's content
directories. Does not write to the filesystem or modify project state.

**Interface**: Exposes 10 MCP tools — content listing by category and
content retrieval by name. One composite tool (`get_activity_guide`)
assembles a curated response from multiple content sources for a given SE
activity.

**Use cases served**: Agent retrieves process guidance, activity workflows,
and SE instructions.

### Artifact Tools

**Purpose**: Manages project planning artifacts — sprints, tickets, TODOs,
and the project overview.

**Boundary**: Reads and writes files under `docs/plans/` in the project
repository. Interacts with the State Database for lifecycle enforcement.

**Interface**: Exposes 19 MCP tools covering sprint and ticket CRUD, sprint
lifecycle state transitions, review gate recording, execution lock
management, and version tagging.

**Interactions**: Depends on Frontmatter, Templates, State Database, and
Versioning.

**Use cases served**: All planning artifact management, sprint lifecycle
management, GitHub issue creation.

### State Database

**Purpose**: Enforces the sprint lifecycle state machine.

**Boundary**: Pure data-access layer backed by a local SQLite file
(`.clasi.db`). No MCP decorators, no filesystem operations beyond the
database file.

**Sprint phases** (in order):
`planning-docs` → `architecture-review` → `stakeholder-review` →
`ticketing` → `executing` → `closing` → `done`

**Interactions**: Used exclusively by Artifact Tools. Never accessed
directly by AI agents.

**Key invariants**:
- Phase transitions are linear — phases cannot be skipped or reversed.
- Review gates must be recorded as `passed` before advancing past review
  phases.
- Only one sprint may hold the execution lock at a time.

**Use cases served**: Sprint lifecycle enforcement, concurrent sprint
prevention.

### Shared Utilities

Three leaf modules with no internal dependencies:

- **Frontmatter** — Reads and writes YAML frontmatter in markdown files.
- **Templates** — Provides content templates for sprint, ticket, and
  overview markdown files. Includes filename slugification.
- **Versioning** — Computes date-based versions from git tags and updates
  `pyproject.toml`.

**Bundled Content** (`agents/`, `skills/`, `instructions/`) — Static
markdown files shipped with the package that define the SE process. Served
by Process Tools via the MCP Server's content path resolver.

## Data Model

### Sprint Lifecycle (SQLite)

Three entities are tracked in the state database:

- **Sprint** — Identified by sprint ID. Records the current lifecycle phase,
  the git branch, and timestamps. Advances through seven phases in sequence.
- **Sprint Gate** — A pass/fail result for a named review gate
  (`architecture_review` or `stakeholder_approval`). Gates must be `passed`
  before the sprint can advance past the corresponding review phase.
- **Execution Lock** — A singleton enforcing that at most one sprint is in
  the `executing` phase at any time. Acquired before entering `executing`;
  released automatically at sprint close.

### Markdown Artifacts

All planning artifacts use YAML frontmatter for machine-readable metadata,
with a markdown body for human and AI consumption:

| Artifact | Key Metadata |
|----------|-------------|
| Sprint | id, title, status, git branch, use case references |
| Ticket | id, title, status, use case references, dependencies |
| Architecture | version, status, sprint, description |
| TODO | status |

## Security Considerations

- The MCP server runs as a local subprocess over stdio — no network
  exposure.
- The state database is a local SQLite file with no authentication.
  It is gitignored.
- `init_command` preserves existing file content outside CLASI-delimited
  sections.
- GitHub issue creation uses `GITHUB_TOKEN` when available, falling back
  to the `gh` CLI.

## Design Rationale

### DR-001: MCP Server Architecture

**Decision**: Serve process content and artifact management through an MCP
server rather than file-based skill stubs.

**Context**: The original approach wrote individual skill files into the
target project's `.claude/skills/` directory. This required `init` to
manage many files and created a maintenance burden whenever skills changed.

**Alternatives**: (1) File-based skill stubs (original), (2) Monolithic
`AGENTS.md`, (3) MCP server.

**Why MCP**: Skills and agents can be updated by upgrading the package
without re-running `init`. The MCP protocol is the standard interface for
AI agent tool access. A single `/se` dispatcher stub is the only file
`init` needs to write.

**Consequences**: Requires the MCP server to be running for AI agents to
access process content. Adds `mcp` as a dependency.

### DR-002: SQLite State Machine

**Decision**: Use SQLite for sprint lifecycle state rather than
frontmatter-based status tracking.

**Context**: Sprint phases, gates, and execution locks require atomic
operations and constraint enforcement that file-based approaches cannot
reliably guarantee.

**Alternatives**: (1) Frontmatter-only status tracking, (2) JSON state
file, (3) SQLite.

**Why SQLite**: Atomic transactions, constraint enforcement (singleton
lock, unique gates), zero additional dependencies (stdlib). Local-only
state is appropriate since sprint state is per-clone.

**Consequences**: State is local to each clone. Sprint phase must be
re-registered if the database is lost.

### DR-003: Date-Based Versioning

**Decision**: Use `<major>.<YYYYMMDD>.<build>` version format.

**Context**: Traditional semver doesn't suit a process tool where the
distinction between patch/minor/major is ambiguous and changes are
frequent.

**Alternatives**: (1) Semver, (2) CalVer (YYYY.MM.DD), (3) Custom
date-based.

**Why this format**: Clear date signal in the version string,
auto-incrementing build number prevents same-day conflicts, major
version reserved for breaking changes.

### DR-004: Inline CLASI into CLAUDE.md

**Decision**: Write the CLASI process block directly into CLAUDE.md
instead of using `@AGENTS.md` indirection.

**Context**: Agents repeatedly ignored process instructions. Two
reflections documented the same root cause: instructions in AGENTS.md
were deprioritized because CLAUDE.md is the primary file agents read
first. The `@AGENTS.md` reference added indirection that reduced the
instructions' priority in the agent's context.

**Alternatives**: (1) Keep `@AGENTS.md` (status quo), (2) Inline into
CLAUDE.md, (3) Use hooks to force tool calls.

**Why inline**: CLAUDE.md is loaded first and directly into agent context.
No indirection means the process instructions have maximum priority.
The `<!-- CLASI:START/END -->` markers already exist for section
replacement, so the same update mechanism works in either file.

**Consequences**: CLAUDE.md becomes larger. Projects that have custom
AGENTS.md content unrelated to CLASI are unaffected (init stops touching
AGENTS.md). The `agents-section.md` init template is kept as the single
source of truth for the CLASI block content — it is used by
`_update_claude_md` to write into CLAUDE.md, just as it was previously
used by `_update_agents_md` to write into AGENTS.md. The `claude-md.md`
template (which contained only `@AGENTS.md`) is deleted.

## Open Questions

None.

## Sprint Changes

Changes planned for sprint 017:

### Changed Components

**Init Command** — Modified to write the CLASI section into CLAUDE.md
instead of AGENTS.md. The `_update_agents_md` function is replaced with
`_update_claude_md` which uses the same marker-based replacement logic
but targets CLAUDE.md. The `_create_claude_md` function is removed (its
role is absorbed by `_update_claude_md`). The `claude-md.md` template
is no longer needed.

**Templates** — All four document templates (`sprint.md`,
`sprint-architecture.md`, `ticket.md`, `sprint-usecases.md`) gain a
single HTML comment line reminding agents to consult the SE process.

### Migration Concerns

Non-breaking. For existing projects that were initialized with the old
version:

- **CLAUDE.md has `@AGENTS.md` but no CLASI markers**: `_update_claude_md`
  appends the CLASI block with markers. The `@AGENTS.md` line remains
  (harmless — it still works). Users can manually remove it.
- **CLAUDE.md has CLASI markers**: Section is replaced in place (same
  behavior as AGENTS.md updates today).
- **No CLAUDE.md**: Created fresh with the CLASI block.
- **Existing AGENTS.md**: Not modified. The old CLASI section in AGENTS.md
  remains but is redundant. No cleanup is performed by init.
