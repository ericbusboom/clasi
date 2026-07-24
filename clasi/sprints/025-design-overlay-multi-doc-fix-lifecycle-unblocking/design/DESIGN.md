# clasi (source root)

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-22 · **Status:** stable

---

## 1. Purpose

`src/clasi` is the declared source root of the CLASI package — the whole
implementation of the CLASI software-engineering process: its MCP server,
CLI, artifact model (sprints, tickets, issues, design docs), state
machines, status computation, and the agent/skill/rule content that ships
to installed projects. This document is the **root-level overview** of that
tree: it orients a reader across the package's subsystems and top-level
modules and records the conventions every subsystem doc below it may
assume. Each immediate subdirectory carries its own `DESIGN.md` describing
that subsystem in depth; this doc is the map, not the territory.

## 2. Orientation

The package divides into subsystem directories (each with its own
`DESIGN.md`) and a set of top-level modules that wire them together.

**Subsystems (one level down, each self-documented):**

- `design/` — the persistent per-subsystem design-doc set: path
  resolution, storage, structural validation, and the sprint-time overlay
  lifecycle. (This doc's own rules — required root + subsystem `DESIGN.md`
  files — are enforced by `design/validator.py`.)
- `schemas/` — the SE-process definition data (instructions, activity
  guides, language instructions) and its loader.
- `state_machine/` — the project/sprint lifecycle state machines and their
  transition guards.
- `status/` — computes and renders the project-status block surfaced to
  the team-lead and injected by hooks.
- `platforms/` — platform installers (Claude, Codex, Copilot, Cursor) that
  materialize agent/skill/rule content into a target project.
- `plugin/` — the packaged agent definitions, skills, and path-scoped rules
  shipped to installed projects.
- `templates/` — packaged template resources served to skills/tools.
- `tools/` — the MCP tool implementations (`artifact_tools`, `design_tools`,
  `process_tools`) exposed by the server.

**Top-level modules (the connective tissue):**

- `mcp_server.py` / `cli.py` — the two entry surfaces (MCP server and
  `clasi` CLI) over the same underlying operations.
- `project.py` — the root object; all path resolution, `sources`/
  `design_docs` config, and artifact-directory discovery flow through it.
- `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
  the artifact model and its markdown+frontmatter substrate.
- `state_db.py` / `state_db_class.py` — the SQLite state store backing
  execution locks, gate results, and OOP records.
- `hook_handlers.py`, `plan_to_issue.py`, `staleness.py` — hook-time
  behavior (role/mcp guards, plan-mode capture, running-build drift).
- `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
  `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
  `dispatch_log.py` — installation, migration, versioning, worktree, and
  agent-dispatch machinery.

## 3. Constraints and Invariants

- **`project.py` is the single source of path truth:** every subsystem
  resolves artifact locations through `Project` properties, never by
  hardcoding `docs/`, `clasi/`, or `.clasi/` paths. This is what lets a
  project remap any artifact directory via `.clasi/config.yaml`'s `paths:`
  map without touching code.
- **The MCP server and CLI must stay behavior-equivalent:** both surfaces
  dispatch to the same operation functions (see `tools/` and the command
  modules). A fix applied on one path but not the other is a defect —
  tests assert parity for the operations that have both.
- **Process artifacts are written only through the sanctioned tools:**
  sprints/tickets/issues/design docs are created and moved via MCP tools
  and the artifact model, never hand-constructed — the path-scoped rules
  shipped in `plugin/` and enforced by `hook_handlers.py` depend on this.
- **Every declared source root and every subsystem below it carries a
  `DESIGN.md`:** required by `design/validator.py`. This root doc satisfies
  that requirement for `src/clasi` itself; each subsystem directory
  satisfies it for its own tree. A `DESIGN.md` nested deeper than one level
  below a root is still flagged as orphaned.
- **Guards fail closed on process violations but must not block
  out-of-root work:** `hook_handlers.py`'s role/mcp guards govern writes to
  this repo's own source and process artifacts; paths outside the project
  root are not CLASI's to police.

## 4. See Also

- `docs/design/design.md` — the system-level design document (the index
  above this package).
- Each subsystem's own `DESIGN.md` for depth on that subsystem.
