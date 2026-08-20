---
source_file: DESIGN.md
source_hash: 963745f5f773700d906423a1889f052893ce5f99e7590e94a78d84f669b7211d
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -54,7 +54,17 @@
 - `project.py` — the root object; all path resolution, `sources`/
   `design_docs` config, and artifact-directory discovery flow through it.
 - `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
-  the artifact model and its markdown+frontmatter substrate.
+  the artifact model and its markdown+frontmatter substrate. **As of
+  sprint 029**: `frontmatter.py`'s body split is line-anchored (no longer
+  a bare `content.find("---", 3)`, which could mis-slice on a `---`
+  inside a frontmatter value), and `_write_document` writes to a temp
+  file and `os.replace`s it over the target instead of truncating in
+  place with `write_text` — a crash mid-write leaves the prior valid
+  content intact rather than corrupting the file into one
+  `list_sprints` would then silently drop. `yaml.dump` becomes
+  `yaml.safe_dump`. `sprint.py`'s git subprocess calls now route through
+  the new `gitutil.run_git(args, cwd=project.root)` instead of bare,
+  cwd-less `subprocess.run(["git", ...])`.
 - `state_db.py` / `state_db_class.py` — the SQLite state store backing
   execution locks, gate results, and OOP records. As of sprint 028,
   `_SCHEMA` also carries a `phase_transitions` table (`sprint_id,
@@ -63,7 +73,51 @@
   `get_sprint_phase` (`StateDB.get_sprint_state`, see `tools-DESIGN.md`)
   exposes the resulting history as a timestamped list. Additive migration — existing
   databases gain the table with no manual step, and there is no backfill
-  for phase transitions recorded before this sprint.
+  for phase transitions recorded before this sprint. **As of sprint
+  029**: read methods no longer call `init()` implicitly — `init()` runs
+  at most once per `StateDB` instance and only on a write path — so a
+  read against a path with no existing database returns that method's
+  documented "absent"/default value instead of creating a phantom
+  schema'd file there (previously the root cause of a wrong-cwd hook
+  silently seeding a stray `.clasi.db` with the OOP flag off, the lock
+  invisible, and the agent tier unset). `_connect`'s busy timeout also
+  drops to `timeout=1`, so contention under parallel agents raises a
+  fast, catchable exception instead of hanging toward the harness's own
+  5-second `PreToolUse` timeout (which, if reached, kills the process
+  before any CLASI code — including the fail-closed boundary described
+  below — can run; a residual gap this change narrows but does not
+  close, see that sprint's Architecture Migration Concerns).
+- `gitutil.py` (new, sprint 029) — one `run_git(args, cwd)` helper
+  wrapping `subprocess.run(["git", *args], cwd=..., capture_output=True,
+  text=True)`, promoted from `design/overlay.py`'s previously-local
+  `_run_git` (deleted in favor of this shared version). `sprint.py`,
+  `tools/artifact_tools.py`, `design/overlay.py`, and
+  `versioning.compute_next_version`/`_get_existing_tags` (the latter two
+  gaining an explicit `project_root` parameter in place of implicit cwd)
+  all route their git subprocess calls through it, always passing
+  `cwd=project.root` — closing the class of bug where a git call silently
+  targets whatever directory the MCP server process happens to be in
+  (`02-mcp-tools.md` F3). Scoped deliberately small: the review's own
+  decomposition proposal groups a future `run_git` into a larger
+  `tools/_common.py` alongside the not-yet-designed uniform
+  `@clasi_tool` envelope — that is Phase 3/4 work (`uniform-mcp-tool-
+  envelope.md`), and this module does not preempt it.
+- `skill_resolve.py` (new, sprint 029) — a single pure function,
+  `resolve_skill_body`, resolving a skill's `Load from:` directive.
+  Moved out of `tools/process_tools.py` (which still imports it back for
+  its own `get_skill_definition` tool) specifically so
+  `platforms/claude.py`'s install path — previously importing it from
+  `process_tools.py`, which imports `clasi.mcp_server` at module level —
+  no longer transitively depends on FastMCP. This was the concrete crash
+  path behind the mcp-2.0 install failure: an unbounded `mcp>=1.0`
+  dependency resolving to `mcp==2.0.0` (which deleted
+  `mcp.server.fastmcp`) meant every `clasi init` crashed on this single
+  indirect import, before any of the rest of this package ever ran.
+  `pyproject.toml` also now caps `mcp` at `>=1.0,<2.0` — the actual mcp
+  2.x migration is tracked separately and depends on Phase 3/4's
+  `@clasi_tool` decorator landing first (`02-mcp-tools.md` F5: the
+  NONE-sentinel stripping and call-logging taps three private FastMCP
+  internals that mcp 2.x removes).
 - `hook_handlers.py`, `plan_to_issue.py`, `staleness.py` — hook-time
   behavior (role/mcp guards, plan-mode capture, running-build drift).
   As of sprint 026, `handle_role_guard` resolves `Project`, its parsed
@@ -111,7 +165,39 @@
   through `_exit_hook` so plan-mode events appear in `hooks.log` at all
   (previously zero such events existed across 3,021 logged hook events).
   No guard decision logic changes — every existing allow/deny outcome is
-  unchanged; only what gets logged about each outcome changes.
+  unchanged; only what gets logged about each outcome changes. **As of
+  sprint 029**: `get_project()` gains upward `.clasi/` discovery — it
+  calls the already-proven `_find_project_root` walk (previously used
+  only by `_oop_active()` and `cli.py`'s `oop` command) instead of
+  `Project(Path.cwd())` directly, falling back to cwd unchanged when no
+  `.clasi/` is found in any ancestor; every handler inherits the fix with
+  no call-site change. A new frozen `HookPayload` dataclass
+  (`from_stdin`) is built once in `handle_hook` and consumed by all six
+  handlers in place of six hand-rolled extractions, validated by a new
+  parametrized replay test reading sprint 028's captured
+  `.clasi/log/denied/*.json` corpus. `handle_hook`'s try/except around
+  the role-guard/mcp-guard dispatch — added by sprint 028's ticket 005 as
+  catch/log/**re-raise-unchanged**, deliberately not fail-closed at the
+  time (see that sprint's ticket 005 for the explicit scope boundary) —
+  now calls `_exit_hook(event, payload, 2, "guard-crash")` instead of
+  re-raising: a guard crash is a logged, blocking exit, never a silent
+  allow. `_oop_active()`'s unconditional file-first bypass is unaffected
+  — it still runs inside each guard's own body, before this boundary can
+  matter, exactly as before. Role-guard's payload ingress gains an
+  `isinstance(tool_input, dict)` check; mcp-guard's tier check becomes an
+  allowlist (`in ("1", "2")`) instead of `not in ("", "0")`; malformed,
+  non-empty stdin logs a `bad-payload` token. This conversion is
+  deliberately the *last* change to land in sprint 029's own execution
+  order, not the first, despite being first in the issue that named it —
+  see that sprint's Architecture Design Rationale for why (this repo
+  dogfoods its own enforcement, and arming the boundary before reducing
+  the guard chain's own crash surface would risk blocking the very work
+  needed to finish reducing it). `staleness.py` gains a third signal:
+  `clasi/__init__.py` records `_IMPORT_TIME` at package import, and
+  `check_staleness` flags `stale: true` when any source `.py` file under
+  `Path(clasi.__file__).parent` has a newer mtime — closing the
+  same-version-drift gap the first two signals (version string, install
+  path) cannot see for a long-lived editable-install MCP server.
 - `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
   `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
   `dispatch_log.py` — installation, migration, versioning, worktree, and
@@ -155,6 +241,25 @@
   and git-subprocess results for the duration of one hook process, then
   discard the cache — there is no cross-invocation cache to invalidate,
   which keeps the caching addition free of staleness concerns.
+- **No component trusts the process's own working directory for root
+  resolution; every path resolves against a discovered or explicitly
+  passed root instead (sprint 029):** `get_project()` walks upward for
+  `.clasi/` rather than assuming cwd is the project root; every git
+  subprocess in the tools layer, `sprint.py`, and `design/overlay.py`
+  passes `cwd=project.root` via the shared `gitutil.run_git`; relative
+  artifact paths resolve against `project.root`, not the server
+  process's cwd. This generalizes the existing cwd-independence pattern
+  `_oop_active()` established narrowly (checking `.clasi/oop` from any
+  subdirectory) to every root-dependent operation in the package.
+- **A guard's default on an unresolved or unanticipated input is the
+  safe, loud action, never a silent success (sprint 029):** a guard
+  handler that raises exits 2 with a logged `guard-crash` line instead of
+  falling through to the harness's own non-2-exit-is-allow default; a
+  malformed or unrecognized payload shape denies with a distinct reason
+  rather than crash-allowing. `.clasi/oop`'s unconditional, file-checked-
+  first bypass remains the operator's escape hatch when this produces an
+  unwanted block — this invariant does not remove that escape hatch, it
+  only removes the *silent* failure mode.
 
 ## 4. See Also
 
```
