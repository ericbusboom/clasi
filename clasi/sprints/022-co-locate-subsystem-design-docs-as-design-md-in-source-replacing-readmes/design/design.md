---
source_paths:
- /Volumes/Proj/proj/ai-projects/clasi/src/clasi
readme_path: null
---
# CLASI: System Design

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** in-flux

CLASI is a Software Engineering process tool: an MCP server plus CLI plus
installable platform integration (Claude Code / Codex / Copilot) that
drives a structured issue -> sprint -> ticket -> execution -> close
lifecycle for AI-agent-assisted software development. This document is the
entry point into the persistent per-subsystem design-doc set introduced in
sprint 021 (see `clasi.design`'s own doc for the mechanics of this doc set
itself).

## Subsystem Map

All subsystems below live under `src/clasi/` (this project's sole
configured source root — see `.clasi/config.yaml`'s `sources: [src/clasi]`).
Each row links to that subsystem's own design doc for full detail; this
document stays at the "what exists and how does it fit together" level.

| Subsystem | One-line purpose |
|---|---|
| [`clasi.design`](clasi-design.md) (`design/`) | Persistent per-subsystem architecture doc set: naming, storage, validation, sprint overlay lifecycle. |
| [`clasi.platforms`](platforms.md) (`platforms/`) | Install/uninstall CLASI's file-based integration for a host AI coding tool. |
| [`clasi.plugin`](plugin.md) (`plugin/`) | Packaged content root: canonical agents, skills, instructions, rules, hooks. |
| [`clasi.schemas`](schemas.md) (`schemas/`) | Declarative workflow-schema and state-machine YAML definitions and their loaders. |
| [`clasi.state_machine`](state_machine.md) (`state_machine/`) | Generic state-machine evaluation engine (state + fireable-transition computation). |
| [`clasi.status`](status.md) (`status/`) | Assembles agent-scoped project/sprint/ticket status from real state. |
| [`clasi.templates`](templates.md) (`templates/`) | Raw markdown template files for new artifacts and the CLASI host-file section. |
| [`clasi.tools`](tools.md) (`tools/`) | MCP tool functions: the agent-facing surface over artifact and process operations. |

Note on `design/`'s doc filename: its mechanically-derived single-root slug would
otherwise be `design.md`, colliding with this document's own reserved filename
(`clasi.design.paths.SYSTEM_DOC_NAME`). Ticket 010 (`clasi.design.paths`) added a
collision fallback: when a subsystem's slug would equal the system-doc name, the
root-qualified form is used instead, so `design/` resolves to `clasi-design.md`.
This is the only subsystem in this doc set whose slug includes the source-root
name — every other subsystem here uses the plain single-root form (root name
omitted) since none of the others collide.

## `clasi-core`: Loose Top-Level Modules

Not every source file lives inside a subsystem directory. `src/clasi/`
also has a substantial set of top-level `.py` files with no enclosing
subdirectory — these are not picked up by the mechanical subsystem
enumeration (`clasi.design.store._subsystem_dirs` only walks directories
one level under a source root), so they have no dedicated per-file design
doc or README in this doc set (see `clasi-design.md`'s Open Questions for
the gap this leaves). They are described here narratively instead, grouped
by rough responsibility:

**Artifact object model** — `sprint.py` (`Sprint`, OO wrapper around a
sprint directory; `MergeConflictError`), `ticket.py` (`Ticket`, OO wrapper
around a ticket markdown file), `issue.py` (`Issue`, OO wrapper around an
issue markdown file), `artifact.py` (`Artifact`, the shared markdown+
frontmatter base every artifact wrapper builds on), `frontmatter.py`
(YAML-frontmatter read/write utility, delimited `---` blocks, built on
`python-frontmatter`), `project.py` (`Project`, root object for path
resolution, `sources`/`design_docs_opt_in` config, sprint lookup —
everything else in the object model is reached through a `Project`).

**Process/lifecycle infrastructure** — `state_db.py` and
`state_db_class.py` (`StateDB`, SQLite-backed sprint lifecycle state;
`state_db.py` is a thin backward-compatible module-function wrapper over
the real class in `state_db_class.py`), `contracts.py` (agent contract
loading/validation against a contract schema), `versioning.py`
(thin shim over `dotconfig.versioning` for clasi-specific version-file
resolution and tagging), `staleness.py` (detects a stale running CLASI
install by comparing in-process `__version__` and installed-package
metadata against the serving project's source), `dispatch_log.py`
(structured logging of subagent dispatch prompts), `worktree.py`
(parallel-ticket-execution worktree lifecycle API — currently unused;
serial-only execution is mandated by
`schemas/se-process/instructions/execution.md`).

**Agent definitions** — `agent.py` (`Agent` class hierarchy: loads agent
definitions/contracts/dispatch templates from disk; does not execute
dispatches itself — pure content-loading and template rendering).

**CLI and server entry points** — `cli.py` (the `clasi` command-line
entry point: `init`, `uninstall`, `migrate`, `mcp`, `status`, `sprint
close`, `design validate`, and more), `mcp_server.py` (the MCP server
instance and stdio transport that `clasi.tools`'s tool modules register
against), `hook_handlers.py` (Claude Code hook event handlers — thin
dispatchers reading stdin JSON and exiting 0/2 to allow/block).

**Setup/installation commands** — `init_command.py` (`clasi init`:
orchestrates `clasi.platforms` detection/installation plus shared
scaffolding — TODO dirs, log dir, `.mcp.json` — that no single platform
installer owns), `uninstall_command.py` (`clasi uninstall`, the reverse),
`migrate_command.py` (one-shot legacy-location -> configured-location
artifact migration), `plan_to_issue.py` (converts a Claude Code plan file
into a CLASI issue), `templates.py` (loads the `templates/` directory's
`.md` files into string constants; see `templates.md`).

## Global Conventions

Every subsystem doc in this set is allowed to assume, without repeating:

- **Artifacts are markdown files with YAML frontmatter**, read/written
  through `Artifact` (`artifact.py`) and its per-type wrappers (`Sprint`,
  `Ticket`, `Issue`). No subsystem should hand-parse frontmatter with its
  own YAML calls.
- **All git operations use the inline `subprocess.run(["git", ...],
  cwd=..., capture_output=True, text=True)` idiom** already established in
  `clasi.sprint`/`tools/artifact_tools.py` — no subsystem introduces a new
  git abstraction layer of its own (`clasi.design.overlay` follows this
  explicitly).
- **Packaged data files are read via `importlib.resources`**, not
  relative filesystem paths, so they resolve correctly under both editable
  installs and built wheels (`clasi.design.store.subsystem_template`,
  `clasi.schemas.loader`, `clasi.state_machine.loader` all follow this).
- **MCP tools are thin wrappers, not where business logic lives** — see
  `tools.md`'s Constraints. The artifact object model and the
  `clasi.design`/`clasi.state_machine`/`clasi.status` subsystems own the
  actual logic; `clasi.tools` exposes it.
- **This doc set coexists with the frozen initiation docs** already in
  `docs/design/` (`overview.md`, `specification.md`, `state-machines.md`,
  `usecases.md`, `worktree-process.md`) at the same top level, per sprint
  021's Open Question 2 — no filename collision occurs between the two
  sets (confirmed by this bootstrap run; the eight subsystem docs above
  are all named `clasi-<subsystem>.md`).

## Open Questions

See each subsystem doc's own "Open Questions" section for subsystem-local
gaps. The one system-level gap worth flagging here: the `clasi-core`
loose-top-level-module grouping above is this bootstrap run's judgment
call, not a mechanically-enforced subsystem — nothing in `clasi.design`
validates that grouping stays accurate as top-level modules are added,
removed, or renamed. A future sprint could resolve this by extending
`clasi.design.store`'s subsystem enumeration to (optionally) name a
synthetic "core" pseudo-subsystem for loose top-level files, with the
validator treating it the same as a real directory-backed subsystem.
