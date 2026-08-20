# clasi (source root)

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-24 · **Status:** stable

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
  `clasi` CLI) over the same underlying operations. As of sprint 028,
  `_logged_call_tool` additionally times each call (`time.monotonic()`)
  and appends one JSON line per call to `.clasi/log/mcp-calls.jsonl`
  (`ts, agent, tool, args, ok, ms, result_len`), alongside its existing
  human-readable `mcp-server.log` line, which now also carries the
  duration (`OK name (NNNms)`) — the machine-readable half of the E2E
  instrumentation plan (`05-e2e-test-infra.md`).
- `project.py` — the root object; all path resolution, `sources`/
  `design_docs` config, and artifact-directory discovery flow through it.
- `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
  the artifact model and its markdown+frontmatter substrate.
- `state_db.py` / `state_db_class.py` — the SQLite state store backing
  execution locks, gate results, and OOP records. As of sprint 028,
  `_SCHEMA` also carries a `phase_transitions` table (`sprint_id,
  from_phase, to_phase, at`), written by `advance_phase` in the same
  transaction as the `sprints.phase` update it accompanies;
  `get_sprint_phase` (`StateDB.get_sprint_state`, see `tools-DESIGN.md`)
  exposes the resulting history as a timestamped list. Additive migration — existing
  databases gain the table with no manual step, and there is no backfill
  for phase transitions recorded before this sprint.
- `hook_handlers.py`, `plan_to_issue.py`, `staleness.py` — hook-time
  behavior (role/mcp guards, plan-mode capture, running-build drift).
  As of sprint 026, `handle_role_guard` resolves `Project`, its parsed
  config, and its sqlite connection once per hook invocation and reuses
  them across every check inside that call, rather than reconstructing
  each per check; its ticket-state gate applies to tier-2 writes only
  (issues/reflections directories are exempt for every tier); its
  recovery-state lookup matches directory-prefix entries in addition to
  exact paths; and its tier-1 branch consults the same artifact-dir
  allow list tier 0 does. `__init__.py` resolves `__version__` lazily
  via module `__getattr__` instead of an eager `importlib.metadata`
  call at import time — see this doc set's `status-DESIGN.md`/
  `state_machine-DESIGN.md` overlay entries for the matching per-prompt
  status-path caching, and `plugin-DESIGN.md` for the corresponding
  `hooks.json` cleanup. As of sprint 027, `handle_hook`'s dispatcher
  (`cli.py`'s `hook` command, routed to `hook_handlers.handle_hook`)
  adds a small **retired-event allowlist** alongside its existing
  live-event routing table: a name in the allowlist (`commit-check`,
  `task-created`, `task-completed`, and documented alias forms — sprint
  026's own removed registrations) no-ops with exit 0, a single stderr
  deprecation line, and a `hooks.log` `retired-event` entry, instead of
  the hard `exit 1` every unrecognized name previously got. A name in
  neither the routing table nor the allowlist still hard-errors,
  unchanged — this is a narrow bridge for registrations that upgrade on
  a different schedule than the CLI (a session's hooks are snapshotted
  at start; a consumer project's `.claude/settings.json` only updates
  on its own `clasi init` re-run), not a general tolerance for unknown
  event names. `cli.py`'s `hook` command argument, previously a
  `click.Choice` enumerating only live event names (which rejected a
  retired name before it ever reached `handle_hook`), widens
  accordingly so a retired name can reach the dispatcher's allowlist
  check at all. Separately, `clasi hook`'s process-startup import cost
  (the `click` CLI import chain `cli.py` pays on every invocation) is a
  contributing factor in the residual status-inject latency gap — see
  `status-DESIGN.md`'s sprint-027 entry for the git-subprocess-spawn
  half of that same latency work. As of sprint 028, `_exit_hook`/`_log_
  hook_event` additionally accept a per-invocation `decisions:
  list[str]` that handlers append to (e.g. `tier=2(db)`, `gate=ticket-
  state:skipped(db-error)`, `missing=[file_path]`), emitted as trailing
  tokens on the existing `hooks.log` line; every denial (`exit_code ==
  2`, or a guard-internal exception) additionally dumps the full hook
  payload to `.clasi/log/denied/<ts>-<hook>.json` (the directory
  auto-gitignores via the existing `_ensure_log_gitignore` mechanism);
  and `handle_plan_to_issue`/`handle_codex_plan_to_issue` are now routed
  through `_exit_hook` so plan-mode events appear in `hooks.log` at all
  (previously zero such events existed across 3,021 logged hook events).
  No guard decision logic changes — every existing allow/deny outcome is
  unchanged; only what gets logged about each outcome changes.
- `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
  `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
  `dispatch_log.py` — installation, migration, versioning, worktree, and
  agent-dispatch machinery.

## 3. Constraints and Invariants

- **`project.py` is the single source of path truth:** every subsystem
  resolves artifact locations through `Project` properties, never by
  hardcoding `docs/`, `clasi/`, or `.clasi/` paths. This is what lets a
  project remap any artifact directory via `.clasi/config.yaml`'s `paths:`
  map without touching code. Sprint 025's design-overlay seed-path fix is
  an instance of this invariant being repaired rather than newly
  introduced: `tools/artifact_tools.py`'s `seed_sprint_design_overlay`
  previously resolved every `doc_names` entry relative to
  `project.design_dir`, which silently mis-resolved a co-located
  subsystem's canonical source path (e.g. `src/clasi/tools/DESIGN.md`);
  it now resolves a path-separator-bearing entry relative to
  `project.root` instead, matching how every other co-located path in the
  package is resolved.
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
- **A hook invocation is a single process lifetime; expensive per-call
  work is memoized within it, not across invocations:** `handle_role_guard`
  and the status-inject path (sprint 026) cache `Project`/config/sqlite
  and git-subprocess results for the duration of one hook process, then
  discard the cache — there is no cross-invocation cache to invalidate,
  which keeps the caching addition free of staleness concerns.

## 4. See Also

- `docs/design/design.md` — the system-level design document (the index
  above this package).
- Each subsystem's own `DESIGN.md` for depth on that subsystem.
