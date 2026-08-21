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
  `process_tools`) exposed by the server. **As of sprint 030**: a new
  `tools/_common.py` holds the `@clasi_tool` decorator (uniform
  `{"ok": bool, ...}` result envelope, owned `"NONE"`-sentinel stripping,
  per-call `mcp-calls.jsonl` tracing) and `resolve_artifact_path`
  (relocated from `artifact_tools.py`, already root-anchored since
  sprint 029) — see `tools-DESIGN.md`'s sprint-030 entry.

**Top-level modules (the connective tissue):**

- `mcp_server.py` / `cli.py` — the two entry surfaces (MCP server and
  `clasi` CLI) over the same underlying operations. As of sprint 028,
  `_logged_call_tool` additionally times each call (`time.monotonic()`)
  and appends one JSON line per call to `.clasi/log/mcp-calls.jsonl`
  (`ts, agent, tool, args, ok, ms, result_len`), alongside its existing
  human-readable `mcp-server.log` line, which now also carries the
  duration (`OK name (NNNms)`) — the machine-readable half of the E2E
  instrumentation plan (`05-e2e-test-infra.md`). **As of sprint 030**:
  both of `mcp_server.py`'s `run()`-time monkey-patches over private
  `mcp`-library internals (`_tool_manager.call_tool`, which owned the
  `"NONE"`-sentinel strip and the call trace above) are removed — that
  behavior now lives in `tools/_common.py`'s `@clasi_tool` decorator,
  applied per-function at import time instead of patched onto the
  library's tool manager at server startup. This is the change that lets
  `mcp-calls.jsonl` tracing and sentinel stripping survive an `mcp` 2.x
  upgrade (2.x deletes `mcp.server.fastmcp` and the private attributes
  the old patches read) — `@clasi_tool` depends on nothing beyond the
  public `@server.tool()` decorator it wraps. The separate raw-RPC
  diagnostic tap (`JSONRPCMessage.model_validate_json`, installed for a
  now-closed investigation) is unchanged by this sprint — flagged as
  Phase 4 debug-scaffolding cleanup, not touched here.
- `project.py` — the root object; all path resolution, `sources`/
  `design_docs` config, and artifact-directory discovery flow through it.
- `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
  the artifact model and its markdown+frontmatter substrate. **As of
  sprint 029**: `frontmatter.py`'s body split is line-anchored (no longer
  a bare `content.find("---", 3)`, which could mis-slice on a `---`
  inside a frontmatter value), and `_write_document` writes to a temp
  file and `os.replace`s it over the target instead of truncating in
  place with `write_text` — a crash mid-write leaves the prior valid
  content intact rather than corrupting the file into one
  `list_sprints` would then silently drop. `yaml.dump` becomes
  `yaml.safe_dump`. `sprint.py`'s git subprocess calls now route through
  the new `gitutil.run_git(args, cwd=project.root)` instead of bare,
  cwd-less `subprocess.run(["git", ...])`. **As of sprint 030**:
  `sprint.py` gains `Sprint.set_sprint_stage(phase)`, the single writer
  for a sprint's recorded stage — it writes the state-DB `phase` column
  and the sprint's frontmatter `status:` field together (delegating the
  DB half to `StateDB.set_phase`/`force_close`, see this doc's
  `state_db_class.py` entry below), raising loudly if either half fails,
  rather than leaving each transition to write frontmatter and advance
  DB phase as two independent, non-transactional steps (the exact shape
  of the drift finding 10 of the reliability review named). `detail_promote`,
  `advance_phase`, and `archive` all route through it instead of calling
  `sprint_doc.update_frontmatter` directly; `archive()` now writes
  `status: "done"` (the state-DB vocabulary's own terminal string)
  instead of `status: "closed"` (sprint 019's choice, reversed here — see
  sprint 030's `sprint.md` Design Rationale: `"closed"` and `"done"` were
  always two spellings of the one fact "this sprint is finished," and
  this sprint collapses every sprint-stage record to the state-DB phase
  vocabulary alone). No historical archive file is rewritten — a sprint
  already under `sprints/done/` is exempt from stage consistency-checking
  by directory location alone, regardless of which legacy `status:`
  string it carries (10 of this repo's own 29 archived sprints carry
  `"closed"`, 19 carry `"done"`; both are tolerated on read forever).
  `ticket.py`'s `move_to_done()` is retained as the primitive a `"done"`
  status transition uses, but the MCP-facing `update_ticket_status(path,
  "done")` now performs the frontmatter write and the `tickets/done/`
  move in one call, and `move_ticket_to_done` becomes a thin alias over
  that same combined path — see `tools-DESIGN.md`'s sprint-030 entry.
- `state_db.py` / `state_db_class.py` — the SQLite state store backing
  execution locks, gate results, and OOP records. As of sprint 028,
  `_SCHEMA` also carries a `phase_transitions` table (`sprint_id,
  from_phase, to_phase, at`), written by `advance_phase` in the same
  transaction as the `sprints.phase` update it accompanies;
  `get_sprint_phase` (`StateDB.get_sprint_state`, see `tools-DESIGN.md`)
  exposes the resulting history as a timestamped list. Additive migration — existing
  databases gain the table with no manual step, and there is no backfill
  for phase transitions recorded before this sprint. **As of sprint
  029**: read methods no longer call `init()` implicitly — `init()` runs
  at most once per `StateDB` instance and only on a write path — so a
  read against a path with no existing database returns that method's
  documented "absent"/default value instead of creating a phantom
  schema'd file there (previously the root cause of a wrong-cwd hook
  silently seeding a stray `.clasi.db` with the OOP flag off, the lock
  invisible, and the agent tier unset). `_connect`'s busy timeout also
  drops to `timeout=1`, so contention under parallel agents raises a
  fast, catchable exception instead of hanging toward the harness's own
  5-second `PreToolUse` timeout (which, if reached, kills the process
  before any CLASI code — including the fail-closed boundary described
  below — can run; a residual gap this change narrows but does not
  close, see that sprint's Architecture Migration Concerns). **As of
  sprint 030**: a new `StateDB.force_close(sprint_id)` sets `sprints.phase`
  to `"done"` and deletes the held `execution_locks` row in one
  transaction, replacing the `except (ValueError, Exception): pass`-
  wrapped advance-and-release sequence `close_sprint` used to run —
  a failure here is now surfaced to the caller, never swallowed. It is
  idempotent (a call against a sprint already at phase `"done"` is a
  cheap no-op), which is what lets a retried `close_sprint` call it
  safely without re-deriving "did the last attempt already get this
  far." No schema change: `force_close` writes the same `sprints` and
  `execution_locks` tables every other phase/lock write already used.
  **As of sprint 031**: a new `StateDB.advance_to(sprint_id,
  target_phase, required_gate=None)` generalizes `force_close`'s own
  shape (jump directly to a target phase, checking one named
  precondition, transactional, idempotent if already there) to two
  non-terminal transitions: `create_ticket`'s first call jumps a
  sprint's phase to `"ticketing"` after checking the `architecture_review`
  gate directly (not a phase-index comparison), and
  `acquire_execution_lock` jumps it to `"executing"` after checking
  `stakeholder_approval`, granting the lock only if that gate has
  recorded `passed`/`skipped`. `_GATE_REQUIREMENTS` loses its
  `"stakeholder-review"` entry — that phase value is deleted from
  `se-process/schema.yaml` (see `schemas-DESIGN.md`'s sprint-031 entry)
  since `stakeholder_approval` now gates the lock instead of the
  ticketing transition. `advance_to` raises a named, actionable error
  (not a raw `ValueError` from `list.index()`) if a sprint's current
  phase is absent from the computed phases list — the stranded-legacy-
  value case for a downstream project that might have a sprint parked
  at the now-deleted phase. `force_close` itself is unchanged;
  `advance_to` generalizes its pattern rather than refactoring
  `force_close` to call it — the two methods keep deliberately
  different contracts (unconditional terminal jump vs. gate-checked
  non-terminal jump).
- `gitutil.py` (sprint 029) — one `run_git(args, cwd)` helper
  wrapping `subprocess.run(["git", *args], cwd=..., capture_output=True,
  text=True)`, promoted from `design/overlay.py`'s previously-local
  `_run_git` (deleted in favor of this shared version). `sprint.py`,
  `tools/artifact_tools.py`, `design/overlay.py`, and
  `versioning.compute_next_version`/`_get_existing_tags` (the latter two
  gaining an explicit `project_root` parameter in place of implicit cwd)
  all route their git subprocess calls through it, always passing
  `cwd=project.root` — closing the class of bug where a git call silently
  targets whatever directory the MCP server process happens to be in
  (`02-mcp-tools.md` F3). **As of sprint 030**: this module is deliberately
  *not* absorbed into the new `tools/_common.py` (see below) even though
  the review's own decomposition proposal grouped a future `run_git` there
  alongside the uniform `@clasi_tool` envelope — `sprint.py` and
  `design/overlay.py` are core modules outside the `tools/` layer and both
  depend on `run_git` directly; moving it into `tools/_common.py` would
  make two core modules import from the tools layer, inverting this
  package's tools-wraps-core dependency direction. `gitutil.py` stays a
  shared leaf module both layers import, unchanged in content by this
  sprint.
- `close.py` (new, sprint 030) — `SprintCloser`, the resumable
  close-sprint orchestration extracted out of `tools/artifact_tools.py`'s
  former ~950-line `_close_sprint_full`. Each lifecycle step
  (precondition check — now read-only; tests; archive; DB update via
  `StateDB.force_close`; design-overlay apply; version bump; git merge;
  tag push; branch delete; worktree prune) owns its own idempotency
  check against ground truth (does the computed version's git tag
  already exist; is the DB phase already `"done"`; is the sprint
  directory already under `sprints/done/`) rather than consulting a
  separately-maintained "completed steps" ledger — so a retry after a
  partial failure skips real work without depending on a second
  bookkeeping mechanism staying in sync with reality. Self-repair
  (ticket/issue relocation, DB phase catch-up) now runs only *after* the
  test gate passes, each repair recorded in `StateDB.recovery_state` as
  it happens — previously this ran unconditionally in Step 1, before
  tests, with no rollback on a later failure. The version-bump step
  checks whether the computed tag already exists in git before bumping
  again (closing the double-tag-on-retry defect); the tag-push step
  pushes only the sprint's own tag by name, never `git push --tags`.
  `tools/artifact_tools.py`'s `close_sprint` tool function becomes a thin
  wrapper delegating to `close.SprintCloser`, the same "extract a
  cohesive piece, leave a thin re-export at the call site" pattern
  `skill_resolve.py` (below) already established for this package.
- `skill_resolve.py` (new, sprint 029) — a single pure function,
  `resolve_skill_body`, resolving a skill's `Load from:` directive.
  Moved out of `tools/process_tools.py` (which still imports it back for
  its own `get_skill_definition` tool) specifically so
  `platforms/claude.py`'s install path — previously importing it from
  `process_tools.py`, which imports `clasi.mcp_server` at module level —
  no longer transitively depends on FastMCP. This was the concrete crash
  path behind the mcp-2.0 install failure: an unbounded `mcp>=1.0`
  dependency resolving to `mcp==2.0.0` (which deleted
  `mcp.server.fastmcp`) meant every `clasi init` crashed on this single
  indirect import, before any of the rest of this package ever ran.
  `pyproject.toml` also now caps `mcp` at `>=1.0,<2.0` — the actual mcp
  2.x migration is tracked separately and depends on Phase 3/4's
  `@clasi_tool` decorator landing first (`02-mcp-tools.md` F5: the
  NONE-sentinel stripping and call-logging taps three private FastMCP
  internals that mcp 2.x removes).
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
  unchanged; only what gets logged about each outcome changes. **As of
  sprint 029**: `get_project()` gains upward `.clasi/` discovery — it
  calls the already-proven `_find_project_root` walk (previously used
  only by `_oop_active()` and `cli.py`'s `oop` command) instead of
  `Project(Path.cwd())` directly, falling back to cwd unchanged when no
  `.clasi/` is found in any ancestor; every handler inherits the fix with
  no call-site change. A new frozen `HookPayload` dataclass
  (`from_stdin`) is built once in `handle_hook` and consumed by all six
  handlers in place of six hand-rolled extractions, validated by a new
  parametrized replay test reading sprint 028's captured
  `.clasi/log/denied/*.json` corpus. `handle_hook`'s try/except around
  the role-guard/mcp-guard dispatch — added by sprint 028's ticket 005 as
  catch/log/**re-raise-unchanged**, deliberately not fail-closed at the
  time (see that sprint's ticket 005 for the explicit scope boundary) —
  now calls `_exit_hook(event, payload, 2, "guard-crash")` instead of
  re-raising: a guard crash is a logged, blocking exit, never a silent
  allow. `_oop_active()`'s unconditional file-first bypass is unaffected
  — it still runs inside each guard's own body, before this boundary can
  matter, exactly as before. Role-guard's payload ingress gains an
  `isinstance(tool_input, dict)` check; mcp-guard's tier check becomes an
  allowlist (`in ("1", "2")`) instead of `not in ("", "0")`; malformed,
  non-empty stdin logs a `bad-payload` token. This conversion is
  deliberately the *last* change to land in sprint 029's own execution
  order, not the first, despite being first in the issue that named it —
  see that sprint's Architecture Design Rationale for why (this repo
  dogfoods its own enforcement, and arming the boundary before reducing
  the guard chain's own crash surface would risk blocking the very work
  needed to finish reducing it). `staleness.py` gains a third signal:
  `clasi/__init__.py` records `_IMPORT_TIME` at package import, and
  `check_staleness` flags `stale: true` when any source `.py` file under
  `Path(clasi.__file__).parent` has a newer mtime — closing the
  same-version-drift gap the first two signals (version string, install
  path) cannot see for a long-lived editable-install MCP server.
  **As of sprint 031**: the tier-0/tier-1 write policy in
  `handle_role_guard` is relaxed to the stakeholder's 2026-08-19
  decision — the tier-0 `blk-sprint` block is deleted (`.clasi/sprints/**`
  becomes `ALLOW` for tier 0, matching the pre-existing tier-1 allow) and
  the docstring allow/block matrix is updated to match; `create_ticket`
  remains the only tier-0-blocked MCP artifact-creation tool (see
  `plugin-DESIGN.md`'s sprint-031 entry for the matching `hooks.json`
  matcher change). `handle_subagent_start` additionally injects a 3-4
  line write-scope summary (allowed prefixes, blocked prefixes, the OOP
  recovery route) for tier 1/2 dispatches, folded into the existing
  tier-0 status block too — an agent can now learn its write scope
  without triggering a block first. Verified, not re-fixed: the
  outside-root allow (any absolute path role-guard cannot make
  root-relative, including `~/.claude/plans/**`) already covers every
  tier, landed by sprints 024 and 026 — this sprint adds the real-
  dispatch/real-payload regression tests that behavior never had. The
  DB-backed `get_active_tier` fallback (`019-003`) is confirmed
  load-bearing by live evidence gathered during this sprint's own
  planning (`tier=1(db)` resolved correctly for the sprint-planner
  dispatches that created sprints 031 and 032 themselves) — not a
  defect, a missing regression test.
- `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
  `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
  `dispatch_log.py` — installation, migration, versioning, worktree, and
  agent-dispatch machinery. **As of sprint 031**: `init_command.py`
  detects (or is told) the project's source/test directories and writes
  `protected_paths:` to `config.yaml` on a fresh `clasi init` — a
  project that declines or upgrades without re-running init keeps the
  pre-existing block-by-default fallback role-guard already applies when
  `protected_paths` is unconfigured.

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
- **No component trusts the process's own working directory for root
  resolution; every path resolves against a discovered or explicitly
  passed root instead (sprint 029):** `get_project()` walks upward for
  `.clasi/` rather than assuming cwd is the project root; every git
  subprocess in the tools layer, `sprint.py`, and `design/overlay.py`
  passes `cwd=project.root` via the shared `gitutil.run_git`; relative
  artifact paths resolve against `project.root`, not the server
  process's cwd. This generalizes the existing cwd-independence pattern
  `_oop_active()` established narrowly (checking `.clasi/oop` from any
  subdirectory) to every root-dependent operation in the package.
- **A guard's default on an unresolved or unanticipated input is the
  safe, loud action, never a silent success (sprint 029):** a guard
  handler that raises exits 2 with a logged `guard-crash` line instead of
  falling through to the harness's own non-2-exit-is-allow default; a
  malformed or unrecognized payload shape denies with a distinct reason
  rather than crash-allowing. `.clasi/oop`'s unconditional, file-checked-
  first bypass remains the operator's escape hatch when this produces an
  unwanted block — this invariant does not remove that escape hatch, it
  only removes the *silent* failure mode.
- **A sprint's lifecycle stage has exactly one recorded vocabulary and
  one writer (sprint 030):** the state-DB `sprints.phase` column
  (`roadmap` → `done`) is authoritative; `sprint.md`'s frontmatter
  `status:` field is a mirror written by `Sprint.set_sprint_stage()` in
  the same call, never independently. The computed sprint-machine
  vocabulary (`open`/`planned`/`pre-flight`/…, see
  `state_machine-DESIGN.md`) is a separate, intentionally different
  concept — "what can happen next," not "what stage is recorded" — and
  is no longer compared against frontmatter for drift; conflating the two
  is exactly the category error `detect_inconsistencies` made before this
  sprint (see `status-DESIGN.md`'s sprint-030 entry). A sprint physically
  under `sprints/done/` is exempt from stage consistency-checking
  regardless of which status string it carries, which is why none of the
  29 sprints archived before this sprint needed editing.
- **Every state-machine predicate and invariant is satisfiable by
  something the shipped toolchain actually writes (sprint 030):** a
  predicate referencing a DB phase string, gate name, or frontmatter flag
  nothing writes is a defect, not a documentation gap — `clasi status`
  must report against the process that runs, not an aspirational one. See
  `state_machine-DESIGN.md`'s sprint-030 entry for the specific
  predicates removed under this rule.
- **A structural phase transition arrives as a side effect of the tool
  call that earns it, never a separate agent-driven
  `advance_sprint_phase` call (sprint 031):** `roadmap` (`create_sprint`),
  `planning-docs` (`detail_sprint`), `ticketing` (`create_ticket`'s first
  call), `executing` (`acquire_execution_lock`), and `done`
  (`close_sprint`, unchanged since sprint 030) each arrive via the tool
  call whose success implies the transition, checked against the one
  gate (if any) that transition requires — `StateDB.advance_to()`
  generalizes `force_close`'s pre-existing "jump + own precondition"
  shape to the two transitions (`ticketing`, `executing`) that gained
  this behavior in sprint 031. `advance_sprint_phase` (the MCP tool)
  remains available for manual recovery; no shipped instruction routes
  the standard flow through it. `record_gate_result` for
  `stakeholder_approval` stays an explicit, agent-driven call
  (deliberately — it is how a human's actual approval gets recorded as a
  fact independent of whoever consumes it, one of the two safety
  properties this campaign does not relax) — see the sprint 031
  `sprint.md` Design Rationale for the full argument against folding it
  into `acquire_execution_lock` as an implicit default.

## 4. See Also

- `docs/design/design.md` — the system-level design document (the index
  above this package).
- Each subsystem's own `DESIGN.md` for depth on that subsystem.
