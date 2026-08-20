---
source_file: DESIGN.md
source_hash: bc015e5e47d9dd7adb72dd561264b4ad27060a4b749ced40a57cf39860200e3c
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -44,13 +44,26 @@
 **Top-level modules (the connective tissue):**
 
 - `mcp_server.py` / `cli.py` — the two entry surfaces (MCP server and
-  `clasi` CLI) over the same underlying operations.
+  `clasi` CLI) over the same underlying operations. As of sprint 028,
+  `_logged_call_tool` additionally times each call (`time.monotonic()`)
+  and appends one JSON line per call to `.clasi/log/mcp-calls.jsonl`
+  (`ts, agent, tool, args, ok, ms, result_len`), alongside its existing
+  human-readable `mcp-server.log` line, which now also carries the
+  duration (`OK name (NNNms)`) — the machine-readable half of the E2E
+  instrumentation plan (`05-e2e-test-infra.md`).
 - `project.py` — the root object; all path resolution, `sources`/
   `design_docs` config, and artifact-directory discovery flow through it.
 - `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
   the artifact model and its markdown+frontmatter substrate.
 - `state_db.py` / `state_db_class.py` — the SQLite state store backing
-  execution locks, gate results, and OOP records.
+  execution locks, gate results, and OOP records. As of sprint 028,
+  `_SCHEMA` also carries a `phase_transitions` table (`sprint_id,
+  from_phase, to_phase, at`), written by `advance_phase` in the same
+  transaction as the `sprints.phase` update it accompanies;
+  `get_sprint_phase` (`StateDB.get_sprint_state`, see `tools-DESIGN.md`)
+  exposes the resulting history as a timestamped list. Additive migration — existing
+  databases gain the table with no manual step, and there is no backfill
+  for phase transitions recorded before this sprint.
 - `hook_handlers.py`, `plan_to_issue.py`, `staleness.py` — hook-time
   behavior (role/mcp guards, plan-mode capture, running-build drift).
   As of sprint 026, `handle_role_guard` resolves `Project`, its parsed
@@ -86,7 +99,19 @@
   (the `click` CLI import chain `cli.py` pays on every invocation) is a
   contributing factor in the residual status-inject latency gap — see
   `status-DESIGN.md`'s sprint-027 entry for the git-subprocess-spawn
-  half of that same latency work.
+  half of that same latency work. As of sprint 028, `_exit_hook`/`_log_
+  hook_event` additionally accept a per-invocation `decisions:
+  list[str]` that handlers append to (e.g. `tier=2(db)`, `gate=ticket-
+  state:skipped(db-error)`, `missing=[file_path]`), emitted as trailing
+  tokens on the existing `hooks.log` line; every denial (`exit_code ==
+  2`, or a guard-internal exception) additionally dumps the full hook
+  payload to `.clasi/log/denied/<ts>-<hook>.json` (the directory
+  auto-gitignores via the existing `_ensure_log_gitignore` mechanism);
+  and `handle_plan_to_issue`/`handle_codex_plan_to_issue` are now routed
+  through `_exit_hook` so plan-mode events appear in `hooks.log` at all
+  (previously zero such events existed across 3,021 logged hook events).
+  No guard decision logic changes — every existing allow/deny outcome is
+  unchanged; only what gets logged about each outcome changes.
 - `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
   `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
   `dispatch_log.py` — installation, migration, versioning, worktree, and
```
