# CLASI: System Design

**Owner:** clasi maintainers · **Last reviewed:** 2026-08-21 (sprint 032) · **Status:** in-flux

CLASI is a Software Engineering process tool: an MCP server plus CLI plus
installable platform integration (Claude Code — the only platform
adapter in master as of sprint 032; see `platforms/DESIGN.md` for the
Codex/Copilot archival) that drives a structured issue -> sprint ->
ticket -> execution -> close lifecycle for AI-agent-assisted software
development. This document is the
entry point into the persistent per-subsystem design-doc set. As of sprint
022, each subsystem's design doc is **co-located with its code** as
`DESIGN.md` inside the subsystem's own source directory — see
`src/clasi/design/DESIGN.md` for the mechanics (sprint 021 introduced the
doc set as a central `docs/design/` + paired-README model; sprint 022
inverted that into this co-located model).

## Subsystem Map

All subsystems below live under `src/clasi/` (this project's sole
configured source root — see `.clasi/config.yaml`'s `sources: [src/clasi]`).
Each row links to that subsystem's own `DESIGN.md`, co-located in its
source directory; this document stays at the "what exists and how does it
fit together" level.

| Subsystem | One-line purpose |
|---|---|
| [`clasi.design`](../design/DESIGN.md) (`design/`) | Per-subsystem architecture doc co-location: path resolution, storage, validation, sprint overlay lifecycle. |
| [`clasi.platforms`](../platforms/DESIGN.md) (`platforms/`) | Install/uninstall CLASI's file-based integration for a host AI coding tool. |
| [`clasi.plugin`](../plugin/DESIGN.md) (`plugin/`) | Packaged content root: canonical agents, skills, instructions, rules, hooks. |
| [`clasi.schemas`](../schemas/DESIGN.md) (`schemas/`) | Declarative workflow-schema and state-machine YAML definitions and their loaders. |
| [`clasi.state_machine`](../state_machine/DESIGN.md) (`state_machine/`) | Generic state-machine evaluation engine (state + fireable-transition computation). |
| [`clasi.status`](../status/DESIGN.md) (`status/`) | Assembles agent-scoped project/sprint/ticket status from real state. |
| [`clasi.templates`](../templates/DESIGN.md) (`templates/`) | Raw markdown template files for new artifacts and the CLASI host-file section. |
| [`clasi.tools`](../tools/DESIGN.md) (`tools/`) | MCP tool functions: the agent-facing surface over artifact and process operations. |

Note on naming: each subsystem's doc is simply `DESIGN.md` inside its own
directory — there is no filename derivation, slugification, or
collision handling anymore. A subsystem's identity is its path, and its
doc's identity is that same path plus `/DESIGN.md`; two subsystems can
never collide on a doc name the way two `docs/design/<slug>.md` files
could under the old central-directory model. (The old model's
`clasi-design.md` collision-fallback naming rule — needed only because
`design/`'s mechanical slug would otherwise equal the reserved
`design.md` system-doc name — no longer applies to anything: the system
doc and every subsystem doc now live in structurally different places by
construction.)

## `clasi-core`: Loose Top-Level Modules

Not every source file lives inside a subsystem directory. `src/clasi/`
also has a substantial set of top-level `.py` files with no enclosing
subdirectory — these are not picked up by the mechanical subsystem
enumeration (`clasi.design.store._subsystem_dirs` only walks directories
one level under a source root), so they have no dedicated per-file
`DESIGN.md` in this doc set (see `design/DESIGN.md`'s Open Questions for
the gap this leaves — unchanged by sprint 022). They are described here
narratively instead, grouped by rough responsibility:

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
(**as of sprint 032**: the parallel-ticket-execution lifecycle this
module used to expose — `create_worktree`, `create_ticket_branch`,
`validate_worktree`, `merge_ticket_branch`, `check_independence`, and
their parsing/topo-sort helpers — is deleted, not merely unused; it was
never wired into the controller and every real sprint ran serial-only.
What remains is a reconcile/cleanup/audit core —
`reconcile_worktrees`, `cleanup_worktree`, `write_audit_record`,
`read_audit_record`, and their two live parsing helpers — genuinely
called by `close.py`'s worktree-pruning step and the `reconcile_worktrees`
MCP tool to clean up git worktrees left behind by other tooling.
`schemas/se-process/instructions/execution.md` now describes exactly one
execution path, with no `worktree`-flag branch; the sprint `worktree:`
frontmatter field is no longer written for new sprints (existing
sprints that still carry `worktree: false` are unaffected and untouched).
The design intent for the deleted parallel-execution half is preserved,
not erased, in `docs/design/worktree-process.md`, now marked `status:
retired` rather than removed).

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

- **A subsystem's design doc is co-located with its code**, as
  `<subsystem_path>/DESIGN.md` — no separate `README.md`, no frontmatter
  required. Written/read through `clasi.design.store`
  (`write_design_doc`/`read_design_doc`); never hand-constructed.
- **Artifacts other than `DESIGN.md`** (sprints, tickets, issues) are
  markdown files with YAML frontmatter, read/written through `Artifact`
  (`artifact.py`) and its per-type wrappers (`Sprint`, `Ticket`, `Issue`).
  No subsystem should hand-parse frontmatter with its own YAML calls.
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
  `tools/DESIGN.md`'s Constraints. The artifact object model and the
  `clasi.design`/`clasi.state_machine`/`clasi.status` subsystems own the
  actual logic; `clasi.tools` exposes it.
- **This doc set coexists with the frozen project-level docs** in
  `docs/design/` (`overview.md`, `specification.md`, `state-machines.md`,
  `usecases.md`, `worktree-process.md`) — these describe the whole
  project or the SE process itself, not any one subsystem, so they have
  no source directory to co-locate into and stay where they are. This
  document (`design.md`) also stays in `docs/design/`, as the one
  system-level design document with no single owning subsystem directory
  of its own. **As of sprint 032**: `worktree-process.md` carries
  `status: retired` — its specified parallel-execution lifecycle was
  deleted from `worktree.py`, not merely left unimplemented, so the doc
  now records design intent for code that no longer exists rather than
  code "not yet wired in." It stays in this list (still frozen,
  project-level, no source directory to co-locate into) rather than
  being deleted, so the design rationale it captured — the independence-
  check algorithm, the audit-format tradeoffs — remains readable rather
  than only recoverable from git history.

## Sprint-Change Linkage

A sprint that changes a subsystem's `DESIGN.md` records which doc(s) it
touched via a `design_docs:` list (repo-relative `DESIGN.md` paths) in
the sprint's own frontmatter — the default, lightweight linkage
mechanism. For a doc whose location is stable for the sprint's duration,
the sprint may additionally run it through the `design/` overlay
lifecycle (seed / edit / generate-diffs / commit / apply) for
diff-reviewable tracking, exactly as this document itself was updated by
sprint 022. The overlay lifecycle's `apply` step resolves each overlay
file's canonical target from the subsystem path it was seeded from, not
from a flat shared directory — necessary once canonical docs live at N
different per-subsystem locations instead of one shared `docs/design/`
directory.

## Open Questions

See each subsystem doc's own "Open Questions" section for subsystem-local
gaps. The one system-level gap worth flagging here: the `clasi-core`
loose-top-level-module grouping above is a judgment call, not a
mechanically-enforced subsystem — nothing in `clasi.design` validates
that grouping stays accurate as top-level modules are added, removed, or
renamed. A future sprint could resolve this by extending
`clasi.design.store`'s subsystem enumeration to (optionally) name a
synthetic "core" pseudo-subsystem for loose top-level files, with the
validator treating it the same as a real directory-backed subsystem.
