---
source_file: DESIGN.md
source_hash: 9b4a1627b58224fad613527efef6b23bad868fcc88bba9fadff4a6f18db94345
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -39,7 +39,12 @@
   shipped to installed projects.
 - `templates/` — packaged template resources served to skills/tools.
 - `tools/` — the MCP tool implementations (`artifact_tools`, `design_tools`,
-  `process_tools`) exposed by the server.
+  `process_tools`) exposed by the server. **As of sprint 030**: a new
+  `tools/_common.py` holds the `@clasi_tool` decorator (uniform
+  `{"ok": bool, ...}` result envelope, owned `"NONE"`-sentinel stripping,
+  per-call `mcp-calls.jsonl` tracing) and `resolve_artifact_path`
+  (relocated from `artifact_tools.py`, already root-anchored since
+  sprint 029) — see `tools-DESIGN.md`'s sprint-030 entry.
 
 **Top-level modules (the connective tissue):**
 
@@ -50,7 +55,20 @@
   (`ts, agent, tool, args, ok, ms, result_len`), alongside its existing
   human-readable `mcp-server.log` line, which now also carries the
   duration (`OK name (NNNms)`) — the machine-readable half of the E2E
-  instrumentation plan (`05-e2e-test-infra.md`).
+  instrumentation plan (`05-e2e-test-infra.md`). **As of sprint 030**:
+  both of `mcp_server.py`'s `run()`-time monkey-patches over private
+  `mcp`-library internals (`_tool_manager.call_tool`, which owned the
+  `"NONE"`-sentinel strip and the call trace above) are removed — that
+  behavior now lives in `tools/_common.py`'s `@clasi_tool` decorator,
+  applied per-function at import time instead of patched onto the
+  library's tool manager at server startup. This is the change that lets
+  `mcp-calls.jsonl` tracing and sentinel stripping survive an `mcp` 2.x
+  upgrade (2.x deletes `mcp.server.fastmcp` and the private attributes
+  the old patches read) — `@clasi_tool` depends on nothing beyond the
+  public `@server.tool()` decorator it wraps. The separate raw-RPC
+  diagnostic tap (`JSONRPCMessage.model_validate_json`, installed for a
+  now-closed investigation) is unchanged by this sprint — flagged as
+  Phase 4 debug-scaffolding cleanup, not touched here.
 - `project.py` — the root object; all path resolution, `sources`/
   `design_docs` config, and artifact-directory discovery flow through it.
 - `artifact.py`, `sprint.py`, `ticket.py`, `issue.py`, `frontmatter.py` —
@@ -64,7 +82,32 @@
   `list_sprints` would then silently drop. `yaml.dump` becomes
   `yaml.safe_dump`. `sprint.py`'s git subprocess calls now route through
   the new `gitutil.run_git(args, cwd=project.root)` instead of bare,
-  cwd-less `subprocess.run(["git", ...])`.
+  cwd-less `subprocess.run(["git", ...])`. **As of sprint 030**:
+  `sprint.py` gains `Sprint.set_sprint_stage(phase)`, the single writer
+  for a sprint's recorded stage — it writes the state-DB `phase` column
+  and the sprint's frontmatter `status:` field together (delegating the
+  DB half to `StateDB.set_phase`/`force_close`, see this doc's
+  `state_db_class.py` entry below), raising loudly if either half fails,
+  rather than leaving each transition to write frontmatter and advance
+  DB phase as two independent, non-transactional steps (the exact shape
+  of the drift finding 10 of the reliability review named). `detail_promote`,
+  `advance_phase`, and `archive` all route through it instead of calling
+  `sprint_doc.update_frontmatter` directly; `archive()` now writes
+  `status: "done"` (the state-DB vocabulary's own terminal string)
+  instead of `status: "closed"` (sprint 019's choice, reversed here — see
+  sprint 030's `sprint.md` Design Rationale: `"closed"` and `"done"` were
+  always two spellings of the one fact "this sprint is finished," and
+  this sprint collapses every sprint-stage record to the state-DB phase
+  vocabulary alone). No historical archive file is rewritten — a sprint
+  already under `sprints/done/` is exempt from stage consistency-checking
+  by directory location alone, regardless of which legacy `status:`
+  string it carries (10 of this repo's own 29 archived sprints carry
+  `"closed"`, 19 carry `"done"`; both are tolerated on read forever).
+  `ticket.py`'s `move_to_done()` is retained as the primitive a `"done"`
+  status transition uses, but the MCP-facing `update_ticket_status(path,
+  "done")` now performs the frontmatter write and the `tickets/done/`
+  move in one call, and `move_ticket_to_done` becomes a thin alias over
+  that same combined path — see `tools-DESIGN.md`'s sprint-030 entry.
 - `state_db.py` / `state_db_class.py` — the SQLite state store backing
   execution locks, gate results, and OOP records. As of sprint 028,
   `_SCHEMA` also carries a `phase_transitions` table (`sprint_id,
@@ -86,8 +129,18 @@
   5-second `PreToolUse` timeout (which, if reached, kills the process
   before any CLASI code — including the fail-closed boundary described
   below — can run; a residual gap this change narrows but does not
-  close, see that sprint's Architecture Migration Concerns).
-- `gitutil.py` (new, sprint 029) — one `run_git(args, cwd)` helper
+  close, see that sprint's Architecture Migration Concerns). **As of
+  sprint 030**: a new `StateDB.force_close(sprint_id)` sets `sprints.phase`
+  to `"done"` and deletes the held `execution_locks` row in one
+  transaction, replacing the `except (ValueError, Exception): pass`-
+  wrapped advance-and-release sequence `close_sprint` used to run —
+  a failure here is now surfaced to the caller, never swallowed. It is
+  idempotent (a call against a sprint already at phase `"done"` is a
+  cheap no-op), which is what lets a retried `close_sprint` call it
+  safely without re-deriving "did the last attempt already get this
+  far." No schema change: `force_close` writes the same `sprints` and
+  `execution_locks` tables every other phase/lock write already used.
+- `gitutil.py` (sprint 029) — one `run_git(args, cwd)` helper
   wrapping `subprocess.run(["git", *args], cwd=..., capture_output=True,
   text=True)`, promoted from `design/overlay.py`'s previously-local
   `_run_git` (deleted in favor of this shared version). `sprint.py`,
@@ -97,11 +150,39 @@
   all route their git subprocess calls through it, always passing
   `cwd=project.root` — closing the class of bug where a git call silently
   targets whatever directory the MCP server process happens to be in
-  (`02-mcp-tools.md` F3). Scoped deliberately small: the review's own
-  decomposition proposal groups a future `run_git` into a larger
-  `tools/_common.py` alongside the not-yet-designed uniform
-  `@clasi_tool` envelope — that is Phase 3/4 work (`uniform-mcp-tool-
-  envelope.md`), and this module does not preempt it.
+  (`02-mcp-tools.md` F3). **As of sprint 030**: this module is deliberately
+  *not* absorbed into the new `tools/_common.py` (see below) even though
+  the review's own decomposition proposal grouped a future `run_git` there
+  alongside the uniform `@clasi_tool` envelope — `sprint.py` and
+  `design/overlay.py` are core modules outside the `tools/` layer and both
+  depend on `run_git` directly; moving it into `tools/_common.py` would
+  make two core modules import from the tools layer, inverting this
+  package's tools-wraps-core dependency direction. `gitutil.py` stays a
+  shared leaf module both layers import, unchanged in content by this
+  sprint.
+- `close.py` (new, sprint 030) — `SprintCloser`, the resumable
+  close-sprint orchestration extracted out of `tools/artifact_tools.py`'s
+  former ~950-line `_close_sprint_full`. Each lifecycle step
+  (precondition check — now read-only; tests; archive; DB update via
+  `StateDB.force_close`; design-overlay apply; version bump; git merge;
+  tag push; branch delete; worktree prune) owns its own idempotency
+  check against ground truth (does the computed version's git tag
+  already exist; is the DB phase already `"done"`; is the sprint
+  directory already under `sprints/done/`) rather than consulting a
+  separately-maintained "completed steps" ledger — so a retry after a
+  partial failure skips real work without depending on a second
+  bookkeeping mechanism staying in sync with reality. Self-repair
+  (ticket/issue relocation, DB phase catch-up) now runs only *after* the
+  test gate passes, each repair recorded in `StateDB.recovery_state` as
+  it happens — previously this ran unconditionally in Step 1, before
+  tests, with no rollback on a later failure. The version-bump step
+  checks whether the computed tag already exists in git before bumping
+  again (closing the double-tag-on-retry defect); the tag-push step
+  pushes only the sprint's own tag by name, never `git push --tags`.
+  `tools/artifact_tools.py`'s `close_sprint` tool function becomes a thin
+  wrapper delegating to `close.SprintCloser`, the same "extract a
+  cohesive piece, leave a thin re-export at the call site" pattern
+  `skill_resolve.py` (below) already established for this package.
 - `skill_resolve.py` (new, sprint 029) — a single pure function,
   `resolve_skill_body`, resolving a skill's `Load from:` directive.
   Moved out of `tools/process_tools.py` (which still imports it back for
@@ -260,6 +341,27 @@
   first bypass remains the operator's escape hatch when this produces an
   unwanted block — this invariant does not remove that escape hatch, it
   only removes the *silent* failure mode.
+- **A sprint's lifecycle stage has exactly one recorded vocabulary and
+  one writer (sprint 030):** the state-DB `sprints.phase` column
+  (`roadmap` → `done`) is authoritative; `sprint.md`'s frontmatter
+  `status:` field is a mirror written by `Sprint.set_sprint_stage()` in
+  the same call, never independently. The computed sprint-machine
+  vocabulary (`open`/`planned`/`pre-flight`/…, see
+  `state_machine-DESIGN.md`) is a separate, intentionally different
+  concept — "what can happen next," not "what stage is recorded" — and
+  is no longer compared against frontmatter for drift; conflating the two
+  is exactly the category error `detect_inconsistencies` made before this
+  sprint (see `status-DESIGN.md`'s sprint-030 entry). A sprint physically
+  under `sprints/done/` is exempt from stage consistency-checking
+  regardless of which status string it carries, which is why none of the
+  29 sprints archived before this sprint needed editing.
+- **Every state-machine predicate and invariant is satisfiable by
+  something the shipped toolchain actually writes (sprint 030):** a
+  predicate referencing a DB phase string, gate name, or frontmatter flag
+  nothing writes is a defect, not a documentation gap — `clasi status`
+  must report against the process that runs, not an aspirational one. See
+  `state_machine-DESIGN.md`'s sprint-030 entry for the specific
+  predicates removed under this rule.
 
 ## 4. See Also
 
```
